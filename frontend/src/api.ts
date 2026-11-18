export type Incident = {id:string;code?:string|null; title:string; location_id:string; location_name:string; event_type:string; status:string; risk_level:string; summary:string; triggered_at:string; is_simulated:boolean}
export type MetricReference={kind:string;rule_id:string;rule_version:string;reference_label:string;normal_condition:{operator:string;value:number}|null;warning_condition:{operator:string;value:number}|null;unit:string;source_kind:'demo_rule';source_label:string;is_simulated:true}
export type TemperatureTrend={device_id:string;device_code:string;sample_count:number;started_at:string|null;ended_at:string|null;first_value:number|null;latest_value:number|null;delta:number|null;duration_minutes:number|null;slope_per_minute:number|null;direction:'rising'|'falling'|'stable'|'insufficient';observation_ids:string[]}
export type RegionalEvidence={device_id:string;device_code:string;kind:string;observation_id:string;observed_at:string;value:number|null;unit:string;quality:string;interpretation:string;data_scope:'event_snapshot'}
export type Location = {id:string;name:string;parent_id:string|null;kind:string;x:number;y:number}
export type Device = {id:string;code?:string;name:string;type:string;location_id:string;location_name:string;status:string;last_seen:string;is_simulated:boolean}
export type Observation = {id:string;device_id:string;incident_id:string;kind:string;value:number|null;unit:string;observed_at:string;quality:string;description:string}
export type KnowledgeDocument = {id:string;title:string;version:string;category:string;tags:string[];content:string;is_demo:boolean}
export type Resource = {id:string;name:string;role:string;location_name:string;status:string;is_simulated:boolean}
export type Message = {id:string;role:string;content:string;created_at:string}
export type Conversation = {id:string;title:string;created_at:string;messages?:Message[]}
export type RiskResult = {level:string;title:string;evidence:{label:string;value:unknown;source_id:string}[];reasons:string[];uncertainties:string[];recommendations:string[];rule_version:string;is_demo:boolean;scope:string;analysis_kind?:'rule_based';temperature_trends?:TemperatureTrend[];regional_evidence?:RegionalEvidence[];risk_judgment?:string;possible_causes?:string[];report_id?:string}
export type Run = {evidence_snapshot_id?:string|null;id:string;conversation_id:string;incident_id:string;instruction:string;mode:string;status:string;stage:string;created_at:string;started_at:string|null;finished_at:string|null;summary:string|null;result:RiskResult|null;error:string|null}
export type RunEvent = {id:string;run_id:string;sequence:number;type:string;stage:string;status:string;message:string;tool_name:string|null;duration_ms:number|null;data:Record<string,unknown>|null;created_at:string}
export type SystemStatus = {app_name:string;version:string;milestone:string;mode:string;model:{provider:string;model:string;configured:boolean;verified:boolean;status:string;message:string};capabilities:Record<string,unknown>;database:string}
export async function api<T>(path:string, body?:unknown, method?:string):Promise<T> {
 const response=await fetch('/api/v1'+path,{method:method??(body===undefined?'GET':'POST'),headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
 if(!response.ok){const error=await response.json().catch(()=>({detail:`请求失败 (${response.status})`})); throw new Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail))}
 return response.json()
}
export const statusLabels:Record<string,string>={standby:'待命',queued:'等待执行',running:'执行中',completed:'已完成',cancelled:'已停止',failed:'执行失败',interrupted:'执行中断',online:'在线',offline:'离线',alarm:'告警',alert:'告警',warning:'异常',normal:'正常',high:'高风险',medium:'中风险',low:'低风险',unknown:'待核实',unassessed:'待研判',insufficient:'证据不足',insufficient_evidence:'证据不足',active:'待核查',open:'待核查',available:'可用',busy:'忙碌',planning:'任务规划',collecting:'数据核查',assessing:'风险研判',pending:'待处理',draft:'待确认',simulated:'模拟运行',in_progress:'处理中',acknowledged:'已接收',resolved:'已处理'}
export function displayText(value:unknown):string{return String(value??'').replace(/天穹/g,'天亨').replace(/(?<![A-Za-z0-9_-])DEMO(?![A-Za-z0-9_-])/gi,'模拟')}
export function ruleVersionText(value:string|undefined):string{const match=value?.match(/^demo-risk-v(.+)$/i);return match?`模拟规则 v${match[1]}`:displayText(value)}
export const label=(value:string|null|undefined)=>value?displayText(statusLabels[value]??value):'—'
export const time=(value:string|null|undefined,full=false)=>value?new Date(value).toLocaleString('zh-CN',full?{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}:{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'—'
