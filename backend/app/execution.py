"""Persistent, server-timed 演示 execution; no physical dispatch or model calls."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from .database import Database, dump, new_id, utc_now
from .evidence import EvidenceService, device_status, latest_by_device, ordered_observations, timestamp
from .spatial import advance_patrol, inspection_route, offset_anchor, point_along_route
from .demo_scenario import INCIDENT_ID as PRESENTATION_INCIDENT, TASK_CODE as PRESENTATION_TASK


ACTIVE = {"dispatching", "running"}
TERMINAL = {"completed", "cancelled", "failed"}
TYPES = {"aerial_inspection": "drone", "ground_inspection": "robot", "remote_sensing": "satellite"}
TYPE_LABELS = {"aerial_inspection": "无人机模拟巡检", "ground_inspection": "机器人模拟巡检", "remote_sensing": "区域遥感模拟复核"}
RESOURCE_DEFINITIONS = [
    {"id": "UAV-003", "code": "UAV-003", "name": "巡检无人机（设备 DRONE-001）", "type": "drone", "device_id": "dev-drone-01",
     "area": "杭州校区 · 演示", "capabilities": ["模拟空中巡检", "规划效果图归一化路线；未采集真实视频"]},
    {"id": "ROBOT-002", "code": "ROBOT-002", "name": "地面机器人（设备 ROBOT-001）", "type": "robot", "device_id": "dev-robot-01",
     "area": "杭州校区 · 演示", "capabilities": ["模拟地面巡检", "示意路线；不具备真实避障导航"]},
    {"id": "SAT-001", "code": "SAT-001", "name": "区域遥感复核（纯模拟）", "type": "satellite", "device_id": None,
     "area": "杭州校区演示范围；无真实遥感覆盖", "capabilities": ["模拟区域复核流程", "未接入卫星设备或遥感影像"]},
]


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


class ExecutionService:
    def __init__(self, db: Database, catalog_provider=None):
        self.db = db
        self.catalog_provider = catalog_provider

    def catalog(self):
        if self.catalog_provider:
            return self.catalog_provider()
        try:
            return json.loads(Path(__file__).with_name("map_catalog.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise HTTPException(503, "校园素材目录尚未就绪") from error

    @staticmethod
    def _get(conn, task_id):
        row = conn.execute("SELECT payload FROM execution_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "执行任务不存在")
        task = json.loads(row[0])
        task.setdefault("incident_code", None)
        return task

    @staticmethod
    def _save(conn, task):
        conn.execute("UPDATE execution_tasks SET resource_id=?,status=?,payload=? WHERE id=?",
                     (task["resource_id"], task["status"], dump(task), task["id"]))

    @staticmethod
    def _log(task, kind, message, at):
        task["logs"].append({"id": new_id("tasklog"), "sequence": len(task["logs"]) + 1,
                             "at": at, "kind": kind, "message": message})

    @staticmethod
    def _device_records(conn):
        return latest_by_device(ordered_observations([dict(row) for row in conn.execute("SELECT * FROM observations ORDER BY rowid")]))

    def _report(self, conn, task, at):
        source = json.loads(conn.execute("SELECT payload FROM execution_task_sources WHERE task_id=?", (task["id"],)).fetchone()[0])
        observations = source["context"].get("observations", [])
        findings = [f"目标：{task['target_building_name']}；关联事件：{task['incident_title']}（{task['incident_id']}）。",
                    f"{task['resource_code']} 已完成 {TYPE_LABELS[task['task_type']]}流程，进度 100%；此状态仅表示模拟流程完成。"]
        for observation in observations[-4:]:
            findings.append(f"任务来源证据 {observation['device_id']} / {observation['kind']}：{observation['value']} {observation['unit']}，记录时间 {observation['observed_at']}；不是本次巡检新采集数据。")
        if source.get("assessment"):
            findings.append(f"来源为确定性规则初评：{source['assessment'].get('level', 'unknown')}；未调用大模型规划。")
        limitations = ["本报告为 演示 模拟执行记录，未采集真实传感器、视频或遥测数据。",
                       "校园底图为规划效果图，位置和路线为图像归一化示意；不代表真实调度或可通行路线。",
                       "模拟完成不等于风险消除，原风险事件未自动关闭；需要人工复核。"]
        if task["task_type"] == "remote_sensing":
            limitations.append("未接入卫星、真实覆盖范围或遥感影像；不存在实际飞行路线或影像采集。")
        if task["task_type"] == "ground_inspection":
            limitations.append("机器人路线仅为示意，不包含道路通行、障碍物或避障算法。")
        return {"id": new_id("execution-report"), "task_id": task["id"], "task_code": task["code"],
                "title": f"{task['title']} · 演示 执行记录", "incident_id": task["incident_id"],
                "source_run_id": task["source_run_id"], "evidence_snapshot_id": task["evidence_snapshot_id"],
                "resource_id": task["resource_id"], "resource_code": task["resource_code"],
                "started_at": task["started_at"], "finished_at": at, "generated_at": at,
                "scope": f"{task['target_building_name']} / {task['incident_id']}",
                "summary": f"{task['code']} 使用 {task['resource_code']} 完成对 {task['target_building_name']} 的模拟执行流程；结果待人工复核。",
                "findings": findings, "recommendations": ["由授权人员核实关联设备及现场情况。", "将人工复核结果另行记录，再决定风险事件后续状态。"],
                "limitations": limitations, "verification_status": "requires_human_review", "is_simulated": True}

    def _advance(self, conn, task, now, device_records):
        if task["status"] not in ACTIVE:
            return task
        definition = next(resource for resource in RESOURCE_DEFINITIONS if resource["id"] == task["resource_id"])
        at = iso(now)
        if definition["device_id"] and device_status(device_records.get(definition["device_id"], {})) != "online":
            task.update(status="failed", finished_at=at, updated_at=at,
                        error="资源最新观测不可用，模拟执行已停止；请恢复设备状态后创建重试任务。")
            for step in task["steps"]:
                if step["status"] in {"pending", "running"}:
                    step.update(status="failed", finished_at=at)
            self._log(task, "failed", task["error"], at)
            return task
        started = timestamp(task["started_at"])
        elapsed = max(0, (now - started).total_seconds())
        execution_start = started + timedelta(seconds=task["dispatch_seconds"])
        if elapsed >= task["dispatch_seconds"] and task["status"] == "dispatching":
            task.update(status="running", updated_at=iso(execution_start))
            task["steps"][0].update(status="completed", finished_at=iso(execution_start))
            task["steps"][1].update(status="running", started_at=iso(execution_start))
            self._log(task, "running", "演示 资源调度完成，开始模拟执行；计时不代表实际作业时长。", iso(execution_start))
        if task["status"] == "running":
            task["progress"] = round(min(100, max(0, (elapsed - task["dispatch_seconds"]) / task["duration_seconds"] * 100)), 2)
            task["position"] = point_along_route(task["route"], task["progress"])
            task["updated_at"] = at
            if task["progress"] >= 100:
                finish = iso(execution_start + timedelta(seconds=task["duration_seconds"]))
                task.update(status="completed", finished_at=finish, updated_at=finish)
                task["steps"][1].update(status="completed", finished_at=finish)
                task["steps"][2].update(status="completed", started_at=finish, finished_at=finish)
                task["report"] = self._report(conn, task, finish)
                self._log(task, "completed", "演示 模拟执行完成，已保存结果；风险事件保持原状态，等待人工复核。", finish)
        return task

    def _sync(self, conn):
        now = timestamp(utc_now())
        records = self._device_records(conn)
        tasks = []
        for row in conn.execute("SELECT payload FROM execution_tasks ORDER BY rowid DESC").fetchall():
            task = self._advance(conn, json.loads(row[0]), now, records)
            if dump(task) != row[0]:
                self._save(conn, task)
            task.setdefault("incident_code", None)
            tasks.append(task)
        patrols = []
        for row in conn.execute("SELECT payload FROM patrol_missions ORDER BY rowid DESC").fetchall():
            patrol = advance_patrol(json.loads(row[0]), now)
            if dump(patrol) != row[0]:
                conn.execute("UPDATE patrol_missions SET payload=? WHERE id=?", (dump(patrol), patrol["id"]))
            patrols.append(patrol)
        return tasks, patrols, records

    def _resources(self, tasks, patrols, records, task=None):
        result = []
        for definition in RESOURCE_DEFINITIONS:
            resource = dict(definition)
            readings = records.get(resource["device_id"], {})
            online = resource["device_id"] is None or device_status(readings) == "online"
            active = next((item for item in tasks if item["resource_id"] == resource["id"] and item["status"] in ACTIVE), None)
            legacy = next((item for item in patrols if item["device_id"] == resource["device_id"] and item["status"] == "running"), None)
            busy = active is not None or legacy is not None
            reason = None
            if task and TYPES[task["task_type"]] != resource["type"]:
                reason = "资源类型与任务类型不匹配"
            elif not online:
                reason = "资源当前离线或状态不可用，请先核实最新观测"
            elif busy:
                reason = "资源已被进行中的任务占用" if active else "资源已被第二天空间巡检占用"
            elif task and resource["type"] != "satellite" and not task["target_point"]:
                reason = "目标建筑位置待核实；请补充并确认地图锚点后重新创建任务"
            elif task and task["status"] != "pending":
                reason = "仅待执行任务可以选择资源"
            resource.update(status="offline" if not online else "busy" if busy else "available", online=online,
                            current_task_id=active["id"] if active else legacy["id"] if legacy else None,
                            current_task_code=active["code"] if active else "DAY2 巡检" if legacy else None,
                            battery=readings.get("battery", {}).get("value"), eligible=reason is None,
                            reason=reason, is_simulated=True)
            result.append(resource)
        return result

    def overview(self):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            tasks, patrols, records = self._sync(conn)
            return {"tasks": tasks, "resources": self._resources(tasks, patrols, records)}

    def list(self, incident_id=None, run_id=None):
        return [task for task in self.overview()["tasks"]
                if (not incident_id or task["incident_id"] == incident_id) and (not run_id or task["source_run_id"] == run_id)]

    def get(self, task_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn)
            return self._get(conn, task_id)

    def resources(self, task_id=None):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            tasks, patrols, records = self._sync(conn)
            task = self._get(conn, task_id) if task_id else None
            return self._resources(tasks, patrols, records, task)

    def _new(self, conn, context, task_type, title, priority, source_run_id=None, snapshot_id=None, assessment=None, parent=None):
        incident = context["incident"]
        if not incident.get("building_id"):
            raise HTTPException(422, "事件缺少目标建筑关联，请先核实空间信息")
        space = next((item for item in self.catalog()["spaces"] if item["id"] == incident["building_id"]), None)
        if not space:
            raise HTTPException(422, "目标建筑尚未登记在校园空间目录中")
        at = utc_now()
        code_number = conn.execute("SELECT COALESCE(MAX(CAST(substr(code,6) AS INTEGER)),0)+1 FROM execution_tasks").fetchone()[0]
        # Reserve 008 for a genuine first aerial task derived from EVT-008.
        # The natural gap at 007 does not represent a fabricated task.
        code = f"TASK-{code_number:03d}"
        special = incident["id"] == PRESENTATION_INCIDENT and source_run_id and task_type == "aerial_inspection" and parent is None
        reserved = conn.execute("SELECT incident_id,source_run_id,task_type FROM execution_tasks WHERE code=?", (PRESENTATION_TASK,)).fetchone()
        if special and reserved is None:
            code = PRESENTATION_TASK
        elif special and (reserved[0] != PRESENTATION_INCIDENT or not reserved[1] or reserved[2] != "aerial_inspection"):
            raise HTTPException(409, "TASK-008 已被无关历史任务占用；系统保留历史，请先核查编号冲突")
        elif code == PRESENTATION_TASK:
            code = "TASK-009"
        anchor = space.get("anchor")
        task = {"id": new_id("execution"), "code": code, "title": title, "task_type": task_type,
                "source_kind": "rule_assessment" if source_run_id else "manual_demo",
                "source_label": "规则核查生成 · 演示（非大模型规划）" if source_run_id else "手动创建 · 演示",
                "source_run_id": source_run_id, "evidence_snapshot_id": snapshot_id,
                "incident_id": incident["id"], "incident_code": incident.get("code"), "incident_title": incident["title"], "device_ids": list(incident["device_ids"]),
                "target_building_id": incident["building_id"], "target_building_name": incident["building_name"],
                "priority": priority, "risk_level": assessment.get("level", incident["risk_level"]) if assessment else incident["risk_level"],
                "resource_id": None, "resource_code": None, "resource_name": None, "status": "pending", "progress": 0,
                "created_at": at, "updated_at": at, "started_at": None, "finished_at": None,
                "dispatch_seconds": 3, "duration_seconds": 24, "image_id": anchor["image_id"] if anchor else None,
                "route": [], "position": None, "target_point": {"x": anchor["x"], "y": anchor["y"]} if anchor else None,
                "patrol_id": None, "parent_task_id": parent["id"] if parent else None,
                "attempt": parent["attempt"] + 1 if parent else 1,
                "steps": [{"id": name, "title": label, "status": "pending", "started_at": None, "finished_at": None}
                          for name, label in [("dispatch", "模拟资源调度"), ("execute", "模拟巡检 / 区域复核"), ("report", "保存记录，等待人工复核")]],
                "logs": [], "report": None, "error": None, "is_simulated": True}
        if parent:
            for key in ("incident_title", "device_ids", "target_building_id", "target_building_name", "risk_level", "image_id", "target_point"):
                task[key] = deepcopy(parent[key])
        self._log(task, "created", f"{task['source_label']}：已关联事件 {task['incident_id']}，等待选择资源。", at)
        conn.execute("INSERT INTO execution_tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (task["id"], task["code"], task["incident_id"], source_run_id, task_type, task["parent_task_id"], None, "pending", dump(task), at))
        conn.execute("INSERT INTO execution_task_sources VALUES (?,?)", (task["id"], dump({"context": context, "assessment": assessment})))
        return task

    def create(self, body):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            context = EvidenceService(self.db)._context(conn, body.incident_id)
            return self._new(conn, context, body.task_type, body.title, body.priority)

    def from_run(self, body):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT payload FROM execution_tasks WHERE source_run_id=? AND task_type=? AND parent_task_id IS NULL",
                                    (body.run_id, body.task_type)).fetchone()
            if existing:
                self._sync(conn)
                return self._get(conn, json.loads(existing[0])["id"])
            run = conn.execute("SELECT * FROM agent_runs WHERE id=?", (body.run_id,)).fetchone()
            if not run:
                raise HTTPException(404, "来源核查记录不存在")
            if run["status"] != "completed" or not run["result"] or not run["evidence_snapshot_id"]:
                raise HTTPException(409, "请先完成绑定证据快照的规则核查，再创建执行任务")
            context = json.loads(conn.execute("SELECT payload FROM evidence_snapshots WHERE id=?", (run["evidence_snapshot_id"],)).fetchone()[0])
            assessment = json.loads(run["result"])
            if context["incident"]["id"] != run["incident_id"]:
                raise HTTPException(409, "来源核查与证据快照关联不一致")
            priority = assessment.get("level") if assessment.get("level") in {"high", "medium", "low"} else "medium"
            return self._new(conn, context, body.task_type, f"{context['incident']['title']} · {TYPE_LABELS[body.task_type]}",
                             priority, run["id"], run["evidence_snapshot_id"], assessment)

    def _resource_for(self, conn, task, resource_id):
        tasks, patrols, records = self._sync(conn)
        resource = next((item for item in self._resources(tasks, patrols, records, task) if item["id"] == resource_id), None)
        if not resource:
            raise HTTPException(404, "执行资源不存在")
        if not resource["eligible"]:
            raise HTTPException(409 if resource["status"] == "busy" else 422, resource["reason"])
        return resource

    def assign(self, task_id, resource_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn)
            task = self._get(conn, task_id)
            if task["status"] != "pending":
                raise HTTPException(409, "仅待执行任务可以更换资源")
            resource = self._resource_for(conn, task, resource_id)
            if task["resource_id"] == resource_id:
                return task
            at = utc_now()
            task.update(resource_id=resource_id, resource_code=resource["code"], resource_name=resource["name"], updated_at=at)
            if resource["type"] != "satellite":
                anchor = {"image_id": task["image_id"], **task["target_point"]}
                training = next((space for space in self.catalog()["spaces"] if space["id"] == "loc-training"), {})
                start = offset_anchor(training.get("anchor"), .07 if resource["type"] == "robot" else -.10,
                                      .09 if resource["type"] == "robot" else -.10)
                task["route"] = inspection_route(anchor, start, resource["type"] == "robot")
                task["position"] = point_along_route(task["route"], 0)
            self._log(task, "assigned", f"选择 {resource['code']} · {resource['name']}（演示）；启动后才占用资源。", at)
            self._save(conn, task)
            return task

    def start(self, task_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn)
            task = self._get(conn, task_id)
            if task["status"] in ACTIVE:
                return task
            if task["status"] != "pending":
                raise HTTPException(409, "任务已结束；请创建重试任务")
            if not task["resource_id"]:
                raise HTTPException(422, "请先选择兼容且在线的执行资源")
            self._resource_for(conn, task, task["resource_id"])
            at = utc_now()
            task.update(status="dispatching", started_at=at, updated_at=at)
            task["steps"][0].update(status="running", started_at=at)
            self._log(task, "dispatching", "已原子预留 演示 资源，开始 3 秒模拟调度；随后执行 24 秒演示流程。", at)
            self._save(conn, task)
            return task

    def cancel(self, task_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn)
            task = self._get(conn, task_id)
            if task["status"] == "cancelled":
                return task
            if task["status"] in TERMINAL:
                raise HTTPException(409, "已完成或失败的任务不能取消，可创建重试任务")
            at = utc_now()
            task.update(status="cancelled", finished_at=at, updated_at=at)
            for step in task["steps"]:
                if step["status"] in {"pending", "running"}:
                    step.update(status="cancelled", finished_at=at)
            self._log(task, "cancelled", "已取消模拟执行并释放资源；保留已执行进度和历史记录。", at)
            self._save(conn, task)
            return task

    def retry(self, task_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync(conn)
            task = self._get(conn, task_id)
            if task["status"] not in TERMINAL:
                raise HTTPException(409, "仅已结束的任务可以创建重试")
            child = conn.execute("SELECT payload FROM execution_tasks WHERE parent_task_id=?", (task_id,)).fetchone()
            if child:
                return json.loads(child[0])
            source = json.loads(conn.execute("SELECT payload FROM execution_task_sources WHERE task_id=?", (task_id,)).fetchone()[0])
            return self._new(conn, source["context"], task["task_type"], task["title"], task["priority"],
                             task["source_run_id"], task["evidence_snapshot_id"], source["assessment"], task)

    def report(self, task_id):
        task = self.get(task_id)
        if task["status"] != "completed":
            raise HTTPException(409, "任务尚未完成，暂无执行报告")
        return task["report"]

    def assert_device_available(self, conn, device_id):
        """Called inside the legacy patrol transaction: both paths share the lock."""
        tasks, patrols, records = self._sync(conn)
        resource = next((item for item in self._resources(tasks, patrols, records) if item["device_id"] == device_id), None)
        if resource and resource["status"] == "busy":
            raise HTTPException(409, "该设备已被执行任务或地图巡检占用，请等待完成或取消任务")
        if resource and not resource["online"]:
            raise HTTPException(422, "设备当前不可用，请先核实最新观测")
