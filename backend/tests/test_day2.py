import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import Database, SCHEMA, dump
from app.fixtures import seed
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as value:
        yield value


def task_input(**overrides):
    return {"instruction": "分析当前校园安全态势", "action": "campus", "source_view": "overview",
            "image_id": "training-2026", "building_id": None, "device_ids": [], "incident_ids": [], **overrides}


def patrol_input(**overrides):
    return {"device_id": "dev-drone-01", "target_building_id": "loc-training", **overrides}


def set_started(client, mission, seconds_ago):
    mission["started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()
    client.app.state.db.execute("UPDATE patrol_missions SET payload=? WHERE id=?", (dump(mission), mission["id"]))


def test_day1_upgrade_preserves_observations_and_is_idempotent(tmp_path):
    db = Database(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    with db.connection() as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO metadata VALUES ('schema_version','1')")
    seed(db)
    old = db.observations("inc-demo-001")
    assert len(db.devices()) == 8
    db.initialize()
    snapshot = db.observations("inc-demo-001")
    assert snapshot == old
    assert len(db.devices()) == 9
    assert len(db.incidents()) == 3
    db.initialize()
    assert db.observations("inc-demo-001") == old
    assert len(db.incidents()) == 3
    assert db.row("SELECT parent_id FROM locations WHERE id='loc-training-2f'")["parent_id"] == "loc-training"


def test_global_snapshot_uses_current_readings_and_preserves_historical_scope(client):
    response = client.get("/api/v1/situation")
    assert response.status_code == 200, response.text
    snap = response.json()
    assert snap["mode"] == "DEMO"
    assert len(snap["devices"]) == 9
    assert len(snap["incidents"]) == 3
    assert {"TEMP-008", "SMOKE-012", "CAM-021", "FIRE-003", "DRONE-001", "ROBOT-001"} <= {d["code"] for d in snap["devices"]}
    assert all(d["is_simulated"] for d in snap["devices"])
    assert all(i["is_simulated"] for i in snap["incidents"])
    global_devices = {d["id"]: d for d in snap["devices"]}
    assert global_devices["dev-camera-01"]["status"] == "offline"
    assert global_devices["dev-water-01"]["status"] == "alarm"
    assert global_devices["dev-drone-01"]["status"] == "online"
    historical = {d["id"]: d for d in client.get("/api/v1/devices?incident_id=inc-demo-001").json()}
    assert historical["dev-water-01"]["status"] == "online"
    assert historical["dev-camera-01"]["status"] == "alarm"
    assert historical["dev-camera-01"]["code"] == global_devices["dev-camera-01"]["code"]
    assert client.get("/api/v1/overview").json()["device_count"] == len(snap["devices"])
    assert snap["satellite"]["updated_at"] is None
    assert all(s["anchor"] is None for s in snap["spaces"] if s["id"] == "loc-library")
    assert global_devices["dev-camera-02"]["anchor"] is None
    for obj in snap["devices"] + snap["incidents"] + snap["spaces"]:
        if obj["anchor"]:
            assert 0 <= obj["anchor"]["x"] <= 1 and 0 <= obj["anchor"]["y"] <= 1
            assert obj["anchor"]["image_id"] in {i["id"] for i in snap["images"]}


def test_global_values_follow_new_scenario_without_overwriting_history(client):
    incident = client.post("/api/v1/scenarios/fire/trigger").json()
    db = client.app.state.db
    db.execute("UPDATE observations SET value=24,quality='good' WHERE incident_id=? AND device_id='dev-temp-01'", (incident["id"],))
    snap = client.get("/api/v1/situation").json()
    device = next(d for d in snap["devices"] if d["id"] == "dev-temp-01")
    assert device["metrics"][0]["value"] == 24
    assert device["status"] == "online"
    assert max(o["value"] for o in db.observations("inc-demo-001", "dev-temp-01")) == 78


def test_robot_standby_task_is_explicit_demo_and_links_snapshot_device(client):
    snapshot = client.get("/api/v1/situation").json()
    task = snapshot["robot_task"]
    device = next(d for d in snapshot["devices"] if d["id"] == task["device_id"])
    assert device["type"] == "robot" and device["code"] == "ROBOT-001"
    assert task["target_building_id"] in {s["id"] for s in snapshot["spaces"]}
    assert task["status"] == "standby" and task["progress"] == 0 and task["is_simulated"] is True
    assert "DEMO" in task["name"]


def test_task_context_and_snapshot_result_survive_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/api/v1/situation/tasks", json=task_input(action="building", building_id="loc-training", source_view="map"))
        assert response.status_code == 201, response.text
        task = response.json()
        assert task["status"] == "completed" and task["is_simulated"]
        assert task["building_id"] == "loc-training"
        assert "dev-temp-01" in task["device_ids"]
        assert "dev-smoke-02" not in task["device_ids"]
        assert len(task["incident_ids"]) == 3
        assert any("未调用大模型" in item for item in task["result"]["limitations"])
        assert any("78" in item for item in task["result"]["evidence"])
        client.app.state.db.execute("UPDATE observations SET value=22 WHERE device_id='dev-temp-01'")
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/api/v1/situation/tasks/{task['id']}").json() == task
        assert client.get("/api/v1/situation").json()["tasks"][0] == task


def test_task_empty_scope_is_unknown_and_all_actions_are_supported(client):
    empty = client.post("/api/v1/situation/tasks", json=task_input(action="building", building_id="loc-canopy")).json()
    assert empty["device_ids"] == [] and empty["incident_ids"] == []
    assert "无法判断安全状态" in empty["result"]["summary"]
    for action in ["campus", "anomalies", "report", "patrol"]:
        response = client.post("/api/v1/situation/tasks", json=task_input(action=action, building_id="loc-training" if action == "patrol" else None))
        assert response.status_code == 201, response.text
    scoped = client.post("/api/v1/situation/tasks", json=task_input(action="anomalies", device_ids=["dev-camera-01"], incident_ids=["inc-demo-offline"])).json()
    assert scoped["device_ids"] == ["dev-camera-01"]
    assert scoped["incident_ids"] == ["inc-demo-offline"]
    assert any("offline" in e for e in scoped["result"]["evidence"])


def test_task_source_selection_is_persisted_without_becoming_first_incident(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        for selection in [{"kind": "building", "id": "loc-training"},
                          {"kind": "incident", "id": "inc-demo-001"},
                          {"kind": "device", "id": "dev-temp-01"}]:
            response = client.post("/api/v1/situation/tasks", json=task_input(
                action="building", building_id="loc-training", source_selection=selection))
            assert response.status_code == 201, response.text
            task = response.json()
            assert task["source_selection"] == selection
            assert task["incident_ids"]
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/api/v1/situation/tasks/{task['id']}").json()["source_selection"] == {"kind": "device", "id": "dev-temp-01"}
        assert client.get("/api/v1/situation").json()["tasks"][0]["source_selection"] == task["source_selection"]
        assert client.post("/api/v1/situation/tasks", json=task_input()).json()["source_selection"] is None


def test_task_source_selection_rejects_unknown_wrong_building_and_outside_scope(client):
    cases = [
        ({"source_selection": {"kind": "device", "id": "missing"}}, 404),
        ({"source_selection": {"kind": "device", "id": "dev-smoke-02"}}, 422),
        ({"source_selection": {"kind": "building", "id": "loc-dorm"}}, 422),
        ({"source_selection": {"kind": "device", "id": "dev-smoke-01"}, "device_ids": ["dev-temp-01"]}, 422),
        ({"source_selection": {"kind": "incident", "id": "inc-demo-offline"}, "incident_ids": ["inc-demo-001"]}, 422),
    ]
    for change, status in cases:
        response = client.post("/api/v1/situation/tasks", json=task_input(action="building", building_id="loc-training", **change))
        assert response.status_code == status, response.text


@pytest.mark.parametrize("change,status", [
    ({"instruction": "  "}, 422), ({"image_id": "unknown"}, 404),
    ({"building_id": "unknown"}, 404), ({"device_ids": ["unknown"]}, 404),
    ({"incident_ids": ["unknown"]}, 404), ({"action": "building"}, 422),
    ({"building_id": "loc-dorm", "device_ids": ["dev-temp-01"]}, 422),
    ({"building_id": "loc-library", "incident_ids": ["inc-demo-001"]}, 422),
    ({"device_ids": ["dev-water-01"], "incident_ids": ["inc-demo-offline"]}, 422),
    ({"action": "building", "building_id": "loc-dorm", "image_id": "training-2026"}, 422),
])
def test_task_rejects_invalid_context(client, change, status):
    assert client.post("/api/v1/situation/tasks", json=task_input(**change)).status_code == status


def test_patrol_confirm_progress_completion_repeat_and_refresh(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/api/v1/situation/patrols", json=patrol_input())
        assert response.status_code == 201, response.text
        draft = response.json()
        assert draft["status"] == "draft" and draft["started_at"] is None and draft["progress"] == 0
        mission = client.post(f"/api/v1/situation/patrols/{draft['id']}/confirm", json={}).json()
        assert mission["status"] == "running"
        repeated = client.post(f"/api/v1/situation/patrols/{draft['id']}/confirm", json={}).json()
        assert repeated["started_at"] == mission["started_at"]
        second = client.post("/api/v1/situation/patrols", json=patrol_input()).json()
        assert client.post(f"/api/v1/situation/patrols/{second['id']}/confirm", json={}).status_code == 409
        set_started(client, mission, 6)
        half = client.get(f"/api/v1/situation/patrols/{draft['id']}").json()
        assert 45 <= half["progress"] < 75
    with TestClient(create_app(tmp_path)) as client:
        refreshed = client.get(f"/api/v1/situation/patrols/{draft['id']}").json()
        assert refreshed["status"] == "running" and refreshed["progress"] >= half["progress"]
        set_started(client, mission, 13)
        completed = client.get(f"/api/v1/situation/patrols/{draft['id']}").json()
        assert completed["status"] == "completed" and completed["progress"] == 100
        assert "未采集真实" in completed["result"]
        assert client.get(f"/api/v1/situation/patrols/{draft['id']}").json() == completed
        assert client.post(f"/api/v1/situation/patrols/{second['id']}/confirm", json={}).json()["status"] == "running"
        assert len(client.get("/api/v1/situation").json()["patrols"]) == 2


def test_patrol_validates_devices_targets_and_image_coordinates(client):
    assert client.post("/api/v1/situation/patrols", json=patrol_input(device_id="dev-robot-01")).status_code == 422
    assert client.post("/api/v1/situation/patrols", json=patrol_input(target_building_id="loc-library")).status_code == 422
    assert client.post("/api/v1/situation/patrols", json=patrol_input(device_id="missing")).status_code == 404
    assert client.post("/api/v1/situation/patrols/missing/confirm", json={}).status_code == 404
    east = client.post("/api/v1/situation/patrols", json=patrol_input(target_building_id="loc-dorm")).json()
    assert east["image_id"] == "east-2023"
    assert len(east["route"]) >= 4
    assert all(0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in east["route"])
    client.app.state.db.execute("UPDATE observations SET quality='offline' WHERE device_id='dev-drone-01' AND kind='connectivity'")
    assert client.post(f"/api/v1/situation/patrols/{east['id']}/confirm", json={}).status_code == 422


def test_missing_catalog_fails_honestly_without_fake_map(client, tmp_path):
    client.app.state.situation.catalog_path = tmp_path / "absent.json"
    response = client.get("/api/v1/situation")
    assert response.status_code == 503
    assert "虚构校园" in response.json()["detail"]
