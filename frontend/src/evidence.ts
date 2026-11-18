import type { Incident, Observation, Run, MetricReference, RiskResult } from './api'

export type EvidenceScope = 'event_snapshot' | 'current_device_state'
export type EvidenceMetric = {kind:string;label:string;value:number|string|null;unit:string;observation_id:string;observed_at:string;incident_id:string;quality:string;data_scope:EvidenceScope}
export type EvidenceDevice = {id:string;code:string;name:string;type:string;location_id:string;status:string;last_seen:string|null;is_simulated:true;metrics:EvidenceMetric[];references?:MetricReference[]}
export type EvidenceObservation = Observation & {observation_id:string;data_scope:EvidenceScope}
export type EvidenceIncident = Incident & {source:{kind:string;label:string};building_id:string|null;building_name:string|null;device_ids:string[]}
export type EvidenceContext = {incident:EvidenceIncident;data_scope:'event_snapshot';devices:EvidenceDevice[];observations:EvidenceObservation[];current_devices:EvidenceDevice[];history:Incident[];references?:MetricReference[];source_context:{source_view:'overview'|'map'|'coordination';image_id:string|null;selection:{kind:'incident'|'device';id:string}};is_simulated:true}
export type AssessmentReport={id:string;run_id:string;incident_id:string;incident_code:string|null;evidence_snapshot_id:string|null;title:string;created_at:string;analysis_kind:'rule_based';rule_version:string;incident:EvidenceIncident;devices:EvidenceDevice[];observations:EvidenceObservation[];references:MetricReference[];assessment:RiskResult;source_context:EvidenceContext['source_context'];limitations:string[];is_simulated:true}
export type DeviceAnalysisContext={device:EvidenceDevice;related_incidents:Incident[];selected_incident_id:string|null;recommended_evidence_snapshot_id:string|null;source_selection:{kind:'device';id:string};can_analyze:boolean;reason:string|null}
export type DemoScenario={incident_id:string;incident_code:'EVT-008';device_id:'dev-temp-01';device_code:'TEMP-008';building_id:'loc-training';resource_id:'UAV-003';task_code:'TASK-008';root_task_id:string|null;is_simulated:true}
export type EvidenceSnapshot = EvidenceContext & {snapshot_id:string;captured_at:string;checksum:string}
export type EvidenceRun = Run & {evidence_snapshot_id:string|null}
export const scopeName = (scope:EvidenceScope) => scope==='event_snapshot'?'事件关联证据':'当前设备状态'
export function metricValue(metric:EvidenceMetric):string {
 if(metric.value===null)return '未知'
 if(typeof metric.value==='number'&&metric.kind==='smoke_alarm')return metric.value===1?'触发':'未触发'
 if(typeof metric.value==='number'&&metric.kind==='connectivity')return metric.value===1?'在线':'离线'
 if(typeof metric.value==='number'&&metric.kind==='camera_event')return metric.value===1?'有异常记录':'无异常记录'
 return `${metric.value}${metric.unit}`
}
export const evidenceTime = (value:string|null|undefined) => value?new Date(value).toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'无记录'
