"""Shared event evidence and immutable, server-created DEMO snapshots.

Current device state and event evidence intentionally have different scopes.
Neither scope is real telemetry. Tools read the saved payload when a run binds
a snapshot, so later observations cannot change that run's evidence.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from .database import Database, dump, new_id, utc_now
from .fixtures import DEVICE_CODES
from .rules import references_for, all_references


METRICS = {
    "temperature": ("温度", "°C"), "smoke_alarm": ("烟雾告警", ""),
    "camera_event": ("异常记录", ""), "water_pressure": ("消防水压", "MPa"),
    "connectivity": ("通信状态", ""), "battery": ("电量", "%"),
}


def timestamp(value):
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def ordered_observations(observations):
    # Database row order is the stable tie-break for equal sample timestamps.
    return sorted(observations, key=lambda row: timestamp(row["observed_at"]))


def latest_by_device(observations):
    result = {}
    for observation in ordered_observations(observations):
        result.setdefault(observation["device_id"], {})[observation["kind"]] = observation
    return result


def device_status(records):
    if not records:
        return "unknown"
    if any(o["quality"] == "offline" for o in records.values()):
        return "offline"
    if any(o["quality"] == "alarm" for o in records.values()):
        return "alarm"
    if any(o["quality"] != "good" for o in records.values()):
        return "unknown"
    return "online"


def metric(observation, scope):
    kind, value = observation["kind"], observation["value"]
    if kind == "connectivity" and value in (0, 1):
        value = "在线" if value else "离线"
    elif kind == "smoke_alarm" and value in (0, 1):
        value = "告警" if value else "未触发"
    return {"kind": kind, "label": METRICS.get(kind, (kind, ""))[0],
            "value": value, "unit": observation["unit"],
            "observation_id": observation["id"], "observed_at": observation["observed_at"],
            "incident_id": observation["incident_id"], "quality": observation["quality"],
            "data_scope": scope}


def associated_device_ids(incident, devices, observations):
    observed_ids = {o["device_id"] for o in observations if o["incident_id"] == incident["id"]}
    # Ancillary robot/drone health samples are not evidence of camera or fire
    # equipment failure merely because they were inserted with that scenario.
    required_type = {"device_offline": "camera", "fire_equipment": "water_pressure"}.get(incident["event_type"])
    return [d["id"] for d in devices if d["location_id"] == incident["location_id"]
            and d["id"] in observed_ids and (required_type is None or d["type"] == required_type)]


def evidence_devices(devices, observations, scope):
    latest = latest_by_device(observations)
    result = []
    for device in devices:
        records = latest.get(device["id"], {})
        result.append({"id": device["id"], "code": DEVICE_CODES.get(device["id"], device["id"]),
                       "name": device["name"], "type": device["type"], "location_id": device["location_id"],
                       "status": device_status(records),
                       "last_seen": max((o["observed_at"] for o in records.values()), key=timestamp, default=None),
                       "metrics": [metric(o, scope) for o in records.values()],
                       "references": references_for(device["type"]), "is_simulated": True})
    return result


class EvidenceService:
    def __init__(self, db: Database):
        self.db = db

    def _context(self, conn, incident_id, source_view="map", image_id=None, source_selection=None):
        def rows(query, args=()):
            return [dict(row) for row in conn.execute(query, args).fetchall()]

        incidents = rows("SELECT i.*,l.name AS location_name,c.code FROM incidents i JOIN locations l ON l.id=i.location_id LEFT JOIN incident_codes c ON c.incident_id=i.id ORDER BY i.rowid")
        incident = next((i for i in incidents if i["id"] == incident_id), None)
        if incident is None:
            raise HTTPException(404, "事件不存在")
        devices = rows("SELECT * FROM devices ORDER BY id")
        observations = ordered_observations(rows("SELECT * FROM observations ORDER BY rowid"))
        locations = {l["id"]: l for l in rows("SELECT * FROM locations")}
        building = locations.get(incident["location_id"])
        seen = set()
        while building and building["kind"] not in {"building", "area"}:
            if building["id"] in seen:
                building = None
                break
            seen.add(building["id"])
            building = locations.get(building["parent_id"])
        try:
            catalog = json.loads(Path(__file__).with_name("map_catalog.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(503, "校园素材目录尚未就绪") from None
        space = next((s for s in catalog["spaces"] if building and s["id"] == building["id"]), None)
        anchor = space.get("anchor") if space else None
        expected_image = anchor["image_id"] if anchor else None
        if image_id is not None and image_id not in {i["id"] for i in catalog["images"]}:
            raise HTTPException(404, "地图素材不存在")
        if image_id is not None and image_id != expected_image:
            raise HTTPException(422, "事件与地图图片不匹配；未定位区域请省略图片 ID")
        device_ids = associated_device_ids(incident, devices, observations)
        selection = source_selection or {"kind": "incident", "id": incident_id}
        if selection["kind"] == "incident" and selection["id"] != incident_id:
            raise HTTPException(422, "来源事件与当前证据事件不匹配")
        if selection["kind"] == "device":
            if selection["id"] not in {device["id"] for device in devices}:
                raise HTTPException(404, "来源设备不存在")
            if selection["id"] not in device_ids:
                raise HTTPException(422, "来源设备不属于当前事件的关联证据")
        related_devices = [d for d in devices if d["id"] in device_ids]
        event_observations = [o for o in observations if o["incident_id"] == incident_id and o["device_id"] in device_ids]
        history = [dict(i, is_simulated=bool(i["is_simulated"])) for i in incidents
                   if i["id"] != incident_id and i["location_id"] == incident["location_id"]
                   and timestamp(i["triggered_at"]) < timestamp(incident["triggered_at"])]
        history.sort(key=lambda i: timestamp(i["triggered_at"]), reverse=True)
        incident = {**incident, "is_simulated": bool(incident["is_simulated"]),
                    "source": {"kind": "demo_fixture" if incident["is_simulated"] else "unverified",
                               "label": "预置模拟场景" if incident["is_simulated"] else "来源待核实"},
                    "building_id": building["id"] if building else None,
                    "building_name": space["name"] if space else building["name"] if building else None,
                    "device_ids": device_ids}
        return {"incident": incident, "data_scope": "event_snapshot", "references": all_references(),
                "devices": evidence_devices(related_devices, event_observations, "event_snapshot"),
                "observations": [dict(o, observation_id=o["id"], data_scope="event_snapshot") for o in event_observations],
                "current_devices": evidence_devices(related_devices, observations, "current_device_state"),
                "history": history, "source_context": {"source_view": source_view, "image_id": expected_image,
                                                       "selection": selection},
                "is_simulated": True}

    def context(self, incident_id):
        with self.db.connection() as conn:
            conn.execute("BEGIN")
            return self._context(conn, incident_id)

    def create(self, incident_id, source_view="map", image_id=None, source_selection=None):
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = self._context(conn, incident_id, source_view, image_id, source_selection)
            result.update(snapshot_id=new_id("evidence"), captured_at=utc_now())
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            result["checksum"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            conn.execute("INSERT INTO evidence_snapshots(id,incident_id,payload,created_at) VALUES (?,?,?,?)",
                         (result["snapshot_id"], incident_id, dump(result), result["captured_at"]))
        return result

    def get(self, snapshot_id):
        row = self.db.row("SELECT payload FROM evidence_snapshots WHERE id=?", (snapshot_id,))
        if row is None:
            raise HTTPException(404, "证据快照不存在")
        return json.loads(row["payload"])

    def for_run(self, snapshot_id, incident_id):
        snapshot = self.get(snapshot_id)
        if snapshot["incident"]["id"] != incident_id:
            raise HTTPException(422, "证据快照与当前事件不匹配")
        return snapshot

    def device_context(self, device_id, incident_id=None):
        with self.db.connection() as conn:
            conn.execute("BEGIN")
            devices = [dict(row) for row in conn.execute("SELECT * FROM devices ORDER BY id")]
            device = next((item for item in devices if item["id"] == device_id), None)
            if not device:
                raise HTTPException(404, "设备不存在")
            observations = ordered_observations([dict(row) for row in conn.execute("SELECT * FROM observations ORDER BY rowid")])
            incidents = [dict(row) for row in conn.execute("SELECT i.*,l.name AS location_name,c.code FROM incidents i JOIN locations l ON l.id=i.location_id LEFT JOIN incident_codes c ON c.incident_id=i.id ORDER BY i.rowid DESC")]
            related = [dict(item, is_simulated=bool(item["is_simulated"])) for item in incidents
                       if device_id in associated_device_ids(item, devices, observations)]
            related.sort(key=lambda item: timestamp(item["triggered_at"]), reverse=True)
            if incident_id and incident_id not in {item["id"] for item in incidents}:
                raise HTTPException(404, "事件不存在")
            if incident_id and incident_id not in {item["id"] for item in related}:
                raise HTTPException(422, "设备与指定事件没有关联证据")
            selected = incident_id or (related[0]["id"] if len(related) == 1 else None)
            return {"device": evidence_devices([device], observations, "current_device_state")[0],
                    "related_incidents": related, "selected_incident_id": selected,
                    "recommended_evidence_snapshot_id": None,
                    "source_selection": {"kind": "device", "id": device_id},
                    "can_analyze": selected is not None,
                    "reason": None if selected else "请选择要核查的关联事件" if related else "该设备没有关联事件证据，无法发起事件研判"}


def tool_context(db, incident_id, evidence_snapshot_id=None):
    service = EvidenceService(db)
    context = service.for_run(evidence_snapshot_id, incident_id) if evidence_snapshot_id else service.context(incident_id)
    metadata = {"evidence_snapshot_id": evidence_snapshot_id, "incident_id": incident_id,
                "data_scope": "event_snapshot", "is_simulated": True}
    return context, metadata
