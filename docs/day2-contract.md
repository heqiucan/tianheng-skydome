# Day 2 API / UI implementation contract

All data DEMO. Maps use supplied planning renders, never described as live imagery or true 3D. All below endpoints under /api/v1. Existing Day1 APIs retained.

GET /situation -> {campus_name,mode:'DEMO',updated_at,images:MapImage[],spaces:Space[],devices:MapDevice[],incidents:MapIncident[],patrols:Patrol[],tasks:MapTask[],robot_task:RobotTask,satellite:{status,coverage,updated_at,note}}

Point={x:number,y:number} normalized 0..1. Anchor=Point & {image_id:string,note:string}.
MapImage={id,title,url,width,height,description,source_url:string|null}
Space={id,name,usage,area_sqm:number|null,floors_note,verification,anchor:Anchor|null,polygon:Point[],detail_image:string|null,source_note}
MapDevice={id,code,name,type,building_id:string|null,floor,status,last_seen,alarm:boolean,anchor:Anchor|null,metrics:{label,value:number|string,unit:string}[],trend:{time,value:number}[],related_device_ids:string[],incident_ids:string[],battery:number|null,is_simulated:true}
Types: temperature,smoke,camera,fire,drone,robot. Status online/offline/alarm. All device anchors DEMO deployments.
MapIncident={id,title,building_id:string|null,device_ids:string[],risk_level,status,summary,triggered_at,anchor:Anchor|null,is_simulated:true}

SourceSelection={kind:'building'|'device'|'incident',id:string}
POST /situation/tasks {instruction,action:'campus'|'building'|'anomalies'|'patrol'|'report',source_view:'overview'|'map'|'coordination',image_id,building_id:string|null,device_ids:string[],incident_ids:string[],source_selection?:SourceSelection|null} -> MapTask
MapTask={id,instruction,action,source_view,image_id,building_id,device_ids,incident_ids,source_selection:SourceSelection|null,created_at,status,result:{title,summary,evidence:string[],recommendations:string[],limitations:string[]},is_simulated:true}
GET /situation/tasks/{id} -> MapTask. Server persists context and generates explicitly labeled deterministic DEMO assessment from unified snapshot, NOT LLM orchestration. No implicit binding to an unrelated Day1 incident. Frontend emits open-task(task); App opens workbench, displays task context/result and return-map action; persistent selected task ID in URL/localStorage.

source_selection preserves the exact object selected when opening the task. It defaults to null, including when reading older persisted tasks. The server validates object existence, membership in the resolved task scope, consistency with building_id, and image_id when the object has an anchor. Return-map must prefer source_selection over inferred first device/incident IDs. Do not replace a selected device with an associated incident merely because the incident appears first in the task context.

RobotTask={id,name,device_id,target_building_id,status:'standby',progress:0,is_simulated:true}. Current robot_task comes from the shared backend fixture definition: a clearly labeled DEMO standby ground patrol linked to ROBOT-001 and loc-training. The client displays its task name and progress; it does not invent a separate numeric status. Robot execution/control is not implemented. Satellite updated_at is null until a real image timestamp exists; no actual satellite feed is connected.

POST /situation/patrols {device_id,target_building_id} -> Patrol (draft). Server generates route in target image, validates positioned target and drone online.
POST /situation/patrols/{id}/confirm {} -> Patrol (running; idempotent)
GET /situation/patrols/{id} -> Patrol (derive progress from server start time, persist completion)
Patrol={id,device_id,target_building_id,image_id,route:Point[],status:'draft'|'running'|'completed',progress:number (0..100),created_at,started_at:string|null,duration_seconds:number,result:string|null,is_simulated:true}
Repeat creates NEW mission. Draft must be visibly confirmed. Browser animates between points using progress; server is authoritative. GET /situation updates patrol state. Duration 12 seconds DEMO (not physical estimate).

Backend owner: backend/app/{situation.py,main.py,fixtures.py,database.py}, backend/tests/test_day2.py. Preserve Day1 test semantics and seed migration idempotence. Add display code aliases for known IDs to Day1 devices response. Keep device IDs stable.

Frontend owner: frontend/src/{App.vue,api.ts,situation.ts,components/SituationView.vue,day2.css}, vite.config.ts. Use publicDir:'../public'. SituationView emits open-task(task) and provides initialSelection from task return. Root map component imports types from ../situation.

Map component owner: frontend/src/components/CampusImageMap.vue. Props: image:MapImage, spaces:Space[],devices:MapDevice[],incidents:MapIncident[],layers:Record<string,boolean>,selected:{kind:'building'|'device'|'incident',id:string}|null,patrol:Patrol|null,focus:Anchor|null. Emits select({kind,id}). Layer keys buildings,temperature,smoke,camera,fire,drone,robot,incidents,routes. Image and SVG geometry share viewBox (0 0 width height); multiply normalized coordinate by image dims. Zoom/pan/fullscreen/reset independent map controls. Focus must change camera center. Accessible role/button names on interactive SVG objects. No external heavy dependencies.

Spaces/images supplied by root at backend/app/map_catalog.json. It is provenance/visual geometry configuration only; business readings and statuses come from backend DB. Default image training-2026. Three positioned spaces: loc-training (training image),loc-canopy(training image),loc-dorm(east image); loc-library retained as unverified building with no coordinates. loc-training-2f is explicitly DEMO floor under training.
