# Day 1 implementation contract

Scope: local single-user foundation, real persisted demo data, three live read-only business tools, working SSE progress, and a separate verified model tool-call probe. Full model-driven orchestration, approval/dispatch, and final report generation remain later milestones. Never present them as completed.

Backend: FastAPI at 127.0.0.1:8000. Frontend Vite at 127.0.0.1:5173, proxy /api and /health to backend. All data is simulated, functions and persistence are real. Never expose secrets or hidden reasoning.

API prefix /api/v1. JSON field names snake_case. IDs strings. Dates ISO 8601 UTC; UI localizes. Frontend fetch wrapper returns typed JSON, backend errors use detail.

- GET /health -> {status:"ok"}
- GET /system/status -> {app_name,version,milestone:"day1",mode:"demo",model:{provider,model,configured,verified,status,message},capabilities:{...},database:"connected"}
- GET /overview -> {incident_count,active_task_count,device_count,online_device_count,latest_incident_id}
- GET /incidents -> Incident[]
- GET /incidents/{id} -> Incident
- POST /scenarios/fire/trigger -> Incident (new independent scenario, do not delete previous data)
- GET /locations -> Location[]
- GET /devices?incident_id= -> Device[]
- GET /devices/{id}/observations?incident_id= -> Observation[]
- GET /knowledge/search?q= -> KnowledgeDocument[]
- GET /knowledge/{id} -> KnowledgeDocument
- GET /resources -> Resource[]
- POST /conversations body {title?:string} -> {id,title,created_at}
- GET /conversations -> Conversation[]
- GET /conversations/{id} -> {id,title,created_at,messages:Message[]}
- POST /runs body {conversation_id,incident_id,instruction} -> Run (202)
- GET /runs -> Run[] newest first
- GET /runs/{id} -> Run
- GET /runs/{id}/events?after=0 SSE events named update, JSON RunEvent, sequence unique. Last-Event-ID supported. Already-finished run replays then closes.
- POST /runs/{id}/cancel -> Run
- GET /tasks -> [] (dispatch tasks not implemented; UI may instead show /runs as analysis tasks)

Incident: {id,title,location_id,location_name,event_type,status,risk_level,summary,triggered_at,is_simulated:true}
Location: {id,name,parent_id,kind,x,y}
Device: {id,name,type,location_id,location_name,status,last_seen,is_simulated:true}
Observation: {id,device_id,incident_id,kind,value:number|null,unit,observed_at,quality,description}
KnowledgeDocument: {id,title,version,category,tags:string[],content,is_demo:true}
Resource: {id,name,role,location_name,status,is_simulated:true}
Message: {id,role,content,created_at}
Conversation: {id,title,created_at}
Run: {id,conversation_id,incident_id,instruction,mode:"demo",status:"queued"|"running"|"completed"|"cancelled"|"failed"|"interrupted",stage,created_at,started_at,finished_at,summary:null|string,result:null|RiskResult,error:null|string}
RunEvent: {id,run_id,sequence,type,stage,status,message,tool_name:null|string,duration_ms:null|number,data:object|null,created_at}
RiskResult: {level,title,evidence:[{label,value,source_id}],reasons:string[],uncertainties:string[],recommendations:string[],rule_version,is_demo:true,scope:"preliminary_demo_assessment"}

Run tools: query_sensor_data, query_device_status, query_event_history. Real DB reads, no fake timing/sleep. Complete a clearly labeled preliminary demo rule assessment; do not claim model-driven planning. Incomplete/no evidence must not become low risk. Clear scope: not an emergency decision system.

All pages read shared backend data. Seed one fictional campus incident, 8 devices, 4 locations, 3 knowledge documents, 4 resources. Temperature 78 C and smoke alert are explicit fixture values, not actual observations. Different scenario instances isolate observations; device state is derived from observations within selected incident.

Frontend: refined dark navy desktop workbench inspired by supplied reference, original brand mark, cyan/blue accents, 3 columns, collapsible process panel, custom SVG campus overview. Nine nav entries, pages have real interactions or honest milestone descriptions. Base app must function without model key/network.

Model probe is a separate script run by root; never auto-call on startup. Runtime config via environment. Save only sanitized probe outcome metadata to runtime directory. No key in frontend, git, docs, logs, command arguments or test output. No hidden reasoning in SSE/logs.
