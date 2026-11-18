"""Shared Day 2 snapshot and persisted, explicitly simulated spatial tasks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import Field

from .database import Database, dump, new_id, utc_now
from .fixtures import DEVICE_CODES, ROBOT_TASK
from .schemas import StrictRequest
from .evidence import METRICS, associated_device_ids, device_status, latest_by_device, metric, ordered_observations, timestamp
from .spatial import advance_patrol, inspection_route, offset_anchor
from .rules import references_for


class SourceSelection(StrictRequest):
    kind: Literal["building", "device", "incident"]
    id: str = Field(min_length=1, max_length=100)


class MapTaskCreate(StrictRequest):
    instruction: str = Field(min_length=1, max_length=2000)
    action: Literal["campus", "building", "anomalies", "patrol", "report"]
    source_view: Literal["overview", "map", "coordination"]
    image_id: str = Field(min_length=1, max_length=100)
    building_id: str | None = None
    device_ids: list[str] = Field(default_factory=list, max_length=30)
    incident_ids: list[str] = Field(default_factory=list, max_length=100)
    source_selection: SourceSelection | None = None


class PatrolCreate(StrictRequest):
    device_id: str = Field(min_length=1, max_length=100)
    target_building_id: str = Field(min_length=1, max_length=100)


DEVICE_OFFSETS = {
    "dev-temp-01": (-.032, -.025), "dev-smoke-01": (.026, -.035),
    "dev-camera-01": (.048, .015), "dev-water-01": (-.04, .035),
    "dev-robot-01": (.07, .09), "dev-drone-01": (-.10, -.10),
    "dev-camera-02": (-.02, 0), "dev-temp-02": (.02, 0),
    "dev-smoke-02": (.015, .01),
}


class Situation:
    def __init__(self, db: Database):
        self.db = db
        self.catalog_path = Path(__file__).with_name("map_catalog.json")

    def catalog(self) -> dict:
        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            if not isinstance(data.get("images"), list) or not isinstance(data.get("spaces"), list):
                raise ValueError("invalid map catalog")
            return data
        except (OSError, ValueError, TypeError) as error:
            raise HTTPException(503, "校园素材目录尚未就绪；不会替换成虚构校园。") from error

    def building_id(self, location_id: str, locations: dict) -> str | None:
        location = locations.get(location_id)
        seen = set()
        while location and location["id"] not in seen:
            seen.add(location["id"])
            if location["kind"] in {"building", "area"}:
                return location["id"]
            location = locations.get(location.get("parent_id"))
        return None

    @staticmethod
    def offset_anchor(anchor: dict | None, dx=0, dy=0, note="DEMO 布点，非学校真实部署"):
        return offset_anchor(anchor, dx, dy, note)

    def snapshot(self) -> dict:
        catalog = self.catalog()
        spaces = catalog["spaces"]
        space_by_id = {s["id"]: s for s in spaces}
        locations = {l["id"]: l for l in self.db.rows("SELECT * FROM locations")}
        observations = ordered_observations(self.db.rows("SELECT * FROM observations ORDER BY rowid"))
        raw_devices = self.db.rows("SELECT * FROM devices ORDER BY id")
        raw_incidents = self.db.incidents()
        latest = latest_by_device(observations)
        event_devices = {i["id"]: associated_device_ids(i, raw_devices, observations) for i in raw_incidents}
        devices = []
        for d in raw_devices:
            records = latest.get(d["id"], {})
            building_id = self.building_id(d["location_id"], locations)
            # Mobile demo equipment starts beside the training building, with an explicit label.
            anchor_space = space_by_id.get(building_id or "loc-training")
            anchor = self.offset_anchor(anchor_space.get("anchor") if anchor_space else None,
                                        *DEVICE_OFFSETS.get(d["id"], (0, 0)))
            kind = "fire" if d["type"] == "water_pressure" else d["type"]
            preferred = {"temperature": "temperature", "smoke": "smoke_alarm", "camera": "connectivity",
                         "fire": "water_pressure", "robot": "battery", "drone": "battery"}.get(kind)
            history = [o for o in observations if o["device_id"] == d["id"] and o["kind"] == preferred and o["value"] is not None][-12:]
            state = device_status(records)
            metrics = [metric(o, "current_device_state") for o in records.values()]
            devices.append({
                "id": d["id"], "code": DEVICE_CODES.get(d["id"], d["id"]), "name": d["name"], "type": kind,
                "building_id": building_id, "floor": "室外（DEMO 位置）" if kind in {"drone", "robot"} else
                    ("二层（DEMO，真实楼层待核实）" if d["location_id"] == "loc-training-2f" else "待核实 / DEMO 布点"),
                "status": state, "last_seen": max((o["observed_at"] for o in records.values()), key=timestamp, default=None),
                "alarm": state in {"alarm", "offline"}, "anchor": anchor, "metrics": metrics,
                "references": references_for(d["type"]),
                "trend": [{"time": o["observed_at"], "value": o["value"]} for o in history],
                "related_device_ids": [], "incident_ids": [i for i, ids in event_devices.items() if d["id"] in ids],
                "battery": records.get("battery", {}).get("value"), "is_simulated": True,
            })
        for d in devices:
            d["related_device_ids"] = [other["id"] for other in devices if other["id"] != d["id"]
                                       and d["building_id"] is not None and other["building_id"] == d["building_id"]]
        incidents = []
        for i in raw_incidents:
            building_id = self.building_id(i["location_id"], locations)
            space = space_by_id.get(building_id)
            shift = {"inc-demo-offline": (.095, -.035), "inc-demo-fire": (-.09, .035)}.get(i["id"], (0, -.075))
            incidents.append({**i, "building_id": building_id, "device_ids": event_devices[i["id"]],
                              "anchor": self.offset_anchor(space.get("anchor") if space else None, *shift,
                                                           note="DEMO 风险位置，非现场定位"), "is_simulated": True})
        from .execution import ExecutionService
        execution = ExecutionService(self.db, self.catalog).overview()
        return {
            "campus_name": "浙江交通职业技术学院杭州校区", "mode": "DEMO", "updated_at": utc_now(),
            "images": catalog["images"], "spaces": spaces, "devices": devices, "incidents": incidents,
            "patrols": self.patrols(), "tasks": self.tasks(),
            "evidence_checks": self.evidence_checks(),
            "execution_tasks": execution["tasks"], "execution_resources": execution["resources"],
            "robot_task": dict(ROBOT_TASK),
            "satellite": {"status": "模拟任务待命", "coverage": "杭州校区演示范围（无真实遥感覆盖数据）",
                          "updated_at": None, "note": "未接入卫星遥感影像。校园规划效果图不代表遥感影像，影像更新时间待核实。"},
        }

    def tasks(self):
        return [{"source_selection": None, **json.loads(r["payload"])} for r in self.db.rows("SELECT payload FROM map_tasks ORDER BY created_at DESC,rowid DESC")]

    def evidence_checks(self):
        # Evidence checks are analysis runs, not Day 4 execution tasks.
        rows = self.db.rows("""SELECT id,incident_id,evidence_snapshot_id,status,created_at,
            COALESCE(finished_at,started_at,created_at) AS updated_at,error
            FROM agent_runs WHERE evidence_snapshot_id IS NOT NULL ORDER BY rowid DESC""")
        return sorted(rows, key=lambda row: timestamp(row["created_at"]), reverse=True)

    def task(self, task_id: str):
        row = self.db.row("SELECT payload FROM map_tasks WHERE id=?", (task_id,))
        if not row:
            raise HTTPException(404, "地图分析任务不存在")
        return {"source_selection": None, **json.loads(row["payload"])}

    def create_task(self, body: MapTaskCreate):
        snap = self.snapshot()
        spaces = {s["id"]: s for s in snap["spaces"]}
        devices = {d["id"]: d for d in snap["devices"]}
        incidents = {i["id"]: i for i in snap["incidents"]}
        if body.image_id not in {i["id"] for i in snap["images"]}:
            raise HTTPException(404, "地图素材不存在")
        if body.building_id and body.building_id not in spaces:
            raise HTTPException(404, "建筑不存在")
        if body.action in {"building", "patrol"} and not body.building_id:
            raise HTTPException(422, "请先选择目标建筑")
        if any(i not in devices for i in body.device_ids) or any(i not in incidents for i in body.incident_ids):
            raise HTTPException(404, "关联设备或事件不存在")
        if body.building_id:
            anchor = spaces[body.building_id].get("anchor")
            if anchor and anchor["image_id"] != body.image_id:
                raise HTTPException(422, "目标建筑不属于当前地图图片，请先切换片区")
            if any(devices[i]["building_id"] != body.building_id and devices[i]["type"] not in {"drone", "robot"} for i in body.device_ids):
                raise HTTPException(422, "设备与选定建筑不匹配")
            if any(incidents[i]["building_id"] != body.building_id for i in body.incident_ids):
                raise HTTPException(422, "事件与选定建筑不匹配")
        if body.device_ids and body.incident_ids and any(not set(incidents[i]["device_ids"]) & set(body.device_ids) for i in body.incident_ids):
            raise HTTPException(422, "选定事件与设备没有关联")
        selected_devices = list(devices.values())
        selected_incidents = list(incidents.values())
        if body.action != "campus":
            if body.building_id:
                selected_devices = [d for d in selected_devices if d["building_id"] == body.building_id]
                selected_incidents = [i for i in selected_incidents if i["building_id"] == body.building_id]
            if body.device_ids:
                selected_devices = [devices[i] for i in dict.fromkeys(body.device_ids)]
                selected_incidents = [i for i in selected_incidents if set(i["device_ids"]) & set(body.device_ids)]
            if body.incident_ids:
                selected_incidents = [incidents[i] for i in dict.fromkeys(body.incident_ids)]
                related = {d for i in selected_incidents for d in i["device_ids"]}
                if not body.device_ids:
                    selected_devices = [d for d in selected_devices if d["id"] in related]
        if body.source_selection:
            selection = body.source_selection
            objects = {"building": spaces, "device": devices, "incident": incidents}[selection.kind]
            selected_object = objects.get(selection.id)
            if selected_object is None:
                raise HTTPException(404, "来源选中对象不存在")
            selection_building = selection.id if selection.kind == "building" else selected_object["building_id"]
            if body.building_id and selection_building != body.building_id:
                raise HTTPException(422, "来源选中对象与任务建筑不匹配")
            if selection.kind == "device" and selection.id not in {d["id"] for d in selected_devices}:
                raise HTTPException(422, "来源设备不在当前任务范围内")
            if selection.kind == "incident" and selection.id not in {i["id"] for i in selected_incidents}:
                raise HTTPException(422, "来源事件不在当前任务范围内")
            if selection.kind == "building" and not body.building_id and body.action != "campus" and (body.device_ids or body.incident_ids):
                scope_buildings = {d["building_id"] for d in selected_devices} | {i["building_id"] for i in selected_incidents}
                if selection.id not in scope_buildings:
                    raise HTTPException(422, "来源建筑不在当前任务范围内")
            selection_anchor = selected_object.get("anchor")
            if selection_anchor and selection_anchor["image_id"] != body.image_id:
                raise HTTPException(422, "来源选中对象与当前地图图片不匹配")
        abnormal = [d for d in selected_devices if d["status"] in {"alarm", "offline", "unknown"}]
        titles = {"campus": "校园安全态势分析", "building": "建筑风险分析", "anomalies": "异常设备核查",
                  "patrol": "无人机巡检规划建议", "report": "区域安全报告摘要"}
        evidence = [f"统一数据快照：{len(selected_devices)} 台关联设备，{len(abnormal)} 台告警、离线或未知，{len(selected_incidents)} 项关联事件。"]
        for d in (abnormal if body.action == "anomalies" else selected_devices):
            metrics = "；".join(f"{m['label']} {m['value']}{m['unit']}" for m in d["metrics"])
            evidence.append(f"{d['code']} · {d['name']} · {d['status']} · {metrics or '无可用记录'}")
        evidence.extend(f"事件 {i['id']}：{i['title']} / {i['risk_level']} / {i['status']}" for i in selected_incidents)
        recommendations = ["先核对告警设备与离线设备的演示证据，再由授权人员依据正式预案复核。",
                           "空间名称、楼层与设备位置待核实项不能作为真实现场定位依据。"]
        if body.action == "patrol":
            recommendations = ["前往空天地协同视图，选择 DRONE-001 与目标建筑生成路线。", "确认 DEMO 巡检任务后才启动动画；本分析不会自动派发或控制设备。"]
        summary = f"DEMO 规则分析已完成：范围内 {len(selected_devices)} 台设备，发现 {len(abnormal)} 台告警、离线或未知设备。"
        if not selected_devices:
            summary = "DEMO 规则分析已完成：当前范围没有设备证据，无法判断安全状态。"
        task = {"id": new_id("maptask"), **body.model_dump(), "device_ids": [d["id"] for d in selected_devices],
                "incident_ids": [i["id"] for i in selected_incidents], "created_at": utc_now(), "status": "completed",
                "result": {"title": titles[body.action] + " · DEMO", "summary": summary, "evidence": evidence,
                           "recommendations": recommendations,
                           "limitations": ["使用同一数据库快照生成的确定性规则摘要，未调用大模型。", "所有设备、事件与巡检均为模拟；校园图片为规划效果图。", "本摘要不是正式安全报告、审批或真实处置指令。"]},
                "is_simulated": True}
        self.db.execute("INSERT INTO map_tasks VALUES (?,?,?)", (task["id"], dump(task), task["created_at"]))
        return task

    @staticmethod
    def advance(patrol):
        return advance_patrol(patrol)

    def patrols(self):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = []
            for row in conn.execute("SELECT * FROM patrol_missions ORDER BY created_at DESC,rowid DESC").fetchall():
                patrol = self.advance(json.loads(row["payload"]))
                if dump(patrol) != row["payload"]:
                    conn.execute("UPDATE patrol_missions SET payload=? WHERE id=?", (dump(patrol), patrol["id"]))
                result.append(patrol)
        return result

    def patrol(self, patrol_id: str):
        found = next((p for p in self.patrols() if p["id"] == patrol_id), None)
        if found is None:
            raise HTTPException(404, "巡检任务不存在")
        return found

    def create_patrol(self, body: PatrolCreate):
        snap = self.snapshot()
        device = next((d for d in snap["devices"] if d["id"] == body.device_id), None)
        target = next((s for s in snap["spaces"] if s["id"] == body.target_building_id), None)
        if not device or not target:
            raise HTTPException(404, "无人机或目标建筑不存在")
        if device["type"] != "drone" or device["status"] != "online":
            raise HTTPException(422, "请选择在线的 DEMO 无人机")
        if not target.get("anchor"):
            raise HTTPException(422, "目标位置尚未核实，不能在地图上生成巡检路线")
        anchor = target["anchor"]
        start = device["anchor"] if device["anchor"] and device["anchor"]["image_id"] == anchor["image_id"] else self.offset_anchor(anchor, -.12, .12)
        route = inspection_route(anchor, start)
        patrol = {"id": new_id("patrol"), "device_id": device["id"], "target_building_id": target["id"],
                  "image_id": anchor["image_id"], "route": route, "status": "draft", "progress": 0,
                  "created_at": utc_now(), "started_at": None, "duration_seconds": 12, "result": None,
                  "is_simulated": True}
        self.db.execute("INSERT INTO patrol_missions VALUES (?,?,?)", (patrol["id"], dump(patrol), patrol["created_at"]))
        return patrol

    def confirm_patrol(self, patrol_id: str):
        snap = self.snapshot()
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM patrol_missions WHERE id=?", (patrol_id,)).fetchone()
            if not row:
                raise HTTPException(404, "巡检任务不存在")
            patrol = self.advance(json.loads(row[0]))
            if patrol["status"] != "draft":
                return patrol
            device = next((d for d in snap["devices"] if d["id"] == patrol["device_id"]), None)
            if not device or device["type"] != "drone" or device["status"] != "online":
                raise HTTPException(422, "无人机当前不可用")
            from .execution import ExecutionService
            ExecutionService(self.db, self.catalog).assert_device_available(conn, patrol["device_id"])
            for item in conn.execute("SELECT payload FROM patrol_missions").fetchall():
                other = self.advance(json.loads(item[0]))
                if other["id"] != patrol_id and other["device_id"] == patrol["device_id"] and other["status"] == "running":
                    raise HTTPException(409, "该无人机已有进行中的巡检，请等待完成")
            patrol.update(status="running", started_at=utc_now(), progress=0)
            conn.execute("UPDATE patrol_missions SET payload=? WHERE id=?", (dump(patrol), patrol_id))
            return patrol
