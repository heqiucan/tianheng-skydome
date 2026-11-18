from __future__ import annotations

import asyncio
from time import perf_counter

from .database import Database, dump, new_id, utc_now
from .evidence import EvidenceService, tool_context, ordered_observations
from .rules import all_references, TEMPERATURE_THRESHOLD, RULE_VERSION
from .assessment import evidence_analysis, make_report


TERMINAL = {"completed", "cancelled", "failed", "interrupted"}


def query_sensor_data(db: Database, incident_id: str, evidence_snapshot_id: str | None = None) -> dict:
    context, metadata = tool_context(db, incident_id, evidence_snapshot_id)
    return {**metadata, "references": context.get("references", all_references()),
            "regional_observations": context["observations"], "observations": [o for o in context["observations"]
            if o["kind"] in {"temperature", "smoke_alarm", "water_pressure"}]}


def query_device_status(db: Database, incident_id: str, evidence_snapshot_id: str | None = None) -> dict:
    context, metadata = tool_context(db, incident_id, evidence_snapshot_id)
    return {**metadata, "devices": context["devices"]}


def query_event_history(db: Database, incident_id: str, evidence_snapshot_id: str | None = None) -> dict:
    context, metadata = tool_context(db, incident_id, evidence_snapshot_id)
    return {**metadata, "incidents": context["history"]}


def assess_risk(sensor_data: dict, device_data: dict, history_data: dict) -> dict:
    """Deterministic demonstration rules, not an operational fire safety standard."""
    latest = {}
    for observation in ordered_observations(sensor_data["observations"]):
        latest[(observation["device_id"], observation["kind"])] = observation
    valid = [o for o in latest.values() if o["quality"] in {"good", "alarm"} and o["value"] is not None]
    temps = [o for o in valid if o["kind"] == "temperature"]
    smoke = [o for o in valid if o["kind"] == "smoke_alarm"]
    references = sensor_data.get("references", all_references())
    temp_reference = next((item for item in references if item["kind"] == "temperature"), None)
    threshold = temp_reference["warning_condition"]["value"] if temp_reference and temp_reference.get("warning_condition") else TEMPERATURE_THRESHOLD
    temp_alarm = any(o["value"] >= threshold for o in temps)
    smoke_alarm = any(o["value"] == 1 for o in smoke)
    enough = bool(temps and smoke)
    if temp_alarm and smoke_alarm:
        level, title = "high", "多源异常需要优先人工复核"
    elif temp_alarm or smoke_alarm:
        level, title = "medium", "存在单项异常，需要补充核查"
    elif enough:
        level, title = "low", "当前演示记录未命中异常规则"
    else:
        level, title = "unknown", "信息不足，无法形成完整研判"
    reasons = []
    if temp_alarm:
        reasons.append(f"温度记录命中 ≥{threshold:g}°C 的演示阈值；此阈值不是消防认证标准。")
    if smoke_alarm:
        reasons.append("同一事件的烟雾传感器存在模拟告警。")
    if not reasons:
        reasons.append("仅根据已提供的监测记录核查；缺失数据不作正常处理。")
    uncertainties = ["所有设备记录均为预置模拟数据；未核实现场情况。", "当前为规则初步核查，未经过真实模型综合研判或人工审批。"]
    if not enough:
        uncertainties.append("温度或烟雾证据不完整，不能排除风险。")
    if any(d["status"] == "offline" for d in device_data["devices"]):
        uncertainties.append("关联设备存在离线状态，不能以其缺失读数判断现场正常。")
    if not history_data["incidents"]:
        uncertainties.append("本地尚无更早的同区域演示事件记录。")
    evidence = [{"label": "温度" if o["kind"] == "temperature" else "烟雾告警",
                 "value": f"{o['value']:g}{o['unit']}" if o["kind"] == "temperature" else ("触发" if o["value"] == 1 else "未触发"),
                 "source_id": o["id"]} for o in temps + smoke]
    trends, regional = evidence_analysis(sensor_data, device_data)
    for trend in trends:
        if trend["direction"] == "rising":
            reasons.append(f"{trend['device_code']} 在 {trend['duration_minutes']:g} 分钟内由 {trend['first_value']:g}℃升至 {trend['latest_value']:g}℃，增加 {trend['delta']:g}℃；仅反映所存模拟样本的变化。")
        elif trend["direction"] == "insufficient":
            uncertainties.append(f"{trend['device_code']} 缺少两个不同时间的有效温度样本，不能计算升温速率。")
    if any(o["quality"] not in {"good", "alarm"} or o["value"] is None for o in sensor_data["observations"]):
        uncertainties.append("存在无效或缺失观测，趋势计算已排除；数据缺失不能视为正常。")
    uncertainties.extend(["无现场视频核验、设备校准记录及实际工况资料，无法确定异常原因。", "同区域关联仅限保存的同事件设备记录，不代表已覆盖区域所有风险。"])
    causes = (["可能存在局部热源或设备运行升温，需结合实际工况核实。", "传感器误差或采样环境变化也可能影响读数，需补充校准记录与现场复测。"]
              if temp_alarm else ["现有证据不足以确定异常原因，应结合设备质量、现场工况和人工核查补充判断。"])
    return {"level": level, "title": title, "evidence": evidence, "reasons": reasons,
            "analysis_kind": "rule_based", "temperature_trends": trends, "regional_evidence": regional,
            "risk_judgment": title + "。温度异常不等于火灾；需要补充现场核验，不能根据模拟记录确认或排除火情。",
            "possible_causes": causes,
            "uncertainties": uncertainties,
            "recommendations": ["由授权人员依据正式校园预案复核现场信息。", "核对关联设备的通信状态和数据质量。", "保存研判报告后，可单独创建模拟巡检任务；需选择资源并确认启动。"],
            "rule_version": temp_reference["rule_version"] if temp_reference else RULE_VERSION, "is_demo": True, "scope": "preliminary_demo_assessment"}


class Workflow:
    def __init__(self, db: Database):
        self.db = db
        self.tasks: set[asyncio.Task] = set()
        self.signals: dict[str, asyncio.Event] = {}

    def signal(self, run_id):
        return self.signals.setdefault(run_id, asyncio.Event())

    def notify(self, run_id):
        self.signal(run_id).set()

    def event(self, run_id, **values):
        event = self.db.append_event(run_id, **values)
        self.notify(run_id)
        return event

    def recover_interrupted(self):
        rows = self.db.rows("SELECT id FROM agent_runs WHERE status IN ('queued','running')")
        for row in rows:
            self.db.execute("UPDATE agent_runs SET status='interrupted',stage='interrupted',finished_at=?,error=? WHERE id=?",
                            (utc_now(), "上次进程结束时核查尚未完成，可新建核查重试。", row["id"]))
            self.event(row["id"], type="terminal", stage="interrupted", status="interrupted", message="执行因服务重启而中断，已保存历史记录。")

    def create(self, conversation_id: str, incident_id: str, instruction: str, evidence_snapshot_id: str | None = None) -> dict:
        if evidence_snapshot_id:
            EvidenceService(self.db).for_run(evidence_snapshot_id, incident_id)
        run_id, now = new_id("run"), utc_now()
        with self.db.connection() as conn:
            conn.execute("INSERT INTO agent_runs(id,conversation_id,incident_id,instruction,status,stage,created_at,evidence_snapshot_id) VALUES (?,?,?,?,?,?,?,?)",
                         (run_id, conversation_id, incident_id, instruction, "queued", "queued", now, evidence_snapshot_id))
            conn.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (new_id("msg"), conversation_id, "user", instruction, now))
            conn.execute("UPDATE conversations SET title=? WHERE id=? AND title='新的安全核查'", (instruction[:36], conversation_id))
        self.event(run_id, type="stage", stage="queued", status="queued", message="已接收核查任务，使用选定事件与规则演示工作流。")
        return self.db.run(run_id)

    def start(self, run_id: str):
        task = asyncio.create_task(self.execute(run_id), name=f"workflow-{run_id}")
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def stopped(self, run_id) -> bool:
        row = self.db.row("SELECT cancel_requested,status FROM agent_runs WHERE id=?", (run_id,))
        return not row or row["cancel_requested"] or row["status"] in TERMINAL

    def cancel(self, run_id):
        changed = self.db.execute("UPDATE agent_runs SET cancel_requested=1,status='cancelled',stage='cancelled',finished_at=? WHERE id=? AND status IN ('queued','running')", (utc_now(), run_id))
        if changed:
            self.event(run_id, type="terminal", stage="cancelled", status="cancelled", message="已停止后续步骤；已经完成的查询记录保留。")
        return self.db.run(run_id)

    async def execute(self, run_id):
        if self.stopped(run_id):
            return
        self.db.execute("UPDATE agent_runs SET status='running',stage='planning',started_at=? WHERE id=?", (utc_now(), run_id))
        run = self.db.run(run_id)
        initial_incident = self.db.incident(run["incident_id"])
        self.event(run_id, type="plan", stage="planning", status="running", message="基础核查计划：监测数据 → 设备状态 → 历史事件 → 演示规则初评。", data={"mode": "demo", "steps": ["query_sensor_data", "query_device_status", "query_event_history", "demo_rule_assessment"]})
        outputs = {}
        try:
            for tool_name, tool, label in [
                ("query_sensor_data", query_sensor_data, "查询监测数据"),
                ("query_device_status", query_device_status, "查询关联设备"),
                ("query_event_history", query_event_history, "查询历史事件"),
            ]:
                if self.stopped(run_id):
                    return
                self.db.execute("UPDATE agent_runs SET stage='collecting' WHERE id=?", (run_id,))
                self.event(run_id, type="tool_start", stage="collecting", status="running", message=label, tool_name=tool_name, data={"incident_id": run["incident_id"], "evidence_snapshot_id": run.get("evidence_snapshot_id"), "data_scope": "event_snapshot"})
                started = perf_counter()
                if run.get("evidence_snapshot_id"):
                    output = await asyncio.to_thread(tool, self.db, run["incident_id"], run["evidence_snapshot_id"])
                else:
                    output = await asyncio.to_thread(tool, self.db, run["incident_id"])
                elapsed = round((perf_counter() - started) * 1000, 2)
                # A cancellation may arrive during the DB query. Do not schedule more tools.
                if self.stopped(run_id):
                    return
                outputs[tool_name] = output
                self.event(run_id, type="tool_result", stage="collecting", status="completed", message=f"{label}完成", tool_name=tool_name, duration_ms=elapsed, data=output)
            if self.stopped(run_id):
                return
            self.db.execute("UPDATE agent_runs SET stage='assessing' WHERE id=?", (run_id,))
            self.event(run_id, type="stage", stage="assessing", status="running", message="正在执行明确标注的演示风险规则。")
            result = assess_risk(outputs["query_sensor_data"], outputs["query_device_status"], outputs["query_event_history"])
            result["evidence_snapshot_id"] = run.get("evidence_snapshot_id")
            result["data_scope"] = "event_snapshot"
            result["report_id"] = new_id("assessment-report")
            if run.get("evidence_snapshot_id"):
                report_context = EvidenceService(self.db).get(run["evidence_snapshot_id"])
                report_context = {**report_context, "references": outputs["query_sensor_data"]["references"]}
            else:
                report_context = {"incident": initial_incident, "devices": outputs["query_device_status"]["devices"],
                                  "observations": outputs["query_sensor_data"].get("regional_observations", outputs["query_sensor_data"]["observations"]),
                                  "references": outputs["query_sensor_data"].get("references", all_references()),
                                  "source_context": {"source_view": "workbench", "image_id": None,
                                                     "selection": {"kind": "incident", "id": run["incident_id"]}}}
            finished_at = utc_now()
            report = make_report(run, result, report_context, finished_at)
            summary = "基础数据核查完成。" + result["title"] + "；这不是已批准的处置方案。"
            with self.db.connection() as conn:
                changed = conn.execute("UPDATE agent_runs SET status='completed',stage='completed',finished_at=?,summary=?,result=? WHERE id=? AND status='running' AND cancel_requested=0", (finished_at, summary, dump(result), run_id)).rowcount
                if changed:
                    conn.execute("INSERT INTO assessment_reports VALUES (?,?,?,?,?,?)", (report["id"], run_id, run["incident_id"], run.get("evidence_snapshot_id"), dump(report), finished_at))
                    conn.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (new_id("msg"), run["conversation_id"], "assistant", summary, utc_now()))
                    conn.execute("UPDATE incidents SET risk_level=?,summary=? WHERE id=?", (result["level"], summary, run["incident_id"]))
            if changed:
                self.event(run_id, type="terminal", stage="completed", status="completed", message=summary, data={"result": result, "next_milestone": "研判报告已保存，可选择创建模拟执行任务；当前未接入大模型规划。"})
        except asyncio.CancelledError:
            if not self.stopped(run_id):
                self.db.execute("UPDATE agent_runs SET status='interrupted',stage='interrupted',finished_at=? WHERE id=?", (utc_now(), run_id))
                self.event(run_id, type="terminal", stage="interrupted", status="interrupted", message="服务停止，核查中断，已有记录已保存。")
            raise
        except Exception as error:
            if not self.stopped(run_id):
                message = "基础核查执行失败，已有记录已保存，请重新发起核查。"
                self.db.execute("UPDATE agent_runs SET status='failed',stage='failed',finished_at=?,error=? WHERE id=?", (utc_now(), message, run_id))
                self.event(run_id, type="terminal", stage="failed", status="failed", message=message, data={"error_type": type(error).__name__})

    async def shutdown(self):
        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
