<script setup lang="ts">
import {displayText} from '../api'
import Icon from './Icon.vue'
import {time,label} from '../api'
import {useSituation,type MapTask} from '../situation'
const props=defineProps<{task:MapTask}>()
defineEmits<{'return-map':[];dismiss:[]}>()
const {data}=useSituation()
function download(){const url=URL.createObjectURL(new Blob([JSON.stringify(props.task,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`天亨-模拟研判-${props.task.id}.json`;a.click();URL.revokeObjectURL(url)}
</script>
<template>
 <div class="map-task-workbench">
  <div class="module-header"><div><span class="eyebrow">SKYDOME AGENT · SPATIAL CONTEXT</span><h2>地图关联任务</h2><p>从全域态势接收的上下文已保存，可追溯并返回原地图。</p></div><button class="outline-button" @click="$emit('return-map')"><Icon name="map" :size="15"/>返回地图</button></div>
  <div class="map-task-instruction">{{displayText(task.instruction)}}</div>
  <div class="context-grid"><div class="context-cell"><span>绑定建筑 ID</span><strong>{{data?.spaces.find(s=>s.id===task.building_id)?.name||(task.source_selection?'未绑定建筑（按所选对象分析）':'杭州校区全域')}}<br/>{{task.building_id||(task.source_selection?'object scope':'campus scope')}}</strong></div><div class="context-cell"><span>任务状态 / 来源视图</span><strong>{{label(task.status)}} · {{task.source_view==='overview'?'全域态势总览':task.source_view==='map'?'数字孪生地图':'空天地协同'}}<br/>{{time(task.created_at,true)}}</strong></div><div class="context-cell"><span>绑定设备 ID · {{task.device_ids.length}} 台</span><strong>{{task.device_ids.map(id=>`${data?.devices.find(d=>d.id===id)?.code||id} (${id})`).join('、')||'未绑定特定设备'}}</strong></div><div class="context-cell"><span>绑定事件 ID · {{task.incident_ids.length}} 起</span><strong>{{task.incident_ids.map(id=>`${data?.incidents.find(i=>i.id===id)?.title||'关联事件'} (${id})`).join('、')||'无关联演示事件'}}</strong></div></div>
  <div class="map-task-id">任务 ID：{{task.id}} · 底图 ID：{{task.image_id}}</div>
  <div class="scope-note"><Icon name="info" :size="15"/>模拟 确定性规则研判 · 基于后台统一演示数据真实查询并保存，不代表大模型自主分析或真实学校安全结论。</div>
  <article class="assessment"><span class="demo-badge">模拟 分析结果</span><h3>{{displayText(task.result.title)}}</h3><p>{{displayText(task.result.summary)}}</p><h4>关联证据</h4><ul><li v-for="(item,index) in task.result.evidence" :key="index">{{displayText(item)}}</li></ul><h4>核查建议</h4><ul><li v-for="(item,index) in task.result.recommendations" :key="index">{{displayText(item)}}</li></ul><div class="uncertainty"><strong>待核实与适用范围</strong><p v-for="(item,index) in task.result.limitations" :key="index">{{displayText(item)}}</p></div></article>
  <div class="map-task-back"><button class="primary-button" @click="$emit('return-map')"><Icon name="map" :size="16"/>返回地图并恢复上下文</button><button class="outline-button" @click="download"><Icon name="download" :size="16"/>下载 模拟 研判记录</button><button class="text-button" @click="$emit('dismiss')">切回基础核查工作台</button></div>
 </div>
</template>
