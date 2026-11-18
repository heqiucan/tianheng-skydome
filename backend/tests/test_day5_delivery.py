import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import dump
from app.main import create_app
from app.workflow import assess_risk


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as value:
        yield value


def prepare(client):
    response = client.post("/api/v1/demo-scenarios/evt-008/prepare", json={})
    assert response.status_code == 200, response.text
    return response.json()


def capture(client, incident_id, selection=None):
    response = client.post(f"/api/v1/incidents/{incident_id}/evidence-snapshots", json={"source_selection": selection} if selection else {})
    assert response.status_code == 201, response.text
    return response.json()


def run_check(client, snapshot):
    conversation = client.post("/api/v1/conversations", json={}).json()
    response = client.post("/api/v1/runs", json={"conversation_id": conversation["id"], "incident_id": snapshot["incident"]["id"],
                           "instruction": "基于事件证据分析升温趋势并核查同区域设备", "evidence_snapshot_id": snapshot["snapshot_id"]})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{response.json()['id']}").json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            assert run["status"] == "completed", run
            return run
        time.sleep(.01)
    pytest.fail("run did not complete")


def new_task(client, title="普通演示任务"):
    response = client.post("/api/v1/execution-tasks", json={"title": title, "incident_id": "inc-demo-001", "task_type": "aerial_inspection"})
    assert response.status_code == 201, response.text
    return response.json()


def test_prepare_is_explicit_idempotent_and_never_resets_existing_work(client):
    db = client.app.state.db
    old_incidents = db.incidents()
    old_observations = db.rows("SELECT * FROM observations ORDER BY rowid")
    assert client.get("/api/v1/demo-scenarios/evt-008").status_code == 404
    task = new_task(client)
    client.post(f"/api/v1/execution-tasks/{task['id']}/assign", json={"resource_id": "UAV-003"})
    client.post(f"/api/v1/execution-tasks/{task['id']}/start", json={})
    stored_task = db.row("SELECT payload FROM execution_tasks WHERE id=?", (task["id"],))
    state = prepare(client)
    assert state == {"incident_id": "inc-demo-evt-008", "incident_code": "EVT-008", "device_id": "dev-temp-01", "device_code": "TEMP-008",
                     "building_id": "loc-training", "resource_id": "UAV-003", "task_code": "TASK-008", "root_task_id": None, "is_simulated": True}
    first_records = db.observations(state["incident_id"])
    assert len(first_records) == 6
    assert [item["value"] for item in first_records if item["kind"] == "temperature"] == [30, 49, 68.5]
    assert prepare(client) == state
    assert client.get("/api/v1/demo-scenarios/evt-008").json() == state
    assert db.observations(state["incident_id"]) == first_records
    assert db.rows("SELECT * FROM observations WHERE incident_id<>? ORDER BY rowid", (state["incident_id"],)) == old_observations
    assert [item for item in db.incidents() if item["id"] != state["incident_id"]] == old_incidents
    assert db.row("SELECT payload FROM execution_tasks WHERE id=?", (task["id"],)) == stored_task
    assert client.post("/api/v1/demo-scenarios/evt-008/prepare", json={"reset": True}).status_code == 422
    context = client.get(f"/api/v1/incidents/{state['incident_id']}/context").json()
    assert context["incident"]["code"] == "EVT-008"
    assert set(context["incident"]["device_ids"]) == {"dev-temp-01", "dev-smoke-01", "dev-camera-01"}


def test_task008_is_real_reserved_and_replays_keep_unique_codes(client):
    for _ in range(6):
        new_task(client)
    state = prepare(client)
    run = run_check(client, capture(client, state["incident_id"]))
    response = client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]})
    assert response.status_code == 200, response.text
    root = response.json()
    assert root["code"] == "TASK-008" and root["incident_code"] == "EVT-008"
    assert len(client.get("/api/v1/execution-tasks").json()) == 7
    assert "TASK-007" not in {task["code"] for task in client.get("/api/v1/execution-tasks").json()}
    assert prepare(client)["root_task_id"] == root["id"]
    assert client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]}).json() == root
    second_run = run_check(client, capture(client, state["incident_id"]))
    other = client.post("/api/v1/execution-tasks/from-run", json={"run_id": second_run["id"]}).json()
    assert other["code"] == "TASK-009" and other["incident_id"] == root["incident_id"]
    client.post(f"/api/v1/execution-tasks/{root['id']}/cancel", json={})
    child = client.post(f"/api/v1/execution-tasks/{root['id']}/retry", json={}).json()
    assert child["code"] == "TASK-010" and child["parent_task_id"] == root["id"]
    assert prepare(client)["root_task_id"] == root["id"]


def test_ordinary_allocator_skips008_and_existing_conflict_is_explicit(client):
    tasks = [new_task(client) for _ in range(8)]
    assert [task["code"] for task in tasks][-2:] == ["TASK-007", "TASK-009"]
    # Simulate an unrelated pre-upgrade TASK-008; the application must not rewrite it.
    collision = tasks[-1]
    collision["code"] = "TASK-008"
    client.app.state.db.execute("UPDATE execution_tasks SET code=?,payload=? WHERE id=?", ("TASK-008", dump(collision), collision["id"]))
    scenario = prepare(client)
    run = run_check(client, capture(client, scenario["incident_id"]))
    response = client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]})
    assert response.status_code == 409 and "无关历史任务" in response.json()["detail"]
    assert client.get(f"/api/v1/execution-tasks/{collision['id']}").json() == collision


def test_references_and_device_source_use_same_evidence_chain(client):
    scenario = prepare(client)
    incident_id = scenario["incident_id"]
    map_state = client.get("/api/v1/situation").json()
    map_device = next(device for device in map_state["devices"] if device["id"] == "dev-temp-01")
    api_device = next(device for device in client.get(f"/api/v1/devices?incident_id={incident_id}").json() if device["id"] == "dev-temp-01")
    context = client.get(f"/api/v1/incidents/{incident_id}/context").json()
    context_device = next(device for device in context["devices"] if device["id"] == "dev-temp-01")
    assert map_device["references"] == api_device["references"] == context_device["references"]
    temp_rule = context_device["references"][0]
    assert temp_rule["warning_condition"] == {"operator": "gte", "value": 60}
    assert "不是设备规范" in temp_rule["source_label"]
    fire = next(device for device in map_state["devices"] if device["code"] == "FIRE-003")
    assert fire["references"][0]["normal_condition"] is None
    assert "未配置" in fire["references"][0]["reference_label"]
    assert next(incident for incident in map_state["incidents"] if incident["id"] == incident_id)["code"] == "EVT-008"
    selection = {"kind": "device", "id": "dev-temp-01"}
    device_context = client.get(f"/api/v1/devices/dev-temp-01/analysis-context?incident_id={incident_id}").json()
    assert device_context["source_selection"] == selection and device_context["can_analyze"]
    assert device_context["selected_incident_id"] == incident_id
    undecided = client.get("/api/v1/devices/dev-temp-01/analysis-context").json()
    assert not undecided["can_analyze"] and undecided["selected_incident_id"] is None
    assert client.get("/api/v1/devices/dev-temp-01/analysis-context?incident_id=inc-demo-offline").status_code == 422
    assert client.get("/api/v1/devices/missing/analysis-context").status_code == 404
    assert not client.get("/api/v1/devices/dev-drone-01/analysis-context").json()["can_analyze"]
    snapshot = capture(client, incident_id, selection)
    assert snapshot["source_context"]["selection"] == selection
    assert snapshot["incident"]["code"] == "EVT-008"
    for invalid, status in [({"kind": "device", "id": "dev-water-01"}, 422), ({"kind": "device", "id": "missing"}, 404),
                            ({"kind": "incident", "id": "inc-demo-offline"}, 422)]:
        assert client.post(f"/api/v1/incidents/{incident_id}/evidence-snapshots", json={"source_selection": invalid}).status_code == status
    assert client.get("/api/v1/situation").json()["tasks"] == []


def test_report_uses_saved_evidence_trends_and_survives_live_changes(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path)) as client:
        scenario = prepare(client)
        snapshot = capture(client, scenario["incident_id"], {"kind": "device", "id": "dev-temp-01"})
        # Live observations and current rule definitions must not replace the saved reference values.
        client.app.state.db.execute("UPDATE observations SET value=20 WHERE incident_id=? AND kind='temperature'", (scenario["incident_id"],))
        monkeypatch.setattr("app.rules.TEMPERATURE_THRESHOLD", 100)
        run = run_check(client, snapshot)
        result = run["result"]
        assert result["analysis_kind"] == "rule_based" and result["level"] == "medium"
        trend = result["temperature_trends"][0]
        assert trend["sample_count"] == 3 and trend["direction"] == "rising"
        assert trend["first_value"] == 30 and trend["latest_value"] == 68.5 and trend["delta"] == 38.5
        assert trend["duration_minutes"] == 6 and trend["slope_per_minute"] == pytest.approx(6.4167)
        assert len(trend["observation_ids"]) == 3
        kinds = {item["kind"]: item for item in result["regional_evidence"]}
        assert kinds["smoke_alarm"]["value"] == 0 and kinds["connectivity"]["value"] == 1
        assert "未执行视频识别" in kinds["camera_event"]["interpretation"]
        assert "温度异常不等于火灾" in result["risk_judgment"] and result["possible_causes"] and result["uncertainties"]
        response = client.get(f"/api/v1/runs/{run['id']}/assessment-report")
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["id"] == result["report_id"] and report["assessment"] == result
        assert report["references"] == snapshot["references"]
        assert report["observations"] == snapshot["observations"] and report["devices"] == snapshot["devices"]
        assert report["incident_code"] == "EVT-008"
        assert report["source_context"]["selection"] == {"kind": "device", "id": "dev-temp-01"}
        assert client.get(f"/api/v1/assessment-reports?device_id=dev-temp-01&incident_id={scenario['incident_id']}").json() == [report]
        assert client.get("/api/v1/assessment-reports?device_id=dev-water-01").json() == []
        with pytest.raises(sqlite3.IntegrityError):
            client.app.state.db.execute("UPDATE assessment_reports SET payload='{}' WHERE id=?", (report["id"],))
        client.app.state.db.execute("UPDATE incidents SET title='后来的修改' WHERE id=?", (scenario["incident_id"],))
        client.app.state.db.execute("UPDATE agent_runs SET result='{}' WHERE id=?", (run["id"],))
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/api/v1/assessment-reports/{report['id']}").json() == report
        assert client.get(f"/api/v1/runs/{run['id']}/assessment-report").json() == report


def test_report_absent_for_legacy_and_report_failure_rolls_back_completion(client):
    snapshot = capture(client, "inc-demo-001")
    run = run_check(client, snapshot)
    db = client.app.state.db
    db.execute("DELETE FROM assessment_reports WHERE run_id=?", (run["id"],))
    original = db.run(run["id"])
    assert client.get(f"/api/v1/runs/{run['id']}/assessment-report").status_code == 404
    assert db.run(run["id"]) == original
    db.execute("CREATE TRIGGER reject_report BEFORE INSERT ON assessment_reports BEGIN SELECT RAISE(ABORT,'test insertion failure'); END")
    chat = client.post("/api/v1/conversations", json={}).json()
    response = client.post("/api/v1/runs", json={"conversation_id": chat["id"], "incident_id": "inc-demo-001",
                           "instruction": "验证原子保存", "evidence_snapshot_id": snapshot["snapshot_id"]})
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        failed = db.run(response.json()["id"])
        if failed["status"] == "failed":
            break
        time.sleep(.01)
    assert failed["status"] == "failed" and failed["result"] is None
    assert client.get(f"/api/v1/runs/{failed['id']}/assessment-report").status_code == 404


def test_trends_handle_mixed_zones_same_instants_and_invalid_samples():
    observations = [
        {"id": "first", "device_id": "dev-temp-01", "kind": "temperature", "value": 30, "unit": "°C", "observed_at": "2026-11-15T12:00:00+08:00", "quality": "good"},
        {"id": "tie-old", "device_id": "dev-temp-01", "kind": "temperature", "value": 55, "unit": "°C", "observed_at": "2026-11-15T04:03:00+00:00", "quality": "good"},
        {"id": "tie-new", "device_id": "dev-temp-01", "kind": "temperature", "value": 49, "unit": "°C", "observed_at": "2026-11-15T12:03:00+08:00", "quality": "good"},
        {"id": "invalid", "device_id": "dev-temp-01", "kind": "temperature", "value": 90, "unit": "°C", "observed_at": "2026-11-15T04:04:00Z", "quality": "offline"},
    ]
    devices = {"devices": [{"id": "dev-temp-01", "type": "temperature", "status": "offline"}]}
    result = assess_risk({"observations": observations}, devices, {"incidents": []})
    trend = result["temperature_trends"][0]
    assert trend["observation_ids"] == ["first", "tie-new"] and trend["latest_value"] == 49
    assert trend["duration_minutes"] == 3 and trend["delta"] == 19
    assert result["level"] == "unknown"
    single = assess_risk({"observations": observations[:1]}, devices, {"incidents": []})["temperature_trends"][0]
    assert single["direction"] == "insufficient" and single["slope_per_minute"] is None


@pytest.mark.parametrize("quality,value", [("offline", 68.5), ("good", None), ("offline", None)])
def test_latest_invalid_same_instant_replaces_earlier_valid_trend_sample(quality, value):
    observations = [
        {"id": "first", "device_id": "dev-temp-01", "kind": "temperature", "value": 30, "unit": "°C", "observed_at": "2026-11-15T04:00:00Z", "quality": "good"},
        {"id": "old-same-time", "device_id": "dev-temp-01", "kind": "temperature", "value": 68.5, "unit": "°C", "observed_at": "2026-11-15T04:03:00+00:00", "quality": "alarm"},
        {"id": "latest-invalid", "device_id": "dev-temp-01", "kind": "temperature", "value": value, "unit": "°C", "observed_at": "2026-11-15T12:03:00+08:00", "quality": quality},
    ]
    result = assess_risk({"observations": observations}, {"devices": [{"id": "dev-temp-01", "type": "temperature", "status": "offline"}]}, {"incidents": []})
    trend = result["temperature_trends"][0]
    assert trend["sample_count"] == 1 and trend["observation_ids"] == ["first"]
    assert trend["direction"] == "insufficient" and trend["slope_per_minute"] is None
    assert trend["latest_value"] == 30 and trend["delta"] is None
    assert result["level"] == "unknown"
    assert result["regional_evidence"][0]["observation_id"] == "latest-invalid"


def test_fixed_scenario_and_first_task_creation_are_concurrently_idempotent(client):
    with ThreadPoolExecutor(max_workers=2) as pool:
        prepared = list(pool.map(lambda _: client.post("/api/v1/demo-scenarios/evt-008/prepare", json={}), range(2)))
    assert [response.status_code for response in prepared] == [200, 200]
    assert prepared[0].json() == prepared[1].json()
    scenario = prepared[0].json()
    assert len(client.app.state.db.observations(scenario["incident_id"])) == 6
    run = run_check(client, capture(client, scenario["incident_id"]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(lambda _: client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]}), range(2)))
    assert [response.status_code for response in created] == [200, 200]
    assert created[0].json() == created[1].json()
    assert created[0].json()["code"] == "TASK-008"
    tasks = client.get("/api/v1/execution-tasks").json()
    assert len(tasks) == 1 and tasks[0]["id"] == created[0].json()["id"]
