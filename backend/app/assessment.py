"""Evidence-derived rule analysis and immutable assessment report reads."""
import json
from copy import deepcopy

from fastapi import HTTPException

from .evidence import ordered_observations, timestamp
from .fixtures import DEVICE_CODES


def evidence_analysis(sensor_data, device_data):
    observations = ordered_observations(sensor_data.get("regional_observations", sensor_data["observations"]))
    latest = {}
    for observation in observations:
        latest[(observation["device_id"], observation["kind"])] = observation
    regional = []
    for observation in latest.values():
        kind, value, quality = observation["kind"], observation["value"], observation["quality"]
        if quality not in {"good", "alarm"} or value is None:
            interpretation = "证据质量不可用，不能据此判定正常"
        elif kind == "connectivity":
            interpretation = "模拟通信在线，仅代表连接状态，不证明现场安全" if value == 1 else "模拟通信离线，需要核查缺失数据"
        elif kind == "camera_event":
            interpretation = "无模拟摄像机异常记录；未执行视频识别，不能确认现场无异常" if value == 0 else "存在模拟摄像机异常记录；尚无真实视频核验"
        elif kind == "smoke_alarm":
            interpretation = "模拟烟雾未触发；不能单独排除现场风险" if value == 0 else "模拟烟雾告警，需要人工复核"
        elif kind == "temperature":
            interpretation = "温度观测，需结合变化趋势与同事件其他证据判断"
        else:
            interpretation = "同事件保存的模拟观测；未配置该指标的现场诊断标准"
        regional.append({"device_id": observation["device_id"], "device_code": DEVICE_CODES.get(observation["device_id"], observation["device_id"]),
                         "kind": kind, "observation_id": observation["id"], "observed_at": observation["observed_at"],
                         "value": value, "unit": observation["unit"], "quality": quality,
                         "interpretation": interpretation, "data_scope": "event_snapshot"})
    temperature_ids = {observation["device_id"] for observation in observations if observation["kind"] == "temperature"}
    temperature_ids.update(device["id"] for device in device_data["devices"] if device["type"] == "temperature")
    trends = []
    for device_id in sorted(temperature_ids):
        # Equal absolute instants use the last inserted sample, matching current-state queries.
        samples_by_time = {}
        for observation in observations:
            if observation["device_id"] == device_id and observation["kind"] == "temperature":
                samples_by_time[timestamp(observation["observed_at"])] = observation
        # A later invalid reading replaces, rather than resurrects, an earlier
        # valid reading at the same instant. Filter quality after deduplication.
        samples = [sample for sample in samples_by_time.values()
                   if sample["quality"] in {"good", "alarm"} and sample["value"] is not None]
        first, last = (samples[0], samples[-1]) if samples else (None, None)
        duration = (timestamp(last["observed_at"]) - timestamp(first["observed_at"])).total_seconds() / 60 if len(samples) >= 2 else None
        delta = last["value"] - first["value"] if len(samples) >= 2 else None
        trends.append({"device_id": device_id, "device_code": DEVICE_CODES.get(device_id, device_id), "sample_count": len(samples),
                       "started_at": first["observed_at"] if first else None, "ended_at": last["observed_at"] if last else None,
                       "first_value": first["value"] if first else None, "latest_value": last["value"] if last else None,
                       "delta": round(delta, 3) if delta is not None else None, "duration_minutes": round(duration, 4) if duration is not None else None,
                       "slope_per_minute": round(delta / duration, 4) if duration and delta is not None else None,
                       "direction": "insufficient" if delta is None or not duration else "rising" if delta > 0 else "falling" if delta < 0 else "stable",
                       "observation_ids": [sample["id"] for sample in samples]})
    return trends, regional


def make_report(run, result, context, created_at):
    return {"id": result["report_id"], "run_id": run["id"], "incident_id": run["incident_id"],
            "incident_code": context["incident"].get("code"), "evidence_snapshot_id": run.get("evidence_snapshot_id"),
            "title": f"{context['incident']['title']} · 规则研判报告", "created_at": created_at,
            "analysis_kind": "rule_based", "rule_version": result["rule_version"], "incident": context["incident"],
            "devices": context["devices"], "observations": context["observations"], "references": context["references"],
            "assessment": deepcopy(result), "source_context": context["source_context"],
            "limitations": ["本报告由已保存的模拟证据和确定性规则生成，未调用大模型。",
                            "温度异常不等于火灾；规则阈值不是设备规范或经审定的安全标准。",
                            "摄像机在线或无异常记录不代表已完成视频识别或现场核验。",
                            "报告生成不代表事件已处置或风险已消除，后续模拟执行仍需单独确认。"]
                           + ([] if run.get("evidence_snapshot_id") else ["该兼容入口未绑定事前证据快照，报告保存的是本次实际工具查询返回的数据。"]),
            "is_simulated": True}


class AssessmentReports:
    def __init__(self, db):
        self.db = db

    def get(self, report_id):
        row = self.db.row("SELECT payload FROM assessment_reports WHERE id=?", (report_id,))
        if not row:
            raise HTTPException(404, "研判报告不存在；历史核查不会使用当前数据重新生成报告")
        return json.loads(row["payload"])

    def for_run(self, run_id):
        row = self.db.row("SELECT payload FROM assessment_reports WHERE run_id=?", (run_id,))
        if not row:
            raise HTTPException(404, "该核查没有已保存的研判报告；历史记录不会自动重算")
        return json.loads(row["payload"])

    def list(self, incident_id=None, device_id=None):
        reports = [json.loads(row["payload"]) for row in self.db.rows("SELECT payload FROM assessment_reports ORDER BY rowid DESC")]
        return [report for report in reports if (not incident_id or report["incident_id"] == incident_id)
                and (not device_id or device_id in {device["id"] for device in report["devices"]})]
