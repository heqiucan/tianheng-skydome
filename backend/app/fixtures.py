"""Fictional campus fixtures; no external telemetry or real persons."""
from datetime import datetime, timedelta, timezone

from .database import Database, dump, new_id, utc_now
from .rules import TEMPERATURE_THRESHOLD


LOCATIONS = [
    ("loc-campus", "天穹示范校园", None, "campus", 50, 50),
    ("loc-training-2f", "实训楼二层", "loc-campus", "floor", 46, 55),
    ("loc-library", "图书馆", "loc-campus", "building", 23, 28),
    ("loc-dorm", "学生公寓", "loc-campus", "building", 76, 32),
]
DEVICES = [
    ("dev-temp-01", "实训楼温度传感器", "temperature", "loc-training-2f"),
    ("dev-smoke-01", "实训楼烟雾传感器", "smoke", "loc-training-2f"),
    ("dev-camera-01", "实训楼走廊摄像机", "camera", "loc-training-2f"),
    ("dev-water-01", "实训楼消防水压监测", "water_pressure", "loc-training-2f"),
    ("dev-robot-01", "校园巡检机器人", "robot", "loc-training-2f"),
    ("dev-camera-02", "图书馆入口摄像机", "camera", "loc-library"),
    ("dev-temp-02", "图书馆温度传感器", "temperature", "loc-library"),
    ("dev-smoke-02", "学生公寓烟雾传感器", "smoke", "loc-dorm"),
]
DEVICE_CODES = {
    "dev-temp-01": "TEMP-008", "dev-smoke-01": "SMOKE-012",
    "dev-camera-01": "CAM-021", "dev-water-01": "FIRE-003",
    "dev-drone-01": "DRONE-001", "dev-robot-01": "ROBOT-001",
    "dev-camera-02": "CAM-022", "dev-temp-02": "TEMP-009",
    "dev-smoke-02": "SMOKE-013",
}
ROBOT_TASK = {
    "id": "robot-task-demo-001", "name": "实训基地周边地面巡检（DEMO 待命任务）",
    "device_id": "dev-robot-01", "target_building_id": "loc-training",
    "status": "standby", "progress": 0, "is_simulated": True,
}
KNOWLEDGE = [
    ("kb-fire-01", "校园疑似火情核查流程", "演示版 1.0", "消防预案", ["火情", "烟雾", "温度", "实训楼"],
     "【演示资料，不是经审定的应急预案】\n适用：监测系统出现疑似火情记录。\n1. 记录告警地点、采样时间和设备来源，区分传感器告警与现场确认。\n2. 由授权值班人员依校方正式预案复核，记录缺失信息。\n3. 汇总可用资源，拟定处置任务，等待人工确认。\n4. 任务执行仅在本系统模拟，现场行动应遵循已批准的正式预案。"),
    ("kb-device-01", "监测设备异常核验记录规范", "演示版 1.0", "设备维护", ["离线", "设备", "传感器", "质量"],
     "【演示资料】\n设备离线不代表现场正常。核验最近通信时间、数据质量与关联设备。缺失或过期读数应标记为未知。演示系统只记录核验建议，不会控制真实硬件。"),
    ("kb-report-01", "事件复盘与报告字段规范", "演示版 1.0", "事件复盘", ["报告", "复盘", "证据", "任务"],
     "【演示资料】\n报告应包含事件基本信息、监测证据、规则版本、不确定项、方案版本、审批记录和任务完成情况。未完成任务必须保留状态，不能因报告生成而标记为完成。"),
]
RESOURCES = [
    ("res-duty", "值班核查组", "现场信息复核", "校园值班室", "available"),
    ("res-security", "校园安保组", "秩序协同", "校园门岗", "available"),
    ("res-maintenance", "设施保障组", "设备核验", "设备管理室", "available"),
    ("res-robot", "巡检机器人 R-01", "模拟巡检", "实训楼一层", "offline"),
]


def _insert_scenario(conn, incident_id: str, now: datetime):
    timestamp = now.isoformat(timespec="milliseconds")
    conn.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?)", (
        incident_id, "实训楼二层疑似火情", "loc-training-2f", "suspected_fire", "open", "unassessed",
        "模拟温度异常与烟雾告警，等待数据核查；尚未确认现场火情。", timestamp, 1))
    records = []
    for minutes, temperature in [(15, 26), (12, 27), (9, 31), (6, 42), (3, 61), (0, 78)]:
        observed = (now - timedelta(minutes=minutes)).isoformat(timespec="milliseconds")
        quality = "alarm" if temperature >= TEMPERATURE_THRESHOLD else "good"
        records.append((new_id("obs"), "dev-temp-01", incident_id, "temperature", temperature, "°C", observed, quality, "预置模拟温度记录"))
    for device_id, kind, value, unit, quality, description in [
        ("dev-smoke-01", "smoke_alarm", 1, "", "alarm", "预置模拟烟雾告警"),
        ("dev-camera-01", "camera_event", 1, "", "alarm", "模拟异常事件记录，未进行视频识别或现场确认"),
        ("dev-water-01", "water_pressure", 0.35, "MPa", "good", "预置模拟消防水压记录"),
        ("dev-robot-01", "connectivity", 0, "", "offline", "模拟设备离线"),
        ("dev-camera-02", "connectivity", 1, "", "good", "模拟在线状态"),
        ("dev-temp-02", "temperature", 25, "°C", "good", "预置模拟温度记录"),
        ("dev-smoke-02", "smoke_alarm", 0, "", "good", "预置模拟无告警状态"),
    ]:
        records.append((new_id("obs"), device_id, incident_id, kind, value, unit, timestamp, quality, description))
    conn.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)", records)


def seed(db: Database):
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT value FROM metadata WHERE key='fixtures_version'").fetchone():
            return
        conn.executemany("INSERT INTO locations VALUES (?,?,?,?,?,?)", LOCATIONS)
        conn.executemany("INSERT INTO devices VALUES (?,?,?,?)", DEVICES)
        conn.executemany("INSERT INTO knowledge_documents VALUES (?,?,?,?,?,?,?)", [
            (row[0], row[1], row[2], row[3], dump(row[4]), row[5], 1) for row in KNOWLEDGE])
        conn.executemany("INSERT INTO resources VALUES (?,?,?,?,?)", RESOURCES)
        _insert_scenario(conn, "inc-demo-001", datetime.now(timezone.utc))
        conn.execute("INSERT INTO metadata VALUES ('fixtures_version','1')")


def trigger_scenario(db: Database) -> dict:
    incident_id = new_id("inc")
    with db.connection() as conn:
        _insert_scenario(conn, incident_id, datetime.now(timezone.utc))
    return db.incident(incident_id)


def trigger_temperature_only(db: Database) -> dict:
    """Explicit comparison scenario. Never seed or overwrite prior evidence."""
    incident_id, now = new_id("inc-temp"), datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="milliseconds")
    with db.connection() as conn:
        conn.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?)", (
            incident_id, "实训基地单项温度异常（对照场景）", "loc-training-2f", "temperature_anomaly",
            "open", "unassessed", "DEMO：温度68.5℃、烟雾未触发、摄像机在线；温度异常不等于火灾。", stamp, 1))
        records = [(new_id("obs"), "dev-temp-01", incident_id, "temperature", value, "°C",
                    (now-timedelta(minutes=minutes)).isoformat(timespec="milliseconds"),
                    "alarm" if value >= TEMPERATURE_THRESHOLD else "good", "DEMO 单项温度异常对照记录")
                   for minutes, value in [(6, 30), (3, 49), (0, 68.5)]]
        for device_id, kind, value, description in [
            ("dev-smoke-01", "smoke_alarm", 0, "DEMO 烟雾未触发"),
            ("dev-camera-01", "connectivity", 1, "DEMO 摄像机在线"),
            ("dev-camera-01", "camera_event", 0, "DEMO 无摄像机异常记录；未进行视频识别"),
        ]:
            records.append((new_id("obs"), device_id, incident_id, kind, value, "", stamp, "good", description))
        conn.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)", records)
    return db.incident(incident_id)


def seed_day2(db: Database):
    """Add the second milestone without deleting Day 1 snapshots or user history."""
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT value FROM metadata WHERE key='day2_fixtures_version'").fetchone():
            return
        conn.execute("INSERT OR IGNORE INTO locations VALUES (?,?,?,?,?,?)", (
            "loc-training", "物流与航空实训基地", "loc-campus", "building", 0, 0))
        conn.execute("INSERT OR IGNORE INTO locations VALUES (?,?,?,?,?,?)", (
            "loc-canopy", "运动场及雨棚", "loc-campus", "area", 0, 0))
        conn.execute("UPDATE locations SET name='浙江交通职业技术学院杭州校区' WHERE id='loc-campus'")
        conn.execute("UPDATE locations SET name='实训基地二层（DEMO 楼层）',parent_id='loc-training' WHERE id='loc-training-2f'")
        conn.execute("UPDATE locations SET name='教学建筑（名称与位置待核实）' WHERE id='loc-library'")
        conn.execute("UPDATE locations SET name='高层学生公寓（规划）' WHERE id='loc-dorm'")
        conn.execute("INSERT OR IGNORE INTO devices VALUES (?,?,?,?)", (
            "dev-drone-01", "模拟巡检无人机", "drone", "loc-campus"))
        # New observations are separate event snapshots. Existing evidence stays intact.
        now = datetime.now(timezone.utc)
        original = conn.execute("SELECT triggered_at FROM incidents WHERE id='inc-demo-001'").fetchone()
        base = datetime.fromisoformat(original[0]) if original else now
        for incident_id, title, kind, risk, summary, age in [
            ("inc-demo-offline", "实验空间设备离线", "device_offline", "medium", "DEMO：CAM-021 通信中断；真实实验空间与楼层待核实。", 2),
            ("inc-demo-fire", "校园区域消防设备异常", "fire_equipment", "high", "DEMO：FIRE-003 水压记录异常，需要人工核验。", 1),
        ]:
            conn.execute("INSERT OR IGNORE INTO incidents VALUES (?,?,?,?,?,?,?,?,?)", (
                incident_id, title, "loc-training-2f", kind, "open", risk, summary,
                (base - timedelta(seconds=age)).isoformat(timespec="milliseconds"), 1))
        conn.execute("UPDATE incidents SET title='实训基地温度异常' WHERE id='inc-demo-001'")
        records = []
        for device_id, incident_id, kind, values, unit, quality, description in [
            ("dev-camera-01", "inc-demo-offline", "connectivity", [1, 1, 1, 0, 0, 0], "", "offline", "DEMO 视频监控通信状态"),
            ("dev-water-01", "inc-demo-fire", "water_pressure", [.35, .31, .26, .18, .12, .08], "MPa", "alarm", "DEMO 消防设备水压记录"),
            ("dev-robot-01", "inc-demo-offline", "connectivity", [1], "", "good", "DEMO 地面机器人在线状态"),
            ("dev-robot-01", "inc-demo-offline", "battery", [76], "%", "good", "DEMO 地面机器人电量"),
            ("dev-drone-01", "inc-demo-offline", "connectivity", [1], "", "good", "DEMO 无人机在线状态"),
            ("dev-drone-01", "inc-demo-offline", "battery", [86], "%", "good", "DEMO 无人机电量"),
        ]:
            for index, value in enumerate(values):
                timestamp = (now - timedelta(minutes=(len(values) - 1 - index) * 3)).isoformat(timespec="milliseconds")
                records.append((new_id("obs"), device_id, incident_id, kind, value, unit, timestamp,
                                quality if index == len(values) - 1 else "good", description))
        conn.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)", records)
        conn.execute("INSERT INTO metadata VALUES ('day2_fixtures_version','1')")
        conn.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
