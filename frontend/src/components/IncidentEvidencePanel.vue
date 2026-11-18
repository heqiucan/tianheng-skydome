<script setup lang="ts">
import {displayText} from '../api'
import {computed,onUnmounted,ref,watch} from 'vue'
import {api,label} from '../api'
import {evidenceTime,metricValue,type EvidenceContext,type EvidenceSnapshot,type EvidenceScope} from '../evidence'
import Icon from './Icon.vue'

const props=defineProps<{incidentId:string;sourceView:'overview'|'map'|'coordination';imageId:string|null}>()
const emit=defineEmits<{'open-snapshot':[snapshot:EvidenceSnapshot];'select-device':[id:string]}>()
const context=ref<EvidenceContext|null>(null),loading=ref(false),busy=ref(false),error=ref(''),scope=ref<EvidenceScope>('event_snapshot')
let generation=0
const devices=computed(()=>scope.value==='event_snapshot'?context.value?.devices:context.value?.current_devices)
async function load(){const token=++generation;context.value=null;scope.value='event_snapshot';loading.value=true;error.value='';try{const result=await api<EvidenceContext>(`/incidents/${encodeURIComponent(props.incidentId)}/context`);if(token===generation)context.value=result}catch(e){if(token===generation)error.value=(e as Error).message}finally{if(token===generation)loading.value=false}}
async function openSnapshot(){if(!context.value||busy.value)return;const token=generation;busy.value=true;error.value='';try{const snapshot=await api<EvidenceSnapshot>(`/incidents/${encodeURIComponent(props.incidentId)}/evidence-snapshots`,{source_view:props.sourceView,image_id:context.value.source_context.image_id===null?null:props.imageId});if(token===generation)emit('open-snapshot',snapshot)}catch(e){if(token===generation)error.value=(e as Error).message}finally{if(token===generation)busy.value=false}}
watch(()=>props.incidentId,()=>{busy.value=false;load()},{immediate:true})
onUnmounted(()=>{generation++})
</script>

<template>
 <div class="incident-evidence-panel">
  <p v-if="loading" class="panel-hint" role="status">正在查询事件与关联证据…</p>
  <div v-if="error" class="evidence-error" role="alert">{{displayText(error)}}<button class="text-button" @click="load">重新读取</button></div>
  <template v-if="context">
   <span class="risk-pill" :class="context.incident.risk_level">{{label(context.incident.risk_level)}}</span>
   <strong v-if="context.incident.code" class="event-display-code">{{context.incident.code}}</strong><p class="event-summary">{{displayText(context.incident.summary)}}</p>
   <dl class="incident-facts"><div><dt>事件编号</dt><dd class="evidence-id">{{context.incident.id}}</dd></div><div><dt>事件来源</dt><dd>{{displayText(context.incident.source.label)}}</dd></div><div><dt>发生时间</dt><dd>{{evidenceTime(context.incident.triggered_at)}}</dd></div><div><dt>区域与建筑</dt><dd>{{displayText(context.incident.building_name||'建筑待核实')}}<small>{{displayText(context.incident.location_name)}}</small></dd></div><div><dt>处理状态</dt><dd>{{label(context.incident.status)}}</dd></div></dl>
   <div class="evidence-scope-switch" role="group" aria-label="事件证据数据范围"><button :class="{active:scope==='event_snapshot'}" :aria-pressed="scope==='event_snapshot'" @click="scope='event_snapshot'">事件关联证据</button><button :class="{active:scope==='current_device_state'}" :aria-pressed="scope==='current_device_state'" @click="scope='current_device_state'">当前设备状态</button></div>
   <p class="evidence-scope-hint">{{scope==='event_snapshot'?'只使用该事件关联的记录；每项证据保留原始采样时间。':'与地图当前读数同源，可能晚于事件发生时间，不替代历史证据。'}} 全部为 模拟。</p>
   <article v-for="device in devices" :key="device.id" class="evidence-device-mini"><div><button class="text-button" @click="emit('select-device',device.id)">{{device.code}}</button><span class="status-badge" :class="device.status">{{label(device.status)}}</span></div><strong>{{displayText(device.name)}}</strong><div v-for="metric in device.metrics" :key="metric.observation_id" class="evidence-mini-metric"><span>{{metric.label}}</span><b>{{metricValue(metric)}}</b><details><summary>采样时间与来源</summary><small>{{evidenceTime(metric.observed_at)}} · {{label(metric.quality)}}</small><code>{{metric.observation_id}}</code><code>{{metric.incident_id}}</code><small>{{metric.data_scope}}</small></details></div><p v-if="!device.metrics.length" class="panel-hint">无可用记录，不能判断为正常。</p></article>
   <p v-if="!devices?.length" class="panel-hint">当前范围没有关联设备证据。</p>
   <p class="evidence-scope-hint">相关历史事件 {{context.history.length}} 起；将随本次证据一起保存。</p>
   <button class="primary-button evidence-start" :disabled="busy||loading" @click="openSnapshot"><Icon name="spark" :size="16"/>{{busy?'正在保存证据…':'发起研判 · 证据核查'}}</button>
   <p class="evidence-scope-hint">DAY 03 阶段一：保存证据快照并进入三工具规则核查。真实模型尚未接入，不会自动关闭告警。</p>
  </template>
 </div>
</template>
