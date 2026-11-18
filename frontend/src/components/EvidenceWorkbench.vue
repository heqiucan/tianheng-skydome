<script setup lang="ts">
import {displayText} from '../api'
import {pollRunProgress} from '../runProgress'
import {computed,onUnmounted,ref,watch} from 'vue'
import {api,label,type Conversation,type RunEvent} from '../api'
import {evidenceTime,metricValue,type EvidenceRun,type EvidenceSnapshot,type EvidenceScope} from '../evidence'
import Icon from './Icon.vue'
import {matchesAssessment} from '../assessmentSelection'
import {useExecution,executionTypes,executionStatuses,type ExecutionTask,type ExecutionType} from '../execution'
const props=defineProps<{snapshot:EvidenceSnapshot;preparingDemo?:boolean;demoError?:string}>()
const emit=defineEmits<{'return-map':[];dismiss:[];'run-changed':[];'open-execution':[task:ExecutionTask];'run-selected':[run:EvidenceRun|null];'show-report':[];'prepare-demo':[]}>()
const execution=useExecution(),creatingTask=ref(false),taskError=ref(''),taskType=ref<ExecutionType>('aerial_inspection')
const linkedTasks=computed(()=>execution.tasks.value.filter(task=>task.source_run_id===run.value?.id))
async function createExecution(){if(!run.value||run.value.status!=='completed'||creatingTask.value)return;const token=generation,runId=run.value.id;creatingTask.value=true;taskError.value='';try{const task=await api<ExecutionTask>('/execution-tasks/from-run',{run_id:runId,task_type:taskType.value});execution.upsert(task);if(token===generation&&run.value?.id===runId)emit('open-execution',task)}catch(e){if(token===generation)taskError.value=(e as Error).message}finally{if(token===generation)creatingTask.value=false}}
const run=ref<EvidenceRun|null>(null),events=ref<RunEvent[]>([]),busy=ref(false),restoring=ref(false),error=ref(''),streamNotice=ref(''),scope=ref<EvidenceScope>('event_snapshot')
const instruction=ref(''),historyOpen=ref(false)
let stream:{close:()=>void}|null=null,generation=0,lastAppliedSequence=0
const running=computed(()=>!!run.value&&['queued','running'].includes(run.value.status))
const result=computed(()=>run.value?.result)
const devices=computed(()=>scope.value==='event_snapshot'?props.snapshot.devices:props.snapshot.current_devices)
const completedTools=computed(()=>events.value.filter(e=>e.type==='tool_result'&&e.status!=='failed').length)
const toolNames:Record<string,string>={query_sensor_data:'监测数据查询',query_device_status:'关联设备查询',query_event_history:'历史事件检索'}
function remember(value:EvidenceRun){localStorage.setItem(`tq-evidence-run:${props.snapshot.snapshot_id}`,value.id)}
function subscribe(value:EvidenceRun,token:number){
 stream?.close();events.value=[];lastAppliedSequence=0;streamNotice.value=''
 if(import.meta.env.VITE_PROGRESS_TRANSPORT==='poll'){
  stream=pollRunProgress(value.id,{onNotice:message=>{if(token===generation&&run.value?.id===value.id)streamNotice.value=message},onUpdate:(batch,latest)=>{
   if(token!==generation||run.value?.id!==value.id)return
   for(const event of batch)if(!events.value.some(item=>item.sequence===event.sequence))events.value.push(event)
   events.value.sort((a,b)=>a.sequence-b.sequence)
   run.value=latest as EvidenceRun
   if(batch.some(event=>event.type==='terminal'))emit('run-changed')
  }})
  return
 }
 const active=new EventSource(`/api/v1/runs/${encodeURIComponent(value.id)}/events`);stream=active
 active.addEventListener('update',async raw=>{
  if(token!==generation||run.value?.id!==value.id)return
  try{
   const event=JSON.parse((raw as MessageEvent).data) as RunEvent
   if(!events.value.some(item=>item.sequence===event.sequence))events.value.push(event)
   events.value.sort((a,b)=>a.sequence-b.sequence)
   const latest=await api<EvidenceRun>(`/runs/${encodeURIComponent(value.id)}`)
   if(token!==generation||run.value?.id!==value.id)return
   if(event.sequence>=lastAppliedSequence){run.value=latest;lastAppliedSequence=event.sequence}
   streamNotice.value=''
   if(event.type==='terminal'){active.close();emit('run-changed')}
  }catch(e){if(token===generation)error.value=(e as Error).message}
 })
 active.onerror=()=>{if(token!==generation)return;if(run.value&&!['queued','running'].includes(run.value.status)){active.close()}else{streamNotice.value='过程连接暂时中断，正在尝试恢复；已保存的查询不会丢失。'}}
}
async function restore(){
 const token=++generation;stream?.close();run.value=null;events.value=[];error.value='';streamNotice.value='';restoring.value=true;busy.value=false;scope.value='event_snapshot'
 creatingTask.value=false;taskError.value=''
 const snapshotId=props.snapshot.snapshot_id,incidentId=props.snapshot.incident.id
 const matchesSnapshot=(value:EvidenceRun|undefined)=>matchesAssessment(props.snapshot,value)
 instruction.value=`核查${props.snapshot.incident.title}的监测数据、关联设备和历史记录，说明证据与信息缺口。`
 try{
  const savedId=localStorage.getItem(`tq-evidence-run:${snapshotId}`)
  let saved:EvidenceRun|undefined
  if(savedId){try{saved=await api<EvidenceRun>(`/runs/${encodeURIComponent(savedId)}`)}catch{/* The server list can recover a stale local pointer. */}}
  if(token!==generation)return
  if(!matchesSnapshot(saved)){const all=await api<EvidenceRun[]>('/runs');saved=all.find(matchesSnapshot)}
  if(token!==generation)return
  if(saved){run.value=saved;instruction.value=saved.instruction;remember(saved);subscribe(saved,token)}
 }catch(e){if(token===generation)error.value=(e as Error).message}finally{if(token===generation)restoring.value=false}
}
async function execute(){
 if(busy.value||running.value||restoring.value||!instruction.value.trim())return
 const token=generation;busy.value=true;error.value=''
 try{
  const conversation=await api<Conversation>('/conversations',{title:`证据核查 · ${props.snapshot.incident.title}`})
  if(token!==generation)return
  const created=await api<EvidenceRun>('/runs',{conversation_id:conversation.id,incident_id:props.snapshot.incident.id,instruction:instruction.value.trim(),evidence_snapshot_id:props.snapshot.snapshot_id})
  if(token!==generation)return
  run.value=created;remember(created);subscribe(created,token);emit('run-changed')
 }catch(e){if(token===generation)error.value=(e as Error).message}finally{if(token===generation)busy.value=false}
}
async function cancel(){if(!run.value||busy.value)return;const token=generation;const id=run.value.id;busy.value=true;try{const cancelled=await api<EvidenceRun>(`/runs/${encodeURIComponent(id)}/cancel`,{});if(token===generation){run.value=cancelled;subscribe(cancelled,token);emit('run-changed')}}catch(e){if(token===generation)error.value=(e as Error).message}finally{if(token===generation)busy.value=false}}
function reconnect(){if(run.value)subscribe(run.value,generation)}
function download(){const url=URL.createObjectURL(new Blob([JSON.stringify({scope:'DAY 03 阶段一证据与规则核查记录，非真实模型研判报告',snapshot:props.snapshot,run:run.value,events:events.value},null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`天亨-证据核查-${props.snapshot.snapshot_id}.json`;a.click();URL.revokeObjectURL(url)}
watch(()=>run.value,value=>{if(value)emit('run-selected',value)})
watch(()=>props.snapshot.snapshot_id,restore,{immediate:true})
onUnmounted(()=>{generation++;stream?.close()})
</script>

<template>
 <div class="evidence-workbench">
  <div class="demo-chain-entry"><div><strong>EVT-008 · 温度异常演示链路</strong><p>准备独立场景并定位实训基地；已有证据和运行记录保持不变。</p></div><button class="outline-button" :disabled="preparingDemo" @click="emit('prepare-demo')">{{preparingDemo?'正在准备…':'准备 EVT-008 演示链路'}}</button><p v-if="demoError" class="evidence-error" role="alert">{{displayText(demoError)}}</p></div>
  <div class="evidence-header"><div><span class="eyebrow">SKYDOME · EVENT EVIDENCE</span><h2>事件证据核查</h2><p>{{snapshot.incident.code?snapshot.incident.code+' · ':''}}{{displayText(snapshot.incident.title)}}</p></div><button class="outline-button" @click="emit('return-map')"><Icon name="map" :size="16"/>返回地图事件</button></div>
  <div class="evidence-mode-note"><Icon name="info" :size="17"/><span><strong>模拟 · DAY 03 阶段一</strong> 后端实际查询已保存的证据，使用固定三工具流程和演示规则。真实智谱模型尚未接入。</span></div>
  <div class="evidence-summary"><div><small>事件编号 / 来源</small><strong>{{snapshot.incident.id}}</strong><span>{{displayText(snapshot.incident.source.label)}}</span></div><div><small>目标建筑 / 区域</small><strong>{{displayText(snapshot.incident.building_name||'建筑待核实')}}</strong><span>{{displayText(snapshot.incident.location_name)}}</span></div><div><small>事件时间 / 状态</small><strong>{{evidenceTime(snapshot.incident.triggered_at)}}</strong><span>{{label(snapshot.incident.status)}} · {{label(snapshot.incident.risk_level)}}（保存时）</span></div><div><small>证据关联</small><strong>{{snapshot.devices.length}} 台设备 · {{snapshot.observations.length}} 条记录</strong><span>{{snapshot.history.length}} 起相关历史事件</span></div></div>
  <details class="snapshot-provenance"><summary>证据快照 {{snapshot.snapshot_id}} · {{evidenceTime(snapshot.captured_at)}} 保存</summary><p>快照内容已持久化，后续读数变化不会改写这份记录。工具输出必须引用同一个快照。</p><code>校验摘要：{{snapshot.checksum}}</code><code>事件：{{snapshot.incident.id}} · 底图：{{snapshot.source_context.image_id||'待核实'}} · 口径：event_snapshot</code></details>
  <div v-if="error" class="evidence-error" role="alert">{{displayText(error)}}<button class="text-button" :disabled="busy" @click="restore">重新读取已保存记录</button></div>
  <section class="evidence-query-box"><div><h3>核查目标</h3><span class="subtle-tag">固定查询流程 · 规则演示</span></div><textarea v-model="instruction" aria-label="证据核查目标" :disabled="running||busy||restoring" rows="2" maxlength="2000"></textarea><div class="evidence-query-actions"><span>{{restoring?'正在恢复保存记录…':running?'查询正在执行，过程来自后端事件流。':run?`最近核查：${label(run.status)}`:'证据已保存，等待执行查询。'}}</span><button v-if="running" class="outline-button" :disabled="busy" @click="cancel">停止本次核查</button><button class="primary-button" :disabled="busy||running||restoring||!instruction.trim()" @click="execute"><Icon name="spark" :size="16"/>{{busy?'正在提交…':run?'重新执行三项查询（规则演示）':'执行三项查询（规则演示）'}}</button></div></section>
  <div class="evidence-work-grid">
   <section class="evidence-card-panel"><div class="evidence-card-heading"><h3>可追溯的关联证据</h3><span class="demo-badge">模拟</span></div><div class="evidence-scope-switch" role="group" aria-label="工作台证据范围"><button :class="{active:scope==='event_snapshot'}" :aria-pressed="scope==='event_snapshot'" @click="scope='event_snapshot'">事件关联证据</button><button :class="{active:scope==='current_device_state'}" :aria-pressed="scope==='current_device_state'" @click="scope='current_device_state'">保存时的当前状态</button></div><p class="evidence-scope-hint">{{scope==='event_snapshot'?'本次三工具核查使用这份事件证据；采样时间以每条记录为准。':'这些是快照保存时的设备最新状态，仅供对照。它们不是现在的实时读数，也不替代本次核查证据。'}}</p>
    <article v-for="device in devices" :key="device.id" class="evidence-device-card"><div class="evidence-device-title"><div><strong>{{device.code}} · {{displayText(device.name)}}</strong><small>{{device.id}}</small></div><span class="status-badge" :class="device.status">{{label(device.status)}}</span></div><div v-for="metric in device.metrics" :key="metric.observation_id" class="evidence-reading"><div><span>{{metric.label}}</span><strong>{{metricValue(metric)}}</strong></div><small>{{evidenceTime(metric.observed_at)}} · 数据质量 {{label(metric.quality)}}</small><code>{{metric.observation_id}}</code><details><summary>完整来源</summary><code>事件 {{metric.incident_id}}</code><code>设备 {{device.id}}</code><code>范围 {{metric.data_scope}}</code></details></div><p v-if="!device.metrics.length" class="panel-hint">暂无观测，不作为正常证据。</p></article>
    <p v-if="!devices.length" class="panel-hint">此范围没有关联设备。</p>
    <button class="text-button evidence-history-toggle" @click="historyOpen=!historyOpen">{{historyOpen?'收起':'查看'}}相关历史事件（{{snapshot.history.length}}）</button><div v-if="historyOpen" class="evidence-history-list"><article v-for="item in snapshot.history" :key="item.id"><strong>{{displayText(item.title)}}</strong><span>{{evidenceTime(item.triggered_at)}} · {{label(item.risk_level)}}</span><code>{{item.id}}</code></article><p v-if="!snapshot.history.length" class="panel-hint">快照中没有更早的同区域相关事件。</p></div>
   </section>
   <div class="evidence-process-column"><section class="evidence-card-panel"><div class="evidence-card-heading"><h3>真实工具执行记录</h3><span>{{completedTools}} / 3</span></div><p v-if="!run" class="panel-hint">执行后显示工具名称、状态、耗时及实际返回值。</p><template v-if="run"><p class="evidence-run-id">{{run.id}}</p><span class="status-badge" :class="run.status">{{label(run.status)}}</span><p v-if="run.error" class="evidence-error">{{displayText(run.error)}}</p><div v-if="streamNotice" class="evidence-error" role="status">{{streamNotice}}<button class="text-button" @click="reconnect">重连过程记录</button></div><details v-for="item in events" :key="item.id" class="evidence-log-entry"><summary><i :class="item.status"></i><span>{{displayText(item.tool_name?toolNames[item.tool_name]||item.tool_name:item.message)}}</span><small>{{item.type==='tool_result'?'查询返回':label(item.status)}}{{item.duration_ms!==null?` · ${item.duration_ms.toFixed(1)} ms`:''}}</small></summary><p>{{displayText(item.message)}}</p><small>{{evidenceTime(item.created_at)}} · #{{item.sequence}}</small><small v-if="item.data">原始接口记录（保留技术标识）</small><pre v-if="item.data">{{JSON.stringify(item.data,null,2)}}</pre></details></template></section>
    <section v-if="result" class="evidence-card-panel evidence-result" aria-label="证据规则核查结果"><div class="evidence-card-heading"><h3>保存时的规则核查结果</h3><span class="risk-pill" :class="result.level">{{label(result.level)}}</span></div><h3>{{displayText(result.title)}}</h3><ul><li v-for="reason in result.reasons" :key="reason">{{displayText(reason)}}</li></ul><h4>关联依据</h4><div v-for="item in result.evidence" :key="item.source_id" class="result-evidence"><strong>{{item.label}} · {{item.value}}</strong><code>{{item.source_id}}</code></div><h4>信息缺口与不确定性</h4><ul><li v-for="item in result.uncertainties" :key="item">{{displayText(item)}}</li></ul><h4>后续核查建议</h4><ul><li v-for="item in result.recommendations" :key="item">{{displayText(item)}}</li></ul><p class="evidence-scope-hint">本次核查未调用模型；可在下方创建模拟执行任务。温度异常不等于已确认火灾。</p></section>
   </div>
  </div>
  <section v-if="run?.status==='completed'&&result" class="execution-followup"><h3>从规则核查进入协同执行</h3><p>根据本次已保存证据创建演示任务；来源为规则核查，启动执行需要在任务中心选择资源并确认。</p><div v-if="taskError" class="execution-error" role="alert">{{displayText(taskError)}}</div><div class="execution-action-row"><select v-model="taskType" aria-label="从核查生成的执行任务类型" :disabled="creatingTask"><option v-for="(name,type) in executionTypes" :key="type" :value="type">{{name}}</option></select><button class="primary-button" :disabled="creatingTask" @click="createExecution"><Icon name="plus" :size="16"/>{{creatingTask?'正在创建…':'根据规则核查创建执行任务'}}</button></div><p class="execution-muted">相同核查与任务类型重复点击会打开原任务，不重复派发。模拟执行完成后仍需人工复核。</p><button v-for="task in linkedTasks" :key="task.id" class="execution-linked-task" @click="emit('open-execution',task)"><span>{{task.code}} · {{displayText(task.title)}}<small>{{task.resource_code||'资源待分配'}} · {{displayText(task.report?'已有执行报告，待人工复核':task.target_building_name)}}</small></span><span class="execution-status" :class="task.status">{{executionStatuses[task.status]}}</span><b>{{Math.round(task.progress)}}%</b><Icon name="chevron" :size="14"/></button></section>
  <div class="evidence-bottom-actions"><button v-if="run?.status==='completed'" class="primary-button" @click="emit('show-report')"><Icon name="file" :size="15"/>查看结构化规则研判报告</button><button class="primary-button" @click="emit('return-map')">返回地图并定位原事件</button><button class="outline-button" :disabled="running||restoring" @click="download"><Icon name="download" :size="16"/>保存证据核查记录</button><button class="text-button" @click="emit('dismiss')">切回基础核查工作台</button></div>
 </div>
</template>
