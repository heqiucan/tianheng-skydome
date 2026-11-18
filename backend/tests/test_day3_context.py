import hashlib
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.workflow import query_device_status, query_event_history, query_sensor_data


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as value:
        yield value


def capture(client, incident_id="inc-demo-001", **body):
    response = client.post(f"/api/v1/incidents/{incident_id}/evidence-snapshots", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def run_from_snapshot(client, snapshot):
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    response = client.post("/api/v1/runs", json={"conversation_id": conversation_id,
                           "incident_id": snapshot["incident"]["id"],
                           "evidence_snapshot_id": snapshot["snapshot_id"], "instruction": "核对事件证据，不把温度异常直接等同火灾"})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{response.json()['id']}").json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            assert run["status"] == "completed", run
            return run
        time.sleep(.01)
    pytest.fail("run did not complete")


def test_event_context_matches_map_associations_and_current_evidence(client):
    context = client.get("/api/v1/incidents/inc-demo-001/context").json()
    situation = client.get("/api/v1/situation").json()
    event = next(i for i in situation["incidents"] if i["id"] == "inc-demo-001")
    assert context["incident"]["device_ids"] == event["device_ids"]
    assert context["incident"]["source"]["kind"] == "demo_fixture"
    assert context["incident"]["building_id"] == "loc-training"
    assert context["source_context"]["image_id"] == "training-2026"
    assert all(o["observation_id"] == o["id"] and o["data_scope"] == "event_snapshot" for o in context["observations"])
    assert all(o["incident_id"] == "inc-demo-001" for o in context["observations"])
    for current in context["current_devices"]:
        on_map = next(d for d in situation["devices"] if d["id"] == current["id"])
        assert current["metrics"] == on_map["metrics"]
        assert current["status"] == on_map["status"]
        assert all(m["data_scope"] == "current_device_state" for m in current["metrics"])
    historical_camera = next(d for d in context["devices"] if d["code"] == "CAM-021")
    current_camera = next(d for d in context["current_devices"] if d["code"] == "CAM-021")
    assert historical_camera["status"] == "alarm"
    assert current_camera["status"] == "offline"


def test_situation_exposes_evidence_check_status_separately_from_map_tasks(client):
    assert client.get("/api/v1/situation").json()["evidence_checks"] == []
    snapshot = capture(client)
    run = run_from_snapshot(client, snapshot)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    client.app.state.workflow.create(conversation_id, "inc-demo-001", "旧版规则运行，不属于证据快照核查")
    situation = client.get("/api/v1/situation").json()
    assert situation["tasks"] == []
    assert situation["evidence_checks"] == [{
        "id": run["id"], "incident_id": "inc-demo-001", "evidence_snapshot_id": snapshot["snapshot_id"],
        "status": "completed", "created_at": run["created_at"], "updated_at": run["finished_at"], "error": None,
    }]


@pytest.mark.parametrize("incident_id,device_id", [("inc-demo-offline", "dev-camera-01"), ("inc-demo-fire", "dev-water-01")])
def test_event_tool_scope_does_not_include_unrelated_colocated_equipment(client, incident_id, device_id):
    context = client.get(f"/api/v1/incidents/{incident_id}/context").json()
    snapshot = capture(client, incident_id)
    assert context["incident"]["device_ids"] == [device_id]
    assert {o["device_id"] for o in context["observations"]} == {device_id}
    devices = query_device_status(client.app.state.db, incident_id, snapshot["snapshot_id"])
    assert [d["id"] for d in devices["devices"]] == [device_id]


def test_snapshot_tools_and_restart_preserve_original_values(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        snapshot = capture(client, source_view="overview", image_id="training-2026")
        original = {**snapshot}
        checksum = original.pop("checksum")
        assert checksum == hashlib.sha256(json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        db = client.app.state.db
        expected_sensors = [o for o in snapshot["observations"] if o["kind"] in {"temperature", "smoke_alarm", "water_pressure"}]
        db.execute("UPDATE observations SET value=12,quality='good' WHERE incident_id='inc-demo-001' AND kind='temperature'")
        db.execute("UPDATE incidents SET title='后续修改的标题',summary='新摘要' WHERE id='inc-demo-001'")
        db.execute("UPDATE incidents SET title='后续修改的历史标题' WHERE id='inc-demo-fire'")
        client.post("/api/v1/scenarios/temperature-only/trigger")
        for tool, field, expected in [(query_sensor_data, "observations", expected_sensors),
                                       (query_device_status, "devices", snapshot["devices"]),
                                       (query_event_history, "incidents", snapshot["history"])]:
            output = tool(db, "inc-demo-001", snapshot["snapshot_id"])
            assert output[field] == expected
            assert output["evidence_snapshot_id"] == snapshot["snapshot_id"]
            assert output["incident_id"] == "inc-demo-001"
        run = run_from_snapshot(client, snapshot)
        assert run["result"]["level"] == "high"
        assert run["evidence_snapshot_id"] == snapshot["snapshot_id"]
        assert run["result"]["evidence_snapshot_id"] == snapshot["snapshot_id"]
        source_ids = {o["id"] for o in snapshot["observations"]}
        assert all(e["source_id"] in source_ids for e in run["result"]["evidence"])
        tools = [e for e in db.events(run["id"]) if e["type"] == "tool_result"]
        assert len(tools) == 3
        assert all(e["data"]["evidence_snapshot_id"] == snapshot["snapshot_id"] for e in tools)
        assert tools[0]["data"]["observations"] == expected_sensors
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE evidence_snapshots SET payload='{}' WHERE id=?", (snapshot["snapshot_id"],))
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/api/v1/evidence-snapshots/{snapshot['snapshot_id']}").json() == snapshot
        assert client.get(f"/api/v1/runs/{run['id']}").json() == run


def test_temperature_only_is_explicit_independent_and_changes_current_not_history(client):
    old = client.app.state.db.observations("inc-demo-001")
    assert len(client.get("/api/v1/incidents").json()) == 3
    old_snapshot = capture(client)
    response = client.post("/api/v1/scenarios/temperature-only/trigger")
    assert response.status_code == 201
    incident = response.json()
    assert incident["event_type"] == "temperature_anomaly"
    assert incident["risk_level"] == "unassessed"
    assert client.app.state.db.observations("inc-demo-001") == old
    context = client.get(f"/api/v1/incidents/{incident['id']}/context").json()
    assert {d["code"] for d in context["devices"]} == {"TEMP-008", "SMOKE-012", "CAM-021"}
    for key, expected in [("TEMP-008", "alarm"), ("SMOKE-012", "online"), ("CAM-021", "online")]:
        assert next(d for d in context["devices"] if d["code"] == key)["status"] == expected
    new_snapshot = capture(client, incident["id"])
    new_run = run_from_snapshot(client, new_snapshot)
    old_run = run_from_snapshot(client, old_snapshot)
    assert new_run["result"]["level"] == "medium"
    assert old_run["result"]["level"] == "high"
    assert "单项异常" in new_run["result"]["title"]
    assert not any("火灾" in reason for reason in new_run["result"]["reasons"])
    current = client.get("/api/v1/situation").json()["devices"]
    temp = next(d for d in current if d["code"] == "TEMP-008")
    assert temp["metrics"][0]["value"] == 68.5
    assert next(d for d in current if d["code"] == "CAM-021")["status"] == "online"
    assert client.app.state.db.observations("inc-demo-001") == old


def test_snapshot_rejects_wrong_ids_context_and_client_fabricated_data(client):
    assert client.get("/api/v1/incidents/missing/context").status_code == 404
    assert client.get("/api/v1/evidence-snapshots/missing").status_code == 404
    assert client.post("/api/v1/incidents/missing/evidence-snapshots", json={}).status_code == 404
    assert client.post("/api/v1/incidents/inc-demo-001/evidence-snapshots", json={"image_id": "east-2023"}).status_code == 422
    assert client.post("/api/v1/incidents/inc-demo-001/evidence-snapshots", json={"image_id": "missing"}).status_code == 404
    assert client.post("/api/v1/incidents/inc-demo-001/evidence-snapshots", json={"source_view": "unrecognized"}).status_code == 422
    assert client.post("/api/v1/incidents/inc-demo-001/evidence-snapshots", json={"observations": []}).status_code == 422
    snapshot = capture(client)
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    body = {"conversation_id": conversation_id, "incident_id": "inc-demo-fire", "instruction": "验证关联",
            "evidence_snapshot_id": snapshot["snapshot_id"]}
    assert client.post("/api/v1/runs", json=body).status_code == 422
    assert client.post("/api/v1/runs", json={**body, "evidence_snapshot_id": "missing"}).status_code == 404
    assert not client.get("/api/v1/runs").json()


def test_mixed_timezones_and_equal_time_samples_use_absolute_time_then_insert_order(client):
    db = client.app.state.db
    db.execute("UPDATE observations SET observed_at='2026-11-15T09:00:00+08:00' WHERE device_id='dev-temp-01'")
    for observation_id, value, sample_time in [("obs-tz-1", 68.5, "2026-11-15T02:00:00+00:00"),
                                               ("obs-tz-0", 66, "2026-11-15T10:00:00+08:00")]:
        db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)",
                   (observation_id, "dev-temp-01", "inc-demo-001", "temperature", value, "°C", sample_time, "alarm", "时区测试DEMO"))
    context = client.get("/api/v1/incidents/inc-demo-001/context").json()
    situation = client.get("/api/v1/situation").json()
    for group in [context["devices"], context["current_devices"], situation["devices"]]:
        device = next(d for d in group if d["code"] == "TEMP-008")
        assert device["metrics"][0]["value"] == 66
        assert device["metrics"][0]["observation_id"] == "obs-tz-0"
        assert device["metrics"][0]["observed_at"] == "2026-11-15T10:00:00+08:00"
    db.execute("UPDATE incidents SET triggered_at='2026-11-15T09:30:00+08:00' WHERE id='inc-demo-001'")
    db.execute("UPDATE incidents SET triggered_at='2026-11-15T02:00:00+00:00' WHERE id='inc-demo-fire'")
    db.execute("UPDATE incidents SET triggered_at='2026-11-15T01:00:00+00:00' WHERE id='inc-demo-offline'")
    assert db.latest_incident_id() == "inc-demo-fire"
    assert [i["id"] for i in db.incidents()] == ["inc-demo-fire", "inc-demo-001", "inc-demo-offline"]
    samples = db.observations("inc-demo-001", "dev-temp-01")
    assert samples[-1]["id"] == "obs-tz-0"
    assert next(d for d in db.devices("inc-demo-001") if d["code"] == "TEMP-008")["last_seen"] == "2026-11-15T10:00:00+08:00"
    assert "inc-demo-fire" not in {i["id"] for i in query_event_history(db, "inc-demo-001")["incidents"]}
