from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS locations(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_id TEXT REFERENCES locations(id),
 kind TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL);
CREATE TABLE IF NOT EXISTS devices(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
 location_id TEXT NOT NULL REFERENCES locations(id));
CREATE TABLE IF NOT EXISTS incidents(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, location_id TEXT NOT NULL REFERENCES locations(id),
 event_type TEXT NOT NULL, status TEXT NOT NULL, risk_level TEXT NOT NULL,
 summary TEXT NOT NULL, triggered_at TEXT NOT NULL, is_simulated INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS observations(
 id TEXT PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(id),
 incident_id TEXT NOT NULL REFERENCES incidents(id), kind TEXT NOT NULL,
 value REAL, unit TEXT NOT NULL, observed_at TEXT NOT NULL, quality TEXT NOT NULL,
 description TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_observations_incident ON observations(incident_id,device_id,observed_at);
CREATE TABLE IF NOT EXISTS knowledge_documents(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,version TEXT NOT NULL,category TEXT NOT NULL,
 tags TEXT NOT NULL, content TEXT NOT NULL,is_demo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS resources(
 id TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,location_name TEXT NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),
 role TEXT NOT NULL CHECK(role IN ('user','assistant')),content TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runs(
 id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),
 incident_id TEXT NOT NULL REFERENCES incidents(id),instruction TEXT NOT NULL,
 mode TEXT NOT NULL DEFAULT 'demo',status TEXT NOT NULL,stage TEXT NOT NULL,
 created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,summary TEXT,result TEXT,error TEXT,
 cancel_requested INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS ix_one_active_run_per_conversation
 ON agent_runs(conversation_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS run_events(
 id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES agent_runs(id),sequence INTEGER NOT NULL,
 type TEXT NOT NULL,stage TEXT NOT NULL,status TEXT NOT NULL,message TEXT NOT NULL,
 tool_name TEXT,duration_ms REAL,data TEXT,created_at TEXT NOT NULL,
 UNIQUE(run_id,sequence));
CREATE TABLE IF NOT EXISTS map_tasks(
 id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS patrol_missions(
 id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_snapshots(
 id TEXT PRIMARY KEY,incident_id TEXT NOT NULL REFERENCES incidents(id),payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS evidence_snapshot_no_update
 BEFORE UPDATE ON evidence_snapshots BEGIN SELECT RAISE(ABORT,'Evidence snapshots are immutable'); END;
CREATE TABLE IF NOT EXISTS execution_tasks(
 id TEXT PRIMARY KEY,code TEXT NOT NULL UNIQUE,incident_id TEXT NOT NULL REFERENCES incidents(id),
 source_run_id TEXT REFERENCES agent_runs(id),task_type TEXT NOT NULL,
 parent_task_id TEXT REFERENCES execution_tasks(id),resource_id TEXT,status TEXT NOT NULL,
 payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ix_execution_from_run ON execution_tasks(source_run_id,task_type)
 WHERE source_run_id IS NOT NULL AND parent_task_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_execution_retry ON execution_tasks(parent_task_id)
 WHERE parent_task_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_execution_resource_active ON execution_tasks(resource_id)
 WHERE resource_id IS NOT NULL AND status IN ('dispatching','running');
CREATE TRIGGER IF NOT EXISTS execution_completed_no_update
 BEFORE UPDATE ON execution_tasks WHEN OLD.status='completed'
 BEGIN SELECT RAISE(ABORT,'Completed execution records are immutable'); END;
CREATE TABLE IF NOT EXISTS execution_task_sources(
 task_id TEXT PRIMARY KEY REFERENCES execution_tasks(id),payload TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS execution_source_no_update
 BEFORE UPDATE ON execution_task_sources
 BEGIN SELECT RAISE(ABORT,'Execution provenance is immutable'); END;
CREATE TABLE IF NOT EXISTS incident_codes(
 incident_id TEXT PRIMARY KEY REFERENCES incidents(id),code TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS assessment_reports(
 id TEXT PRIMARY KEY,run_id TEXT NOT NULL UNIQUE REFERENCES agent_runs(id),
 incident_id TEXT NOT NULL REFERENCES incidents(id),evidence_snapshot_id TEXT REFERENCES evidence_snapshots(id),
 payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS assessment_report_no_update
 BEFORE UPDATE ON assessment_reports BEGIN SELECT RAISE(ABORT,'Assessment reports are immutable'); END;
"""


class Database:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "tianqiong.sqlite3"

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_runs)")}
            if "evidence_snapshot_id" not in columns:
                conn.execute("ALTER TABLE agent_runs ADD COLUMN evidence_snapshot_id TEXT REFERENCES evidence_snapshots(id)")
            conn.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version','1')")
        from .fixtures import seed, seed_day2
        seed(self)
        seed_day2(self)

    def rows(self, query: str, args=()) -> list[dict]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(query, args).fetchall()]

    def row(self, query: str, args=()) -> dict | None:
        rows = self.rows(query, args)
        return rows[0] if rows else None

    def execute(self, query: str, args=()):
        with self.connection() as conn:
            return conn.execute(query, args).rowcount

    def incident(self, incident_id: str) -> dict | None:
        result = self.row("SELECT i.*,l.name AS location_name,c.code FROM incidents i JOIN locations l ON l.id=i.location_id LEFT JOIN incident_codes c ON c.incident_id=i.id WHERE i.id=?", (incident_id,))
        if result:
            result["is_simulated"] = bool(result["is_simulated"])
        return result

    def incidents(self) -> list[dict]:
        from .evidence import timestamp
        rows = self.rows("SELECT i.*,l.name AS location_name,c.code FROM incidents i JOIN locations l ON l.id=i.location_id LEFT JOIN incident_codes c ON c.incident_id=i.id ORDER BY i.rowid DESC")
        rows.sort(key=lambda row: timestamp(row["triggered_at"]), reverse=True)
        for row in rows:
            row["is_simulated"] = bool(row["is_simulated"])
        return rows

    def latest_incident_id(self) -> str | None:
        incidents = self.incidents()
        return incidents[0]["id"] if incidents else None

    def observations(self, incident_id: str, device_id: str | None = None) -> list[dict]:
        from .evidence import ordered_observations
        query = "SELECT * FROM observations WHERE incident_id=?"
        args = [incident_id]
        if device_id:
            query += " AND device_id=?"
            args.append(device_id)
        return ordered_observations(self.rows(query + " ORDER BY rowid", args))

    def devices(self, incident_id: str | None = None) -> list[dict]:
        from .fixtures import DEVICE_CODES
        from .evidence import device_status
        from .rules import references_for
        incident_id = incident_id or self.latest_incident_id()
        observations = self.observations(incident_id) if incident_id else []
        result = self.rows("SELECT d.*,l.name AS location_name FROM devices d JOIN locations l ON l.id=d.location_id ORDER BY d.id")
        for device in result:
            related = [o for o in observations if o["device_id"] == device["id"]]
            # Only this incident's latest record of each kind contributes to state.
            latest = {o["kind"]: o for o in related}
            status = device_status(latest)
            device.update(code=DEVICE_CODES.get(device["id"], device["id"]), status=status, last_seen=related[-1]["observed_at"] if related else None, references=references_for(device["type"]), is_simulated=True)
        return result

    def run(self, run_id: str) -> dict | None:
        row = self.row("SELECT * FROM agent_runs WHERE id=?", (run_id,))
        if row:
            row.pop("cancel_requested", None)
            row["result"] = json.loads(row["result"]) if row["result"] else None
        return row

    def runs(self) -> list[dict]:
        return [self.run(row["id"]) for row in self.rows("SELECT id FROM agent_runs ORDER BY created_at DESC,rowid DESC")]

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        rows = self.rows("SELECT * FROM run_events WHERE run_id=? AND sequence>? ORDER BY sequence", (run_id, after))
        for row in rows:
            row["data"] = json.loads(row["data"]) if row["data"] else None
        return rows

    def append_event(self, run_id: str, *, type: str, stage: str, status: str, message: str,
                     tool_name: str | None = None, duration_ms: float | None = None, data: dict | None = None) -> dict:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sequence = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM run_events WHERE run_id=?", (run_id,)).fetchone()[0]
            row = dict(id=new_id("evt"), run_id=run_id, sequence=sequence, type=type, stage=stage,
                       status=status, message=message, tool_name=tool_name, duration_ms=duration_ms,
                       data=data, created_at=utc_now())
            conn.execute("INSERT INTO run_events VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                row["id"],run_id,sequence,type,stage,status,message,tool_name,duration_ms,
                dump(data) if data is not None else None,row["created_at"]))
        return row
