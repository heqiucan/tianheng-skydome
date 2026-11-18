# DAY 04 implementation contract

Current baseline is Day 3 stage 1 only: real database tools + deterministic rules, no model-driven planning. Day 4 must label task source truthfully and preserve prior interfaces/history. No keys or LLM calls in this scope. Vue/FastAPI/SQLite retained; no new dependencies.

## Canonical execution API

All under /api/v1. New endpoints use /execution-tasks, separate from analysis runs and map_tasks. Existing GET /tasks becomes compatible alias returning execution task list (initially empty).

- GET /execution-tasks -> ExecutionTask[]; optional incident_id, run_id filters.
- POST /execution-tasks {title,incident_id,task_type,priority} -> 201 ExecutionTask. Server derives building and related devices from event context, validates all inputs.
- POST /execution-tasks/from-run {run_id,task_type:'aerial_inspection' default} -> ExecutionTask. Requires completed run with saved result and evidence_snapshot_id. Derive context from immutable snapshot. Idempotent per (run_id,task_type); return existing original task on repeated requests. Priority derived from assessment, source_kind='rule_assessment'.
- GET /execution-tasks/{id} -> ExecutionTask, including logs/steps/report.
- GET /execution-resources?task_id=... -> ExecutionResource[]. Task-specific eligibility and reason server-derived; no task_id gives general status.
- POST /execution-tasks/{id}/assign {resource_id} -> ExecutionTask (pending only).
- POST /execution-tasks/{id}/start {} -> ExecutionTask. pending -> dispatching, transactional resource reservation.
- POST /execution-tasks/{id}/cancel {} -> ExecutionTask. pending/dispatching/running -> cancelled. Idempotent on cancelled; completed/failed reject.
- POST /execution-tasks/{id}/retry {} -> ExecutionTask. New child attempt for cancelled/failed/completed, preserve original. Repeated retry on same parent returns same child (idempotent); repeat again from child if wanted.
- GET /execution-tasks/{id}/report -> ExecutionReport. 409 until completed.

## Types

ExecutionTask={
id:string,code:string (TASK-001 etc persisted),title:string,
task_type:'aerial_inspection'|'ground_inspection'|'remote_sensing',
source_kind:'manual_demo'|'rule_assessment',source_label:string,
source_run_id:string|null,evidence_snapshot_id:string|null,
incident_id:string,incident_title:string,device_ids:string[],
target_building_id:string,target_building_name:string,
priority:'high'|'medium'|'low',risk_level:string,
resource_id:string|null,resource_code:string|null,resource_name:string|null,
status:'pending'|'dispatching'|'running'|'completed'|'failed'|'cancelled',progress:number,
created_at:string,updated_at:string,started_at:string|null,finished_at:string|null,
dispatch_seconds:number,duration_seconds:number,
image_id:string|null,route:{x:number,y:number}[],position:{x:number,y:number}|null,
target_point:{x:number,y:number}|null,patrol_id:string|null,
parent_task_id:string|null,attempt:number,
steps:{id:string,title:string,status:'pending'|'running'|'completed'|'cancelled'|'failed',started_at:string|null,finished_at:string|null}[],
logs:{id:string,sequence:number,at:string,kind:string,message:string}[],
report:ExecutionReport|null,error:string|null,is_simulated:true
}

ExecutionResource={id:string,code:string,name:string,type:'drone'|'robot'|'satellite',device_id:string|null,status:'available'|'busy'|'offline',online:boolean,current_task_id:string|null,current_task_code:string|null,area:string,capabilities:string[],battery:number|null,eligible:boolean,reason:string|null,is_simulated:true}

ExecutionReport={id:string,task_id:string,task_code:string,title:string,incident_id:string,source_run_id:string|null,evidence_snapshot_id:string|null,resource_id:string,resource_code:string,started_at:string,finished_at:string,generated_at:string,scope:string,summary:string,findings:string[],recommendations:string[],limitations:string[],verification_status:'requires_human_review',is_simulated:true}

Resources: UAV-003 maps to existing dev-drone-01 (Day2 DRONE-001), ROBOT-002 maps to existing dev-robot-01 (Day2 ROBOT-001), SAT-001 has no real device or imagery. Display alias mapping where helpful. Do not rename existing stable device IDs or create fake duplicate physical devices. Resource online state for mapped devices uses latest observations; satellite is explicitly simulation-only.

## State and persistence

Server owns state, timing, steps, logs and immutable completed report. SQLite BEGIN IMMEDIATE for transitions/resource reservation; exactly once phase logs under polling. Proposed demo timing: 3 sec dispatch + 24 sec execution (not physical estimate). Frontend may interpolate only route marker based on last authoritative state; does not manufacture task results or completion.

Persist all data, derive elapsed progress from stored timestamps on reads, survive refresh/service restart. Resource has one active task across dispatching/running and existing Day2 patrols. Day2 confirm must also reject a reserved Day4 drone. Cancel frees reservation and freezes progress, stops attached patrol. Failed/terminal tasks never resume automatically. Retry creates a new linked attempt.

Reuse Situation route/advance geometry with small lower-level helpers, avoid snapshot -> task -> snapshot recursion. Optional use attached Day2 patrol; both models must have same authoritative start/progress/state. Otherwise separate execution route with shared occupation check and common geometry is acceptable. UAV normalized route/position mandatory. Robot normalized route may be illustrative (not obstacle-aware navigation); satellite must be simulated regional review without invented imagery or flight route. Unknown building anchor blocks mobile route execution with actionable error.

Task report is specific to task/resource/target/time/evidence; states no actual sensor/video collection. Completion records review required; does not clear original incident or claim risk eliminated.

GET /situation adds execution_tasks:ExecutionTask[], execution_resources:ExecutionResource[] (no recursion). Shared frontend polling keeps task center, workbench linked task list, and map consistent.

## Frontend scope

TaskCenter replaces current tasks module but keeps old runs/map_tasks in a separate visible history tab. Stats derive from canonical task list; pending includes dispatching only if clearly labeled otherwise separate dispatching badge. Abnormal=failed/cancelled with explicit caption. Search/status/type filters; manual creation; detail drawer; resource selection; start/cancel/retry; logs, report view/download.

EvidenceWorkbench completed results expose '根据规则核查创建执行任务'; show linked execution progress/results, navigation to tasks, with Chinese simulation labels. No claims of real model planning. App can restore selected execution task ID via localStorage; in-app page state retained, no router dependency. Open related event/device through existing map selection. Return map restores task image, target and selected execution route.

SituationView coordination view adds resource/active execution cards and selection. CampusImageMap receives optional executionMission prop; reuse SVG and pointAlongRoute. Selected execution route takes precedence over old patrol route, maps UAV alias to existing device ID; include start/target marker, status/progress and clear Chinese simulation label. Product brand is 天亨. Legacy technical identifiers are preserved. Satellite no fake flight. Preserve legacy map controls and images.

Images only design references. Keep current deep-blue navigation and header; no foreign campus backgrounds. Root copies latest three references and records actual sizes/usage before implementation.

## Ownership and acceptance

Backend agent owns backend/** and backend tests. Frontend agent owns frontend/src/**. Root owns docs/references/integration acceptance. Reviewer read-only. No server restart by agents.

Tests: from-run eligibility + idempotence + immutable provenance; manual invalid IDs; state transitions + duplicate start; cross-Day2/Day4 resource busy; cancel/retry; offline/resource-type mismatch; reload persistence; report association + event not auto-closed; normalized route/position; satellite honesty. Run old tests as regression.

Root actual browser acceptance: create from saved run -> task list -> select UAV -> start -> dispatch/running position/progress -> refresh -> finish -> report -> workbench feedback -> map state; manual task + resource compatibility + cancel/retry; old Day1/2/3 basic functions and responsive view.
