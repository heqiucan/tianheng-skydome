from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .database import Database, dump, new_id, utc_now
from .fixtures import trigger_scenario, trigger_temperature_only
from .evidence import EvidenceService
from .schemas import ConversationCreate, RunCreate, EvidenceSnapshotCreate, ExecutionTaskCreate, ExecutionFromRun, ExecutionAssignment, StrictRequest
from .situation import MapTaskCreate, PatrolCreate, Situation
from .execution import ExecutionService
from .demo_scenario import prepare_scenario, get_scenario
from .assessment import AssessmentReports
from .workflow import TERMINAL, Workflow


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    runtime_dir = Path(data_dir or os.environ.get("TIANQIONG_DATA_DIR") or PROJECT_ROOT / ".runtime")
    db = Database(runtime_dir)
    workflow = Workflow(db)
    situation = Situation(db)
    evidence = EvidenceService(db)
    execution = ExecutionService(db, situation.catalog)
    assessments = AssessmentReports(db)

    @asynccontextmanager
    async def lifespan(application):
        db.initialize()
        workflow.recover_interrupted()
        yield
        await workflow.shutdown()

    app = FastAPI(title="天亨 · 安全协同演示 API", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.workflow = workflow
    app.state.situation = situation
    app.state.execution = execution
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Last-Event-ID"])

    def require_incident(incident_id):
        incident = db.incident(incident_id)
        if not incident:
            raise HTTPException(404, "事件不存在")
        return incident

    def require_run(run_id):
        run = db.run(run_id)
        if not run:
            raise HTTPException(404, "核查任务不存在")
        return run

    def document(row):
        row["tags"] = json.loads(row["tags"])
        row["is_demo"] = bool(row["is_demo"])
        return row

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/system/status")
    def system_status():
        db.row("SELECT value FROM metadata WHERE key='schema_version'")
        model = {"provider": "zhipu", "model": os.environ.get("ZAI_MODEL") or os.environ.get("TIANQIONG_MODEL", "glm-5.3-flash"),
                 "configured": bool(os.environ.get("ZHIPU_API_KEY") or os.environ.get("ZAI_API_KEY")),
                 "verified": False, "status": "not_verified", "message": "当前使用规则演示工作流；模型连接尚未验证。"}
        probe_file = runtime_dir / "model_probe.json"
        try:
            probe = json.loads(probe_file.read_text(encoding="utf-8"))
            if not isinstance(probe, dict):
                raise ValueError("invalid probe metadata")
            for key in ("provider", "model", "status", "message"):
                if isinstance(probe.get(key), str):
                    model[key] = probe[key][:300]
            for key in ("configured", "verified"):
                if isinstance(probe.get(key), bool):
                    model[key] = probe[key]
        except (OSError, ValueError, TypeError):
            pass
        return {"app_name": "天亨 · 空天地人智能安全协同平台", "version": "0.5.0", "milestone": "day5", "mode": "demo", "model": model,
                "capabilities": {"persistent_data": True, "sensor_query": True, "device_query": True,
                                 "history_query": True, "sse_progress": True, "preliminary_rules": True,
                                 "model_driven_workflow": False, "approval_dispatch": False,
                                 "final_report": False, "real_device_control": False,
                                 "situation_map": True, "map_task_context": True, "simulated_patrol": True,
                                 "event_evidence_context": True, "immutable_evidence_snapshots": True,
                                 "simulated_execution_tasks": True, "simulated_execution_reports": True,
                                 "persistent_assessment_reports": True, "device_evidence_entry": True,
                                 "fixed_presentation_scenario": True}, "database": "connected"}

    @app.get("/api/v1/overview")
    def overview():
        devices = db.devices()
        return {"incident_count": db.row("SELECT COUNT(*) AS count FROM incidents")["count"],
                "active_task_count": db.row("SELECT COUNT(*) AS count FROM agent_runs WHERE status IN ('queued','running')")["count"],
                "device_count": len(devices), "online_device_count": sum(d["status"] in {"online", "alarm"} for d in devices),
                "latest_incident_id": db.latest_incident_id()}

    @app.get("/api/v1/incidents")
    def incidents():
        return db.incidents()

    @app.get("/api/v1/incidents/{incident_id}")
    def incident(incident_id: str):
        return require_incident(incident_id)

    @app.get("/api/v1/incidents/{incident_id}/context")
    def incident_context(incident_id: str):
        return evidence.context(incident_id)

    @app.post("/api/v1/incidents/{incident_id}/evidence-snapshots", status_code=201)
    def evidence_snapshot(incident_id: str, body: EvidenceSnapshotCreate):
        return evidence.create(incident_id, body.source_view, body.image_id,
                               body.source_selection.model_dump() if body.source_selection else None)

    @app.get("/api/v1/evidence-snapshots/{snapshot_id}")
    def get_evidence_snapshot(snapshot_id: str):
        return evidence.get(snapshot_id)

    @app.post("/api/v1/demo-scenarios/evt-008/prepare")
    def prepare_presentation(body: StrictRequest):
        return prepare_scenario(db)

    @app.get("/api/v1/demo-scenarios/evt-008")
    def presentation_state():
        return get_scenario(db)

    @app.post("/api/v1/scenarios/temperature-only/trigger", status_code=201)
    def temperature_only():
        return trigger_temperature_only(db)

    @app.post("/api/v1/scenarios/fire/trigger", status_code=201)
    def trigger():
        return trigger_scenario(db)

    @app.get("/api/v1/locations")
    def locations():
        return db.rows("SELECT * FROM locations ORDER BY rowid")

    @app.get("/api/v1/devices")
    def devices(incident_id: str | None = None):
        if incident_id:
            require_incident(incident_id)
        return db.devices(incident_id)

    @app.get("/api/v1/devices/{device_id}/observations")
    def observations(device_id: str, incident_id: str | None = None):
        if not db.row("SELECT id FROM devices WHERE id=?", (device_id,)):
            raise HTTPException(404, "设备不存在")
        incident_id = incident_id or db.latest_incident_id()
        if incident_id:
            require_incident(incident_id)
        return db.observations(incident_id, device_id) if incident_id else []

    @app.get("/api/v1/devices/{device_id}/analysis-context")
    def device_analysis_context(device_id: str, incident_id: str | None = None):
        return evidence.device_context(device_id, incident_id)

    @app.get("/api/v1/assessment-reports")
    def assessment_reports(incident_id: str | None = None, device_id: str | None = None):
        return assessments.list(incident_id, device_id)

    @app.get("/api/v1/assessment-reports/{report_id}")
    def assessment_report(report_id: str):
        return assessments.get(report_id)

    @app.get("/api/v1/runs/{run_id}/assessment-report")
    def run_assessment_report(run_id: str):
        return assessments.for_run(run_id)

    @app.get("/api/v1/knowledge/search")
    def knowledge_search(q: str = Query(default="", max_length=200)):
        # Small local fixture collection: literal substring search supports Chinese.
        rows = [document(row) for row in db.rows("SELECT * FROM knowledge_documents ORDER BY id")]
        term = q.strip().casefold()
        return [row for row in rows if not term or term in " ".join([row["title"], row["content"], *row["tags"]]).casefold()]

    @app.get("/api/v1/knowledge/{document_id}")
    def knowledge_document(document_id: str):
        row = db.row("SELECT * FROM knowledge_documents WHERE id=?", (document_id,))
        if not row:
            raise HTTPException(404, "知识资料不存在")
        return document(row)

    @app.get("/api/v1/resources")
    def resources():
        return [dict(row, is_simulated=True) for row in db.rows("SELECT * FROM resources ORDER BY id")]

    @app.post("/api/v1/conversations", status_code=201)
    def create_conversation(body: ConversationCreate):
        row = {"id": new_id("chat"), "title": body.title, "created_at": utc_now()}
        db.execute("INSERT INTO conversations VALUES (?,?,?)", tuple(row.values()))
        return row

    @app.get("/api/v1/conversations")
    def conversations():
        return db.rows("SELECT * FROM conversations ORDER BY created_at DESC,rowid DESC")

    @app.get("/api/v1/conversations/{conversation_id}")
    def conversation(conversation_id: str):
        row = db.row("SELECT * FROM conversations WHERE id=?", (conversation_id,))
        if not row:
            raise HTTPException(404, "会话不存在")
        row["messages"] = db.rows("SELECT id,role,content,created_at FROM messages WHERE conversation_id=? ORDER BY created_at,rowid", (conversation_id,))
        return row

    @app.post("/api/v1/runs", status_code=202)
    async def create_run(body: RunCreate):
        if not db.row("SELECT id FROM conversations WHERE id=?", (body.conversation_id,)):
            raise HTTPException(404, "会话不存在，请先新建会话")
        require_incident(body.incident_id)
        try:
            run = workflow.create(body.conversation_id, body.incident_id, body.instruction, body.evidence_snapshot_id)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "该会话已有进行中的核查，请等待或停止后再发送") from None
        workflow.start(run["id"])
        return run

    @app.get("/api/v1/runs")
    def runs():
        return db.runs()

    @app.get("/api/v1/runs/{run_id}")
    def run(run_id: str):
        return require_run(run_id)

    @app.get("/api/v1/runs/{run_id}/event-history")
    def run_event_history(run_id: str, after: int = Query(default=0, ge=0)):
        require_run(run_id)
        return db.events(run_id, after)

    @app.post("/api/v1/runs/{run_id}/cancel")
    async def cancel_run(run_id: str):
        require_run(run_id)
        return workflow.cancel(run_id)

    @app.get("/api/v1/runs/{run_id}/events")
    async def stream_events(run_id: str, request: Request, after: int = Query(default=0, ge=0), last_event_id: str | None = Header(default=None)):
        require_run(run_id)
        if last_event_id is not None:
            try:
                after = max(after, int(last_event_id))
            except ValueError:
                raise HTTPException(400, "Last-Event-ID 必须是非负事件序号") from None
            if int(last_event_id) < 0:
                raise HTTPException(400, "Last-Event-ID 必须是非负事件序号")

        async def generate():
            cursor = after
            signal = workflow.signal(run_id)
            while True:
                signal.clear()
                events = db.events(run_id, cursor)
                for event in events:
                    cursor = event["sequence"]
                    yield f"id: {cursor}\nevent: update\ndata: {dump(event)}\n\n"
                if require_run(run_id)["status"] in TERMINAL:
                    break
                if await request.is_disconnected():
                    break
                try:
                    await asyncio.wait_for(signal.wait(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/v1/tasks")
    @app.get("/api/v1/execution-tasks")
    def dispatch_tasks(incident_id: str | None = None, run_id: str | None = None):
        return execution.list(incident_id, run_id)

    @app.post("/api/v1/execution-tasks", status_code=201)
    def create_execution_task(body: ExecutionTaskCreate):
        return execution.create(body)

    @app.post("/api/v1/execution-tasks/from-run")
    def execution_from_run(body: ExecutionFromRun):
        return execution.from_run(body)

    @app.get("/api/v1/execution-resources")
    def execution_resources(task_id: str | None = None):
        return execution.resources(task_id)

    @app.get("/api/v1/execution-tasks/{task_id}")
    def execution_task(task_id: str):
        return execution.get(task_id)

    @app.post("/api/v1/execution-tasks/{task_id}/assign")
    def execution_assign(task_id: str, body: ExecutionAssignment):
        return execution.assign(task_id, body.resource_id)

    @app.post("/api/v1/execution-tasks/{task_id}/start")
    def execution_start(task_id: str, body: StrictRequest):
        return execution.start(task_id)

    @app.post("/api/v1/execution-tasks/{task_id}/cancel")
    def execution_cancel(task_id: str, body: StrictRequest):
        return execution.cancel(task_id)

    @app.post("/api/v1/execution-tasks/{task_id}/retry")
    def execution_retry(task_id: str, body: StrictRequest):
        return execution.retry(task_id)

    @app.get("/api/v1/execution-tasks/{task_id}/report")
    def execution_report(task_id: str):
        return execution.report(task_id)

    @app.get("/api/v1/situation")
    def situation_snapshot():
        return situation.snapshot()

    @app.post("/api/v1/situation/tasks", status_code=201)
    def create_map_task(body: MapTaskCreate):
        return situation.create_task(body)

    @app.get("/api/v1/situation/tasks/{task_id}")
    def map_task(task_id: str):
        return situation.task(task_id)

    @app.post("/api/v1/situation/patrols", status_code=201)
    def create_patrol(body: PatrolCreate):
        return situation.create_patrol(body)

    @app.post("/api/v1/situation/patrols/{patrol_id}/confirm")
    def confirm_patrol(patrol_id: str):
        return situation.confirm_patrol(patrol_id)

    @app.get("/api/v1/situation/patrols/{patrol_id}")
    def patrol(patrol_id: str):
        return situation.patrol(patrol_id)

    return app


app = create_app()
