"""Explicit, idempotent preparation of the fixed presentation scenario."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .database import new_id
from .rules import TEMPERATURE_THRESHOLD

INCIDENT_ID = "inc-demo-evt-008"
INCIDENT_CODE = "EVT-008"
TASK_CODE = "TASK-008"


def scenario_state(conn):
    row = conn.execute("SELECT incident_id FROM incident_codes WHERE code=?", (INCIDENT_CODE,)).fetchone()
    if row is None:
        raise HTTPException(404, "固定演示场景尚未准备")
    root = conn.execute("SELECT id FROM execution_tasks WHERE code=? AND incident_id=? AND source_run_id IS NOT NULL AND task_type='aerial_inspection'", (TASK_CODE, row[0])).fetchone()
    return {"incident_id": row[0], "incident_code": INCIDENT_CODE, "device_id": "dev-temp-01", "device_code": "TEMP-008",
            "building_id": "loc-training", "resource_id": "UAV-003", "task_code": TASK_CODE,
            "root_task_id": root[0] if root else None, "is_simulated": True}


def get_scenario(db):
    with db.connection() as conn:
        return scenario_state(conn)


def prepare_scenario(db):
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM incident_codes WHERE code=?", (INCIDENT_CODE,)).fetchone():
            return scenario_state(conn)
        if conn.execute("SELECT 1 FROM incidents WHERE id=?", (INCIDENT_ID,)).fetchone():
            raise HTTPException(409, "固定事件 ID 已存在但没有演示编号关联，请核查数据，系统不会覆盖历史")
        now = datetime.now(timezone.utc)
        stamp = now.isoformat(timespec="milliseconds")
        conn.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?)", (
            INCIDENT_ID, "实训基地温度异常", "loc-training-2f", "temperature_anomaly", "open", "unassessed",
            "模拟温度升至68.5℃；烟雾未触发、摄像机在线。温度异常不等于火灾，等待证据核查。", stamp, 1))
        conn.execute("INSERT INTO incident_codes VALUES (?,?)", (INCIDENT_ID, INCIDENT_CODE))
        records = [(new_id("obs"), "dev-temp-01", INCIDENT_ID, "temperature", value, "°C",
                    (now - timedelta(minutes=minutes)).isoformat(timespec="milliseconds"),
                    "alarm" if value >= TEMPERATURE_THRESHOLD else "good", "固定演示场景的模拟温度记录")
                   for minutes, value in [(6, 30), (3, 49), (0, 68.5)]]
        for device, kind, value, text in [("dev-smoke-01", "smoke_alarm", 0, "模拟烟雾未触发"),
                                         ("dev-camera-01", "connectivity", 1, "模拟摄像机在线"),
                                         ("dev-camera-01", "camera_event", 0, "无模拟视频异常记录，未进行真实视频识别")]:
            records.append((new_id("obs"), device, INCIDENT_ID, kind, value, "", stamp, "good", text))
        conn.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)", records)
        return scenario_state(conn)
