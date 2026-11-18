import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.database import Database
from app.main import create_app
from app.workflow import assess_risk, query_event_history
from app import workflow as workflow_module


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as value:
        yield value


def create_conversation(client):
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    return response.json()["id"]


def finish(client, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return run
        time.sleep(0.01)
    pytest.fail("workflow did not finish")


def test_fixtures_are_idempotent_and_not_real_telemetry(tmp_path):
    db = Database(tmp_path)
    db.initialize()
    initial = db.observations("inc-demo-001")
    db.initialize()
    assert db.observations("inc-demo-001") == initial
    assert len(db.devices()) == 9
    assert len(db.incidents()) == 3
    assert all(d["is_simulated"] for d in db.devices())
    assert db.incident("inc-demo-001")["risk_level"] == "unassessed"


def test_scenarios_do_not_mix_observations_or_device_states(client):
    db = client.app.state.db
    original = db.observations("inc-demo-001")
    other = client.post("/api/v1/scenarios/fire/trigger").json()
    db.execute("UPDATE observations SET value=24,quality='good' WHERE incident_id=? AND device_id='dev-temp-01'", (other["id"],))
    assert db.observations("inc-demo-001") == original
    old_devices = client.get("/api/v1/devices", params={"incident_id": "inc-demo-001"}).json()
    new_devices = client.get("/api/v1/devices", params={"incident_id": other["id"]}).json()
    assert next(d for d in old_devices if d["id"] == "dev-temp-01")["status"] == "alarm"
    assert next(d for d in new_devices if d["id"] == "dev-temp-01")["status"] == "online"
    readings = client.get("/api/v1/devices/dev-temp-01/observations", params={"incident_id": other["id"]}).json()
    assert all(o["incident_id"] == other["id"] and o["value"] == 24 for o in readings)
    history = query_event_history(db, "inc-demo-001")["incidents"]
    assert other["id"] not in {i["id"] for i in history}
    assert all(i["triggered_at"] < db.incident("inc-demo-001")["triggered_at"] for i in history)


def test_run_records_real_tools_and_replay_resumes_without_duplicates(client):
    conversation_id = create_conversation(client)
    response = client.post("/api/v1/runs", json={"conversation_id": conversation_id, "incident_id": "inc-demo-001", "instruction": "检查实训楼二层异常情况"})
    assert response.status_code == 202
    run = finish(client, response.json()["id"])
    assert run["status"] == "completed", run
    assert run["mode"] == "demo"
    assert run["result"]["level"] == "high"
    assert run["result"]["scope"] == "preliminary_demo_assessment"
    db = client.app.state.db
    source_ids = {o["id"] for o in db.observations("inc-demo-001")}
    assert all(e["source_id"] in source_ids for e in run["result"]["evidence"])
    events = db.events(run["id"])
    tools = [e for e in events if e["type"] == "tool_result"]
    assert [e["tool_name"] for e in tools] == ["query_sensor_data", "query_device_status", "query_event_history"]
    assert all(e["duration_ms"] >= 0 for e in tools)
    assert db.incident("inc-demo-001")["risk_level"] == run["result"]["level"]
    replay = client.get(f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": "3"})
    assert replay.status_code == 200
    parsed = [json.loads(line[6:]) for line in replay.text.splitlines() if line.startswith("data: ")]
    assert [e["sequence"] for e in parsed] == [e["sequence"] for e in events if e["sequence"] > 3]
    assert parsed[-1]["type"] == "terminal"
    assert client.get(f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": "invalid"}).status_code == 400
    messages = client.get(f"/api/v1/conversations/{conversation_id}").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert client.get("/api/v1/tasks").json() == []


def test_cancel_queued_run_does_not_execute_tools(client):
    conversation_id = create_conversation(client)
    workflow = client.app.state.workflow
    run = workflow.create(conversation_id, "inc-demo-001", "停止测试")
    result = client.post(f"/api/v1/runs/{run['id']}/cancel").json()
    assert result["status"] == "cancelled"
    asyncio.run(workflow.execute(run["id"]))
    assert not any(e["type"] == "tool_start" for e in client.app.state.db.events(run["id"]))
    assert client.post(f"/api/v1/runs/{run['id']}/cancel").json()["status"] == "cancelled"


def test_poll_history_returns_persisted_events_incrementally_and_validates_cursor(client):
    run = client.app.state.workflow.create(create_conversation(client), "inc-demo-001", "轮询核查")
    path = f"/api/v1/runs/{run['id']}/event-history"
    first = client.get(path)
    assert first.status_code == 200
    assert first.json() == client.app.state.db.events(run["id"])
    cursor = first.json()[-1]["sequence"]
    assert client.get(path, params={"after": cursor}).json() == []
    client.post(f"/api/v1/runs/{run['id']}/cancel")
    tail = client.get(path, params={"after": cursor}).json()
    assert tail == client.app.state.db.events(run["id"], cursor)
    assert tail[-1]["type"] == "terminal"
    assert all(event["sequence"] > cursor and event["run_id"] == run["id"] for event in tail)
    assert client.get(path, params={"after": -1}).status_code == 422
    assert client.get(path, params={"after": "invalid"}).status_code == 422
    assert client.get("/api/v1/runs/missing/event-history").status_code == 404


def test_cancel_during_query_prevents_following_tools(client, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original = workflow_module.query_sensor_data

    def held_query(db, incident_id):
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test query was not released")
        return original(db, incident_id)

    monkeypatch.setattr(workflow_module, "query_sensor_data", held_query)
    conversation_id = create_conversation(client)
    try:
        response = client.post("/api/v1/runs", json={"conversation_id": conversation_id, "incident_id": "inc-demo-001", "instruction": "核查后停止"})
        run_id = response.json()["id"]
        assert started.wait(timeout=2)
        assert client.post(f"/api/v1/runs/{run_id}/cancel").json()["status"] == "cancelled"
    finally:
        release.set()
    deadline = time.monotonic() + 3
    while client.app.state.workflow.tasks and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not client.app.state.workflow.tasks
    events = client.app.state.db.events(run_id)
    assert [event["tool_name"] for event in events if event["type"] == "tool_start"] == ["query_sensor_data"]
    assert events[-1]["status"] == "cancelled"


def test_no_evidence_is_unknown_not_low():
    result = assess_risk({"observations": []}, {"devices": []}, {"incidents": []})
    assert result["level"] == "unknown"
    assert result["evidence"] == []
    assert any("不完整" in item for item in result["uncertainties"])


def test_api_rejects_missing_ids_blank_instructions_and_active_duplicate(client):
    conversation_id = create_conversation(client)
    body = {"conversation_id": conversation_id, "incident_id": "inc-demo-001", "instruction": "检查"}
    assert client.post("/api/v1/runs", json={**body, "instruction": "   "}).status_code == 422
    assert client.post("/api/v1/runs", json={**body, "incident_id": "missing"}).status_code == 404
    assert client.get("/api/v1/devices?incident_id=missing").status_code == 404
    client.app.state.workflow.create(conversation_id, "inc-demo-001", "核查")
    assert client.post("/api/v1/runs", json=body).status_code == 409


def test_restart_marks_running_task_interrupted_and_preserves_history(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        conversation_id = create_conversation(client)
        run = client.app.state.workflow.create(conversation_id, "inc-demo-001", "持久化核查")
    with TestClient(create_app(tmp_path)) as client:
        response = client.get(f"/api/v1/runs/{run['id']}").json()
        assert response["status"] == "interrupted"
        assert len(client.get("/api/v1/incidents").json()) == 3
        assert client.app.state.db.events(run["id"])[-1]["type"] == "terminal"


def test_model_metadata_whitelist_and_knowledge_search(client):
    runtime = client.app.state.db.data_dir
    (runtime / "model_probe.json").write_text(json.dumps({"provider": "zhipu", "model": "test-model", "verified": True, "configured": True, "api_key": "must-not-be-returned", "status": "verified", "message": "已完成工具调用探测"}), encoding="utf-8")
    response = client.get("/api/v1/system/status")
    assert "must-not-be-returned" not in response.text
    assert response.json()["model"]["verified"] is True
    assert response.json()["capabilities"]["model_driven_workflow"] is False
    assert client.get("/api/v1/knowledge/search?q=烟雾").json()[0]["id"] == "kb-fire-01"
    (runtime / "model_probe.json").write_text("[]", encoding="utf-8")
    assert client.get("/api/v1/system/status").status_code == 200
