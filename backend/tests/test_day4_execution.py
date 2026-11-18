import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.database import dump, new_id


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as value:
        yield value


@pytest.fixture
def clock(monkeypatch):
    state = {"at": datetime.now(timezone.utc)}
    monkeypatch.setattr("app.execution.utc_now", lambda: state["at"].isoformat(timespec="milliseconds"))
    def advance(seconds):
        state["at"] += timedelta(seconds=seconds)
    return advance


def create(client, **overrides):
    response = client.post("/api/v1/execution-tasks", json={"title": "实训基地异常复核", "incident_id": "inc-demo-001",
                           "task_type": "aerial_inspection", "priority": "high", **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def action(client, task, operation, **body):
    return client.post(f"/api/v1/execution-tasks/{task['id']}/{operation}", json=body)


def assign_start(client, task, resource="UAV-003"):
    response = action(client, task, "assign", resource_id=resource)
    assert response.status_code == 200, response.text
    response = action(client, task, "start")
    assert response.status_code == 200, response.text
    return response.json()


def read(client, task):
    response = client.get(f"/api/v1/execution-tasks/{task['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def complete_rule_run(client, incident_id="inc-demo-001"):
    snapshot = client.post(f"/api/v1/incidents/{incident_id}/evidence-snapshots", json={}).json()
    conversation = client.post("/api/v1/conversations", json={}).json()
    response = client.post("/api/v1/runs", json={"conversation_id": conversation["id"], "incident_id": incident_id,
                           "instruction": "核查关联证据", "evidence_snapshot_id": snapshot["snapshot_id"]})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{response.json()['id']}").json()
        if run["status"] == "completed":
            return run, snapshot
        time.sleep(.01)
    pytest.fail("Rule run did not complete")


def test_from_run_idempotence_and_frozen_provenance(client, clock):
    run, snapshot = complete_rule_run(client)
    # Mutating live context before creation must not change the captured evidence.
    db = client.app.state.db
    db.execute("UPDATE incidents SET title='新事件标题',risk_level='low' WHERE id=?", (run["incident_id"],))
    db.execute("UPDATE observations SET value=17 WHERE device_id='dev-temp-01'")
    response = client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]})
    assert response.status_code == 200, response.text
    task = response.json()
    assert task["incident_title"] == snapshot["incident"]["title"]
    assert task["device_ids"] == snapshot["incident"]["device_ids"]
    assert task["source_kind"] == "rule_assessment" and "非大模型" in task["source_label"]
    assert task["priority"] == run["result"]["level"] == "high"
    assert task["evidence_snapshot_id"] == snapshot["snapshot_id"]
    original_source = db.row("SELECT payload FROM execution_task_sources WHERE task_id=?", (task["id"],))["payload"]
    db.execute("UPDATE agent_runs SET result=? WHERE id=?", (dump({"level": "low"}), run["id"]))
    repeated = client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]}).json()
    assert repeated == task
    assert len(client.get(f"/api/v1/execution-tasks?run_id={run['id']}").json()) == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE execution_task_sources SET payload='{}' WHERE task_id=?", (task["id"],))
    assert db.row("SELECT payload FROM execution_task_sources WHERE task_id=?", (task["id"],))["payload"] == original_source
    assign_start(client, task)
    clock(28)
    report = client.get(f"/api/v1/execution-tasks/{task['id']}/report").json()
    assert report["source_run_id"] == run["id"] and report["evidence_snapshot_id"] == snapshot["snapshot_id"]
    assert "新事件标题" not in dump(report)
    assert "确定性规则初评：high" in dump(report)


def test_from_run_requires_complete_snapshot_and_valid_ids(client):
    assert client.post("/api/v1/execution-tasks/from-run", json={"run_id": "missing"}).status_code == 404
    run, _ = complete_rule_run(client)
    client.app.state.db.execute("UPDATE agent_runs SET status='failed' WHERE id=?", (run["id"],))
    assert client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]}).status_code == 409
    client.app.state.db.execute("UPDATE agent_runs SET status='completed',evidence_snapshot_id=NULL WHERE id=?", (run["id"],))
    assert client.post("/api/v1/execution-tasks/from-run", json={"run_id": run["id"]}).status_code == 409
    assert client.post("/api/v1/execution-tasks", json={"title": "  ", "incident_id": "inc-demo-001", "task_type": "aerial_inspection"}).status_code == 422
    assert client.post("/api/v1/execution-tasks", json={"title": "test", "incident_id": "missing", "task_type": "aerial_inspection"}).status_code == 404
    assert client.post("/api/v1/execution-tasks", json={"title": "test", "incident_id": "inc-demo-001", "task_type": "invented"}).status_code == 422
    assert client.get("/api/v1/execution-resources?task_id=missing").status_code == 404


def test_dispatch_running_complete_logs_report_and_restart(tmp_path, clock):
    with TestClient(create_app(tmp_path)) as client:
        task = create(client)
        incident_before = client.get("/api/v1/incidents/inc-demo-001").json()
        assert action(client, task, "start").status_code == 422
        assert client.get(f"/api/v1/execution-tasks/{task['id']}/report").status_code == 409
        started = assign_start(client, task)
        assert started["status"] == "dispatching" and started["progress"] == 0
        repeated = action(client, task, "start").json()
        assert repeated == started
        clock(3)
        running = read(client, task)
        assert running["status"] == "running" and running["progress"] == 0
        assert running["steps"][0]["status"] == "completed"
        clock(12)
        halfway = read(client, task)
        assert halfway["progress"] == 50
        assert halfway["position"] != started["position"]
        assert all(0 <= point[key] <= 1 for point in halfway["route"] + [halfway["position"]] for key in ("x", "y"))
        assert read(client, task)["logs"] == halfway["logs"]
    with TestClient(create_app(tmp_path)) as client:
        assert read(client, task) == halfway
        clock(12)
        finished = read(client, task)
        assert finished["status"] == "completed" and finished["progress"] == 100
        assert finished["position"] == finished["route"][-1]
        assert all(step["status"] == "completed" for step in finished["steps"])
        assert [log["kind"] for log in finished["logs"]] == ["created", "assigned", "dispatching", "running", "completed"]
        report = client.get(f"/api/v1/execution-tasks/{task['id']}/report").json()
        assert report == finished["report"] and report["verification_status"] == "requires_human_review"
        assert report["task_id"] == task["id"] and report["resource_code"] == "UAV-003"
        assert "未采集真实" in dump(report)
        assert client.get("/api/v1/incidents/inc-demo-001").json() == incident_before
        assert client.get("/api/v1/tasks").json() == [finished]
        snapshot = client.get("/api/v1/situation").json()
        assert snapshot["execution_tasks"] == [finished] and snapshot["tasks"] == []
        assert snapshot["execution_resources"][0]["status"] == "available"
        assert action(client, task, "start").status_code == 409
        assert action(client, task, "cancel").status_code == 409
        clock(100)
        assert read(client, task) == finished
        with pytest.raises(sqlite3.IntegrityError):
            client.app.state.db.execute("UPDATE execution_tasks SET payload='{}' WHERE id=?", (task["id"],))


@pytest.mark.parametrize("cancel_after", [0, 1, 11])
def test_cancel_freezes_progress_and_retry_preserves_original(client, clock, cancel_after):
    task = create(client)
    if cancel_after:
        assign_start(client, task)
        clock(cancel_after)
    cancelled = action(client, task, "cancel").json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["report"] is None
    clock(60)
    assert read(client, task) == cancelled
    assert action(client, task, "cancel").json() == cancelled
    assert client.get("/api/v1/execution-resources").json()[0]["status"] == "available"
    retry = action(client, task, "retry").json()
    assert retry["id"] != task["id"] and retry["code"] != task["code"]
    assert retry["parent_task_id"] == task["id"] and retry["attempt"] == 2
    assert retry["status"] == "pending" and retry["progress"] == 0 and retry["resource_id"] is None
    assert action(client, task, "retry").json() == retry
    assert action(client, retry, "retry").status_code == 409
    assert read(client, task) == cancelled


def test_concurrent_start_and_mutual_exclusion_with_legacy_patrol(client, clock):
    first, second = create(client), create(client)
    for task in [first, second]:
        assert action(client, task, "assign", resource_id="UAV-003").status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda task: action(client, task, "start"), [first, second]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    active = next(response.json() for response in responses if response.status_code == 200)
    draft = client.post("/api/v1/situation/patrols", json={"device_id": "dev-drone-01", "target_building_id": "loc-training"}).json()
    assert client.post(f"/api/v1/situation/patrols/{draft['id']}/confirm", json={}).status_code == 409
    assert action(client, active, "cancel").status_code == 200
    assert client.post(f"/api/v1/situation/patrols/{draft['id']}/confirm", json={}).status_code == 200
    waiting = first if first["id"] != active["id"] else second
    assert action(client, waiting, "start").status_code == 409
    resources = client.get(f"/api/v1/execution-resources?task_id={waiting['id']}").json()
    assert resources[0]["status"] == "busy" and "第二天" in resources[0]["reason"]
    clock(15)
    assert action(client, waiting, "start").status_code == 200


def test_resource_type_offline_unknown_anchor_and_aliases(client):
    task = create(client)
    resources = client.get(f"/api/v1/execution-resources?task_id={task['id']}").json()
    assert len(resources) == 3
    assert [item["device_id"] for item in resources] == ["dev-drone-01", "dev-robot-01", None]
    assert resources[0]["eligible"] is True and all(not item["eligible"] for item in resources[1:])
    assert action(client, task, "assign", resource_id="ROBOT-002").status_code == 422
    assert action(client, task, "assign", resource_id="missing").status_code == 404
    db = client.app.state.db
    db.execute("UPDATE observations SET quality='offline' WHERE device_id='dev-drone-01' AND kind='connectivity'")
    assert action(client, task, "assign", resource_id="UAV-003").status_code == 422
    assert read(client, task)["status"] == "pending"
    db.execute("UPDATE incidents SET location_id='loc-library' WHERE id='inc-demo-offline'")
    unknown = create(client, incident_id="inc-demo-offline")
    assert unknown["target_point"] is None
    ground = create(client, incident_id="inc-demo-offline", task_type="ground_inspection")
    # Robot may be offline in older fixtures; either actionable state must prevent execution.
    assert action(client, ground, "assign", resource_id="ROBOT-002").status_code == 422


def add_device_reading(client, device, quality, value):
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    client.app.state.db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)",
                               (new_id("obs"), device, "inc-demo-001", "connectivity", value, "", now.isoformat(), quality, "演示观测"))


def test_offline_during_execution_persists_failure_and_releases_resource(client, clock):
    task = assign_start(client, create(client))
    clock(7)
    running = read(client, task)
    add_device_reading(client, "dev-drone-01", "offline", 0)
    failed = read(client, task)
    assert failed["status"] == "failed" and failed["error"] and failed["report"] is None
    assert failed["progress"] == running["progress"]
    assert failed["logs"][-1]["kind"] == "failed"
    resources = client.get("/api/v1/execution-resources").json()
    assert resources[0]["status"] == "offline" and resources[0]["current_task_id"] is None
    clock(100)
    assert read(client, task) == failed
    retry = action(client, task, "retry").json()
    assert retry["status"] == "pending" and retry["parent_task_id"] == failed["id"]


@pytest.mark.parametrize("task_type,resource", [("ground_inspection", "ROBOT-002"), ("remote_sensing", "SAT-001")])
def test_ground_and_satellite_simulations_are_explicit(client, clock, task_type, resource):
    # Current map fixtures already have an online robot; same readings drive eligibility.
    task = assign_start(client, create(client, task_type=task_type), resource)
    assert task["source_kind"] == "manual_demo" and task["source_run_id"] is None
    if resource == "SAT-001":
        assert task["route"] == [] and task["position"] is None and task["patrol_id"] is None
    else:
        assert task["route"] and task["position"]
    clock(28)
    finished = read(client, task)
    assert finished["status"] == "completed"
    assert finished["report"]["resource_code"] == resource
    assert ("未接入卫星" if resource == "SAT-001" else "避障") in dump(finished["report"])
    assert "DEMO" not in finished["source_label"]
    assert "DEMO" not in dump(finished["report"])
