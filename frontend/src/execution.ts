import {computed,ref,watch} from 'vue'
import {api} from './api'
import type {Point} from './situation'

export type ExecutionType='aerial_inspection'|'ground_inspection'|'remote_sensing'
export type ExecutionStatus='pending'|'dispatching'|'running'|'completed'|'failed'|'cancelled'
export type ExecutionReport={id:string;task_id:string;task_code:string;title:string;incident_id:string;source_run_id:string|null;evidence_snapshot_id:string|null;resource_id:string;resource_code:string;started_at:string;finished_at:string;generated_at:string;scope:string;summary:string;findings:string[];recommendations:string[];limitations:string[];verification_status:'requires_human_review';is_simulated:true}
export type ExecutionTask={id:string;code:string;title:string;task_type:ExecutionType;source_kind:'manual_demo'|'rule_assessment';source_label:string;source_run_id:string|null;evidence_snapshot_id:string|null;incident_id:string;incident_code?:string|null;incident_title:string;device_ids:string[];target_building_id:string;target_building_name:string;priority:'high'|'medium'|'low';risk_level:string;resource_id:string|null;resource_code:string|null;resource_name:string|null;status:ExecutionStatus;progress:number;created_at:string;updated_at:string;started_at:string|null;finished_at:string|null;dispatch_seconds:number;duration_seconds:number;image_id:string|null;route:Point[];position:Point|null;target_point:Point|null;patrol_id:string|null;parent_task_id:string|null;attempt:number;steps:{id:string;title:string;status:string;started_at:string|null;finished_at:string|null}[];logs:{id:string;sequence:number;at:string;kind:string;message:string}[];report:ExecutionReport|null;error:string|null;is_simulated:true}
export type ExecutionResource={id:string;code:string;name:string;type:'drone'|'robot'|'satellite';device_id:string|null;status:'available'|'busy'|'offline';online:boolean;current_task_id:string|null;current_task_code:string|null;area:string;capabilities:string[];battery:number|null;eligible:boolean;reason:string|null;is_simulated:true}
export const executionTypes:Record<ExecutionType,string>={aerial_inspection:'无人机巡检',ground_inspection:'地面巡检',remote_sensing:'模拟遥感核查'}
export const executionStatuses:Record<ExecutionStatus,string>={pending:'待执行',dispatching:'派发中',running:'执行中',completed:'已完成',failed:'执行失败',cancelled:'已取消'}
export const resourceTypes={drone:'空 · 无人机',robot:'地 · 机器人',satellite:'天 · 模拟遥感'}
export const executionActive=(task:ExecutionTask)=>['dispatching','running'].includes(task.status)
export const executionIcon=(type:ExecutionType|ExecutionResource['type'])=>type==='remote_sensing'||type==='satellite'?'signal':type==='ground_inspection'||type==='robot'?'device':'flow'
export function saveExecutionReport(report:ExecutionReport){const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`天亨-${report.task_code}-模拟执行报告.json`;a.click();URL.revokeObjectURL(url)}

const tasks=ref<ExecutionTask[]>([]),resources=ref<ExecutionResource[]>([]),failure=ref(''),loading=ref(false)
const selectedId=ref(localStorage.getItem('tq-execution-task')||'')
watch(selectedId,id=>{if(id)localStorage.setItem('tq-execution-task',id);else localStorage.removeItem('tq-execution-task')})
let activeRequests:Promise<void>|null=null,timer:ReturnType<typeof setTimeout>|undefined,subscribers=0,version=0
function upsert(task:ExecutionTask){version++;const index=tasks.value.findIndex(t=>t.id===task.id);if(index<0)tasks.value.unshift(task);else tasks.value[index]=task}
async function refresh(){if(activeRequests)return activeRequests;const token=version;loading.value=true;activeRequests=(async()=>{try{const [next,nextResources]=await Promise.all([api<ExecutionTask[]>('/execution-tasks'),api<ExecutionResource[]>('/execution-resources')]);if(token===version){tasks.value=next;resources.value=nextResources;failure.value=''}}catch(e){failure.value=(e as Error).message}finally{loading.value=false;activeRequests=null}})();return activeRequests}
async function tick(){await refresh();if(subscribers>0)timer=setTimeout(tick,tasks.value.some(executionActive)?900:4000)}
function start(){subscribers++;if(subscribers===1){clearTimeout(timer);void tick()}}
function stop(){subscribers=Math.max(0,subscribers-1);if(!subscribers)clearTimeout(timer)}
function select(id:string){selectedId.value=id}
export function useExecution(){return {tasks,resources,failure,loading,selectedId,selected:computed(()=>tasks.value.find(t=>t.id===selectedId.value)||null),refresh,upsert,select,start,stop}}
