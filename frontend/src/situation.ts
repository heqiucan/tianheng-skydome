import { computed, ref, watch } from 'vue'
import { api,type MetricReference } from './api'
import type {EvidenceMetric} from './evidence'
import type {ExecutionTask,ExecutionResource} from './execution'
export type Point = { x:number; y:number }
export type Anchor = Point & { image_id:string; note:string }
export type Selection = {kind:'building'|'device'|'incident';id:string}
export type MapImage = {id:string;title:string;url:string;width:number;height:number;description:string;source_url:string|null}
export type Space = {id:string;name:string;usage:string;area_sqm:number|null;floors_note:string;verification:string;anchor:Anchor|null;polygon:Point[];detail_image:string|null;source_note:string}
export type MapDevice = {id:string;code:string;name:string;type:string;building_id:string|null;floor:string;status:string;last_seen:string;alarm:boolean;anchor:Anchor|null;metrics:EvidenceMetric[];references?:MetricReference[];trend:{time:string;value:number}[];related_device_ids:string[];incident_ids:string[];battery:number|null;is_simulated:true}
export type MapIncident = {id:string;code?:string|null;title:string;building_id:string|null;device_ids:string[];risk_level:string;status:string;summary:string;triggered_at:string;anchor:Anchor|null;is_simulated:true}
export type Patrol = {id:string;device_id:string;target_building_id:string;image_id:string;route:Point[];status:'draft'|'running'|'completed';progress:number;created_at:string;started_at:string|null;duration_seconds:number;result:string|null;is_simulated:true}
export type MapTask = {source_selection?:Selection|null;id:string;instruction:string;action:string;source_view:'overview'|'map'|'coordination';image_id:string;building_id:string|null;device_ids:string[];incident_ids:string[];created_at:string;status:string;result:{title:string;summary:string;evidence:string[];recommendations:string[];limitations:string[]};is_simulated:true}
export type EvidenceCheck = {id:string;incident_id:string;evidence_snapshot_id:string;status:string;created_at:string;updated_at:string;error:string|null}
export type SituationData = {campus_name:string;mode:'DEMO';updated_at:string;images:MapImage[];spaces:Space[];devices:MapDevice[];incidents:MapIncident[];patrols:Patrol[];tasks:MapTask[];evidence_checks:EvidenceCheck[];execution_tasks:ExecutionTask[];execution_resources:ExecutionResource[];robot_task:{id:string;name:string;device_id:string;target_building_id:string;status:string;progress:number;is_simulated:true};satellite:{status:string;coverage:string;updated_at:string|null;note:string}}
export const layerOptions=[['buildings','建筑区域'],['temperature','温度传感器'],['smoke','烟雾传感器'],['camera','视频监控'],['fire','消防设备'],['drone','无人机'],['robot','地面机器人'],['incidents','风险事件'],['routes','巡检航线']]
export const typeNames:Record<string,string>={temperature:'温度传感器',smoke:'烟雾传感器',camera:'视频监控',fire:'消防设备',drone:'无人机',robot:'地面机器人'}
function restore(){try{const value=JSON.parse(localStorage.getItem('tq-situation-ui')||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{}}catch{return {}}}
const saved=restore()
const data=ref<SituationData|null>(null), loading=ref(false), failure=ref('')
const view=ref<'overview'|'map'|'coordination'>(['overview','map','coordination'].includes(saved.view)?saved.view:'overview')
const imageId=ref<string>(saved.imageId||'training-2026'), selection=ref<Selection|null>(saved.selection||null), focus=ref<Anchor|null>(null)
const layers=ref<Record<string,boolean>>(Object.fromEntries(layerOptions.map(([key])=>[key!,saved.layers?.[key!]!==false])))
const patrolId=ref<string>(saved.patrolId||'')
watch([view,imageId,selection,layers,patrolId],()=>localStorage.setItem('tq-situation-ui',JSON.stringify({view:view.value,imageId:imageId.value,selection:selection.value,layers:layers.value,patrolId:patrolId.value})),{deep:true})
async function refresh(quiet=false){if(!quiet)loading.value=true;try{data.value=await api<SituationData>('/situation');failure.value='';if(!data.value.images.some(i=>i.id===imageId.value))imageId.value=data.value.images[0]?.id||'';if(!patrolId.value)patrolId.value=data.value.patrols.find(p=>p.status==='running')?.id||''}catch(e){failure.value=(e as Error).message}finally{loading.value=false}}
function choose(item:Selection){selection.value=item;let anchor:Anchor|null|undefined;if(item.kind==='building')anchor=data.value?.spaces.find(s=>s.id===item.id)?.anchor;else if(item.kind==='device')anchor=data.value?.devices.find(s=>s.id===item.id)?.anchor;else anchor=data.value?.incidents.find(s=>s.id===item.id)?.anchor;if(anchor){imageId.value=anchor.image_id;focus.value={...anchor};if(item.kind==='building')layers.value.buildings=true;else if(item.kind==='incident')layers.value.incidents=true;else {const type=data.value?.devices.find(d=>d.id===item.id)?.type;if(type)layers.value[type]=true}}}
function restoreTask(task:MapTask){view.value=task.source_view;imageId.value=task.image_id;focus.value=null;if(task.source_selection)choose(task.source_selection);else if(task.source_selection===null||['campus','anomalies'].includes(task.action))selection.value=null;else if(task.incident_ids.length)choose({kind:'incident',id:task.incident_ids[0]!});else if(task.device_ids.length)choose({kind:'device',id:task.device_ids[0]!});else if(task.building_id)choose({kind:'building',id:task.building_id});else selection.value=null}
export function useSituation(){return {data,loading,failure,view,imageId,selection,focus,layers,patrolId,refresh,choose,restoreTask,image:computed(()=>data.value?.images.find(i=>i.id===imageId.value)),patrol:computed(()=>data.value?.patrols.find(p=>p.id===patrolId.value)||null)}}
