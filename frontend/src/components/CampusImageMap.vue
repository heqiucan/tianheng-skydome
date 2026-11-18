<script setup lang="ts">
import {displayText} from '../api'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Icon from './Icon.vue'
import type { MapImage, Space, MapDevice, MapIncident, Patrol, Anchor } from '../situation'
import { cameraBounds, clamp, pointAlongRoute } from '../mapGeometry'
import {executionStatuses,type ExecutionTask,type ExecutionResource} from '../execution'

type Selection = { kind: 'building' | 'device' | 'incident'; id: string }
const props = defineProps<{
  image: MapImage
  spaces: Space[]
  devices: MapDevice[]
  incidents: MapIncident[]
  layers: Record<string, boolean>
  selected: Selection | null
  patrol: Patrol | null
  focus: Anchor | null
  executionMission?: ExecutionTask | null
  executionResources?: ExecutionResource[]
}>()
const emit = defineEmits<{ select: [selection: Selection] }>()
const container = ref<HTMLElement | null>(null), svg = ref<SVGSVGElement | null>(null)
const zoom = ref(1), center = ref({ x: props.image.width / 2, y: props.image.height / 2 })
const viewport = ref({ width: 800, height: 500 }), isFullscreen = ref(false), dragging = ref(false)
const fallbackFullscreen = ref(false)
const imageError = ref(false), fullscreenError = ref(''), hover = ref(''), animationNow = ref(Date.now())
let resizeObserver: ResizeObserver | null = null, animationFrame = 0
let dragStart: { id: number; x: number; y: number; centerX: number; centerY: number; scale: number } | null = null
let dragged = false, suppressClickUntil = 0
let progressBaseline = { id: '', progress: 0, at: performance.now() }

const bounds = computed(() => ({ width: props.image.width / zoom.value, height: props.image.height / zoom.value }))
const viewBox = computed(() => `${center.value.x - bounds.value.width / 2} ${center.value.y - bounds.value.height / 2} ${bounds.value.width} ${bounds.value.height}`)
const unitsPerPixel = computed(() => Math.max(bounds.value.width / Math.max(viewport.value.width, 1), bounds.value.height / Math.max(viewport.value.height, 1)))
const validAnchor = (anchor: Anchor | null | undefined) => !!anchor && anchor.image_id === props.image.id
const visibleSpaces = computed(() => props.layers.buildings ? props.spaces.filter(space => validAnchor(space.anchor)) : [])
const visibleDevices = computed(() => props.devices.filter(device => props.layers[device.type] && (validAnchor(device.anchor) || device.id === activePatrol.value?.device_id)))
const visibleIncidents = computed(() => props.layers.incidents ? props.incidents.filter(incident => validAnchor(incident.anchor)) : [])
const activeExecution = computed(()=>props.executionMission?.image_id===props.image.id?props.executionMission:null)
const activePatrol = computed(() => {
 if(props.executionMission){const task=activeExecution.value;if(!task||task.task_type==='remote_sensing'||!task.route.length)return null;const resource=props.executionResources?.find(r=>r.id===task.resource_id);return {id:task.id,device_id:resource?.device_id||'',image_id:task.image_id,route:task.route,status:task.status,progress:task.progress,duration_seconds:task.duration_seconds}}
 return props.patrol?.image_id === props.image.id ? props.patrol : null
})
const missionLabel=computed(()=>activeExecution.value?`${activeExecution.value.code} · ${executionStatuses[activeExecution.value.status]}`:activePatrol.value?.status==='draft'?'待确认路线':activePatrol.value?.status==='completed'?'模拟巡检完成':'模拟巡检中')
function deviceDisplayCode(device:MapDevice){const resource=props.executionResources?.find(item=>item.device_id===device.id);return resource?`${resource.code} / ${device.code}`:device.code}
const routePoints = computed(() => activePatrol.value?.route.map(point => `${point.x * props.image.width},${point.y * props.image.height}`).join(' ') || '')
const displayProgress = computed(() => {
  const mission = activePatrol.value
  if (!mission) return 0
  if (mission.status === 'completed') return 100
  if (mission.status !== 'running') return mission.progress
  // The last server response is authoritative; interpolate only for rendering.
  const elapsed = Math.max(0, animationNow.value - progressBaseline.at)
  return clamp(progressBaseline.progress + elapsed / Math.max(mission.duration_seconds * 1000, 1) * 100, 0, 99.9)
})
const dronePosition = computed(() => activePatrol.value ? pointAlongRoute(activePatrol.value.route, displayProgress.value) : null)
// Labels may move in screen space; the anchor itself always stays at its source
// image coordinate. Leaders make the distinction visible, including duplicates.
const markerOffsets = computed(() => {
  const offsets: Record<string, { x: number; y: number }> = {}
  const occupied: { x: number; y: number; width: number; height: number }[] = []
  const screenPoint = (point: { x:number; y:number }) => ({ x: (point.x * props.image.width - center.value.x) / unitsPerPixel.value + viewport.value.width / 2, y: (point.y * props.image.height - center.value.y) / unitsPerPixel.value + viewport.value.height / 2 })
  for (const space of visibleSpaces.value) {
    if (!space.anchor) continue
    const point = screenPoint(space.anchor), width = space.name.length * 11 + 30
    occupied.push({ x: point.x - width / 2, y: point.y - 62, width, height: 34 })
  }
  const items = [
    ...visibleDevices.value.filter(device => device.id !== activePatrol.value?.device_id).map(device => ({ key: `device:${device.id}`, point: devicePoint(device), width: Math.max(84,deviceDisplayCode(device).length*6.2+10), height: 58 })),
    ...visibleIncidents.value.map(incident => ({ key: `incident:${incident.id}`, point: incident.anchor!, width: 52, height: 58 })),
  ]
  for (const item of items) {
    const origin = screenPoint(item.point)
    if (origin.x < -30 || origin.y < -30 || origin.x > viewport.value.width + 30 || origin.y > viewport.value.height + 30) { offsets[item.key] = { x:0, y:0 }; continue }
    const options = [{ x:0, y:0 }]
    for (const radius of [48,76,106,140,180,220]) for (let index = 0; index < 16; index++) {
      const angle = (index / 16) * Math.PI * 2
      options.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius })
    }
    let choice = options[0]!
    let score = Infinity
    for (const option of options) {
      const rect = { x: origin.x + option.x - item.width / 2, y: origin.y + option.y - 20, width:item.width, height:item.height }
      if (rect.x < 6 || rect.y < 8 || rect.x + rect.width > viewport.value.width - 6 || rect.y + rect.height > viewport.value.height - 30) continue
      const overlap = occupied.reduce((sum, other) => sum + Math.max(0, Math.min(rect.x + rect.width, other.x + other.width) - Math.max(rect.x, other.x)) * Math.max(0, Math.min(rect.y + rect.height, other.y + other.height) - Math.max(rect.y, other.y)), 0)
      const cost = overlap * 100 + Math.hypot(option.x, option.y)
      if (cost < score) { score = cost; choice = option }
      if (!overlap) break
    }
    offsets[item.key] = choice
    occupied.push({ x:origin.x + choice.x - item.width / 2, y:origin.y + choice.y - 20, width:item.width, height:item.height })
  }
  return offsets
})
function offset(kind: string, id:string) { return markerOffsets.value[`${kind}:${id}`] || { x:0, y:0 } }
const devicePaths: Record<string, string> = {
  temperature: 'M10 4a2 2 0 0 1 4 0v9a4 4 0 1 1-4 0V4Zm2 5v7',
  smoke: 'M5 15h14M7 19h10M8 10c-4-3 4-3 0-6m5 6c-4-3 4-3 0-6m5 6c-4-3 4-3 0-6',
  camera: 'M3 6h12v12H3V6Zm12 4 6-4v12l-6-4',
  fire: 'M12 2c2 5 6 6 6 12a6 6 0 1 1-12 0c0-3 2-5 3-7 0 4 2 4 2 4 2-3 1-5 1-9Z',
  drone: 'M9 9h6v6H9zM5 5l4 4m6 0 4-4M5 19l4-4m6 0 4 4M5 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm14 0a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM5 16a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm14 0a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  robot: 'M5 8h14v11H5zM12 4v4m-3 4h1m4 0h1M8 16h8M7 19v2m10-2v2',
}
function markerTransform(point: { x: number; y: number }, displacement = { x:0, y:0 }) {
  return `translate(${point.x * props.image.width + displacement.x * unitsPerPixel.value} ${point.y * props.image.height + displacement.y * unitsPerPixel.value}) scale(${unitsPerPixel.value})`
}
function devicePoint(device: MapDevice) {
  if (device.id === activePatrol.value?.device_id && dronePosition.value) return dronePosition.value
  return device.anchor || { x: .5, y: .5 }
}
function selected(kind: Selection['kind'], id: string) { return props.selected?.kind === kind && props.selected.id === id }
function choose(kind: Selection['kind'], id: string) {
  if (Date.now() < suppressClickUntil) return
  emit('select', { kind, id })
}
function polygon(space: Space) { return space.polygon.map(p => `${p.x * props.image.width},${p.y * props.image.height}`).join(' ') }
function boundCamera() { center.value = cameraBounds(center.value, zoom.value, props.image.width, props.image.height) }
function reset() { zoom.value = 1; center.value = { x: props.image.width / 2, y: props.image.height / 2 } }
function imagePoint(clientX: number, clientY: number) {
  const matrix = svg.value?.getScreenCTM()
  if (!matrix || !svg.value) return null
  const point = svg.value.createSVGPoint(); point.x = clientX; point.y = clientY
  return point.matrixTransform(matrix.inverse())
}
function zoomTo(next: number, pivot?: { x: number; y: number }) {
  const previous = zoom.value
  zoom.value = clamp(next, 1, 4)
  if (pivot) center.value = { x: pivot.x + (center.value.x - pivot.x) * previous / zoom.value, y: pivot.y + (center.value.y - pivot.y) * previous / zoom.value }
  boundCamera()
}
function wheel(event: WheelEvent) { zoomTo(zoom.value * Math.exp(-event.deltaY * .0015), imagePoint(event.clientX, event.clientY) || undefined) }
function startDrag(event: PointerEvent) {
  if (event.button !== 0 || !svg.value) return
  dragStart = { id: event.pointerId, x: event.clientX, y: event.clientY, centerX: center.value.x, centerY: center.value.y, scale: unitsPerPixel.value }
  dragged = false
  // Capture on first movement so a normal tap still reaches its marker.
}
function moveDrag(event: PointerEvent) {
  if (!dragStart || event.pointerId !== dragStart.id) return
  const dx = event.clientX - dragStart.x, dy = event.clientY - dragStart.y
  if (!dragged && Math.hypot(dx, dy) < 5) return
  if (!dragged) { dragged = true; svg.value?.setPointerCapture(event.pointerId) }
  dragging.value = true
  center.value = { x: dragStart.centerX - dx * dragStart.scale, y: dragStart.centerY - dy * dragStart.scale }
  boundCamera()
}
function endDrag(event: PointerEvent) {
  if (dragStart?.id !== event.pointerId) return
  if (dragged) suppressClickUntil = Date.now() + 150
  if (svg.value?.hasPointerCapture(event.pointerId)) svg.value.releasePointerCapture(event.pointerId)
  dragStart = null; dragging.value = false
}
function keyboardPan(event: KeyboardEvent) {
  if (event.target !== svg.value) return
  const amount = 45 * unitsPerPixel.value
  const movement: Record<string, [number, number]> = { ArrowLeft: [-amount, 0], ArrowRight: [amount, 0], ArrowUp: [0, -amount], ArrowDown: [0, amount] }
  if (movement[event.key]) { event.preventDefault(); const [x, y] = movement[event.key]!; center.value = { x: center.value.x + x, y: center.value.y + y }; boundCamera() }
  if (event.key === '+' || event.key === '=') { event.preventDefault(); zoomTo(zoom.value * 1.3) }
  if (event.key === '-') { event.preventDefault(); zoomTo(zoom.value / 1.3) }
  if (event.key === 'Home') { event.preventDefault(); reset() }
}
async function fullscreen() {
  fullscreenError.value = ''
  if (fallbackFullscreen.value) { fallbackFullscreen.value = false; syncFullscreen(); return }
  try {
    if (document.fullscreenElement === container.value) await document.exitFullscreen()
    else await container.value?.requestFullscreen()
    syncFullscreen()
  } catch {
    // Embedded browsers may reject the native fullscreen API. Keep the same
    // interaction available by expanding only this map over the current page.
    fallbackFullscreen.value = true
    syncFullscreen()
  }
}
function syncFullscreen() { isFullscreen.value = fallbackFullscreen.value || document.fullscreenElement === container.value }
function escapeFullscreen(event: KeyboardEvent) {
  if (event.key === 'Escape' && fallbackFullscreen.value) {
    event.preventDefault()
    fallbackFullscreen.value = false
    syncFullscreen()
  }
}
function applyFocus(anchor: Anchor | null) {
  if (!validAnchor(anchor) || !anchor) return
  zoom.value = Math.max(1.65, zoom.value)
  center.value = { x: anchor.x * props.image.width, y: anchor.y * props.image.height }
  boundCamera()
}
watch(() => props.image.id, () => { imageError.value = false; reset(); applyFocus(props.focus) })
watch(() => props.focus, anchor => applyFocus(anchor), { deep: true })
watch(() => [activePatrol.value?.id, activePatrol.value?.progress, activePatrol.value?.status], () => {
  progressBaseline = { id: activePatrol.value?.id || '', progress: activePatrol.value?.progress || 0, at: performance.now() }
  animationNow.value = performance.now()
}, { immediate: true })
onMounted(() => {
  resizeObserver = new ResizeObserver(entries => {
    const entry = entries[0]
    if (entry) viewport.value = { width: entry.contentRect.width, height: entry.contentRect.height }
  })
  if (svg.value) resizeObserver.observe(svg.value)
  document.addEventListener('fullscreenchange', syncFullscreen)
  document.addEventListener('keydown', escapeFullscreen)
  const tick = (now: number) => { animationNow.value = now; animationFrame = requestAnimationFrame(tick) }
  animationFrame = requestAnimationFrame(tick)
  applyFocus(props.focus)
})
onUnmounted(() => { resizeObserver?.disconnect(); document.removeEventListener('fullscreenchange', syncFullscreen); document.removeEventListener('keydown', escapeFullscreen); cancelAnimationFrame(animationFrame) })
</script>

<template>
  <section ref="container" class="campus-image-map" :class="{ 'is-fullscreen': isFullscreen, 'is-fallback-fullscreen': fallbackFullscreen }" :style="{ '--image-ratio': image.width / image.height }" aria-label="杭州校区图片交互地图">
    <header class="map-toolbar">
      <div class="map-image-title"><span class="map-indicator"></span><strong>{{displayText(image.title)}}</strong><span class="planning-chip">规划效果图</span></div>
      <div class="map-actions">
        <button aria-label="地图缩小" title="缩小" :disabled="zoom <= 1" @click="zoomTo(zoom / 1.3)">−</button>
        <output aria-label="地图缩放比例">{{ Math.round(zoom * 100) }}%</output>
        <button aria-label="地图放大" title="放大" :disabled="zoom >= 4" @click="zoomTo(zoom * 1.3)">＋</button>
        <button aria-label="地图复位" title="恢复全部视野" @click="reset"><Icon name="refresh" :size="15" /></button>
        <button :aria-label="isFullscreen ? '退出地图全屏' : '地图全屏'" :title="isFullscreen ? '退出全屏' : '地图全屏'" @click="fullscreen"><Icon name="expand" :size="15" /></button>
      </div>
    </header>
    <div class="map-canvas" :class="{ dragging }">
      <svg ref="svg" class="image-space" :viewBox="viewBox" preserveAspectRatio="xMidYMid meet" role="group" tabindex="0" aria-label="校园地图，滚轮缩放，拖动平移；键盘加减号缩放，方向键移动，Home复位" @wheel.prevent="wheel" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag" @keydown="keyboardPan">
        <image :href="image.url" x="0" y="0" :width="image.width" :height="image.height" preserveAspectRatio="xMidYMid meet" @error="imageError = true" />
        <rect x="0" y="0" :width="image.width" :height="image.height" fill="#061a30" opacity=".13" pointer-events="none" />
        <g v-if="layers.buildings" class="building-layer">
          <g v-for="space in visibleSpaces" :key="space.id" class="building-hit" :class="{ 'is-selected': selected('building', space.id) }" role="button" tabindex="0" :aria-label="`建筑 ${space.name}`" :aria-pressed="selected('building', space.id)" @click.stop="choose('building', space.id)" @keydown.enter.prevent="choose('building', space.id)" @keydown.space.prevent="choose('building', space.id)" @mouseenter="hover = space.id" @mouseleave="hover = ''">
            <title>{{displayText(space.name)}} · {{displayText(space.verification)}}</title>
            <polygon v-if="space.polygon.length" :points="polygon(space)" class="building-region" vector-effect="non-scaling-stroke" />
            <g v-if="space.anchor" :transform="markerTransform(space.anchor)" class="building-tag">
              <line x1="0" y1="0" x2="0" y2="-33" stroke="currentColor" stroke-width="1.2" />
              <circle r="3" fill="currentColor" />
              <rect :x="-(space.name.length * 5.5 + 12)" y="-58" :width="space.name.length * 11 + 24" height="25" rx="4" />
              <text x="0" y="-42" text-anchor="middle">{{displayText(space.name)}}</text>
            </g>
          </g>
        </g>
        <g v-if="layers.routes && activePatrol" class="route-layer" pointer-events="none">
          <polyline :points="routePoints" class="route-glow" vector-effect="non-scaling-stroke" />
          <polyline :points="routePoints" class="route-line" :class="{ draft: activePatrol.status === 'draft' }" vector-effect="non-scaling-stroke" />
          <g v-for="(point, index) in activePatrol.route" :key="index" :transform="markerTransform(point)"><circle r="4" fill="#082f42" stroke="#6be0ef" stroke-width="1.5" /><text v-if="index === 0" y="18" text-anchor="middle" class="route-label">模拟起点</text></g>
        </g>
        <g v-if="activeExecution?.target_point && layers.routes" :transform="markerTransform(activeExecution.target_point)" pointer-events="none"><circle r="10" fill="#194b5bcc" stroke="#94f0df" stroke-width="1.5" stroke-dasharray="3 2"/><path d="M-15 0H15M0 -15V15" stroke="#a5eee8" stroke-width="1"/><text y="-21" text-anchor="middle" class="route-label">任务目标</text></g>
        <g class="marker-leaders" pointer-events="none">
          <g v-for="device in visibleDevices" :key="device.id" :transform="markerTransform(devicePoint(device))"><line v-if="offset('device',device.id).x || offset('device',device.id).y" x1="0" y1="0" :x2="offset('device',device.id).x" :y2="offset('device',device.id).y"/><circle r="2.5"/></g>
          <g v-for="incident in visibleIncidents" :key="incident.id" :transform="markerTransform(incident.anchor!)"><line v-if="offset('incident',incident.id).x || offset('incident',incident.id).y" x1="0" y1="0" :x2="offset('incident',incident.id).x" :y2="offset('incident',incident.id).y"/><circle r="2.5"/></g>
        </g>
        <g class="device-layer">
          <g v-for="device in visibleDevices" :key="device.id" :transform="markerTransform(devicePoint(device), offset('device',device.id))" class="device-marker" :class="[device.type, device.status, { 'is-selected': selected('device', device.id), moving: device.id === activePatrol?.device_id && activePatrol.status === 'running' }]" role="button" tabindex="0" :aria-label="`设备 ${device.code} ${device.name}`" :aria-pressed="selected('device', device.id)" @click.stop="choose('device', device.id)" @keydown.enter.prevent="choose('device', device.id)" @keydown.space.prevent="choose('device', device.id)" @mouseenter="hover = device.id" @mouseleave="hover = ''">
            <title>{{deviceDisplayCode(device)}} · {{displayText(device.name)}} · 模拟 点位</title>
            <circle class="marker-halo" r="22" />
            <circle class="marker-base" r="14" />
            <svg x="-9" y="-9" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="devicePaths[device.type] || devicePaths.temperature" /></svg>
            <g class="device-label"><rect :x="-Math.max(37,deviceDisplayCode(device).length*3.1)" y="18" :width="Math.max(74,deviceDisplayCode(device).length*6.2)" height="17" rx="3" /><text x="0" y="30" text-anchor="middle">{{deviceDisplayCode(device)}}</text></g>
            <g v-if="hover === device.id || selected('device', device.id)" class="device-tooltip"><rect :x="-(device.name.length * 5.5 + 9)" y="-40" :width="device.name.length * 11 + 18" height="21" rx="4" /><text x="0" y="-26" text-anchor="middle">{{displayText(device.name)}}</text></g>
          </g>
        </g>
        <g v-if="layers.incidents" class="incident-layer">
          <g v-for="(incident,index) in visibleIncidents" :key="incident.id" :transform="markerTransform(incident.anchor!, offset('incident',incident.id))" class="incident-marker" :class="[incident.risk_level, { 'is-selected': selected('incident', incident.id) }]" role="button" tabindex="0" :aria-label="`事件 ${incident.title}`" :aria-pressed="selected('incident', incident.id)" @click.stop="choose('incident', incident.id)" @keydown.enter.prevent="choose('incident', incident.id)" @keydown.space.prevent="choose('incident', incident.id)">
            <title>{{displayText(incident.title)}} · 模拟 风险事件</title>
            <circle class="incident-ring" r="26" />
            <path d="M0 -17 18 14H-18Z" class="warning-triangle" /><path d="M0 -7v10m0 5v1" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" />
            <rect :x="incident.code?-30:-22" y="19" :width="incident.code?60:44" height="16" rx="3" fill="#452b2aeb"/><text x="0" y="30" text-anchor="middle" class="incident-index">{{incident.code||('事件 '+(index+1))}}</text>
          </g>
        </g>
      </svg>
      <div v-if="imageError" class="map-image-error" role="alert">校园底图加载失败，请检查本地素材路径。不会替换为虚构校园。</div>
      <div class="map-help" aria-hidden="true">滚轮缩放 · 拖动平移 · 点击查看详情</div>
      <div v-if="activePatrol && layers.routes" class="patrol-map-status"><span class="map-indicator"></span>{{missionLabel}}<b>{{ Math.round(displayProgress) }}%</b></div>
      <div class="map-watermark">模拟 · 引线端点为图像点位</div>
    </div>
    <footer class="map-caption"><span>学校规划资料 · 图片空间交互 · 非实时影像 / 非三维模型</span><span>点位 0—1 归一化</span></footer>
    <p v-if="fullscreenError" class="map-fullscreen-error" role="status">{{ fullscreenError }}</p>
  </section>
</template>

<style scoped>
.campus-image-map{display:flex;flex-direction:column;min-width:0;min-height:380px;height:100%;overflow:hidden;border:1px solid #284665;background:#09192b;border-radius:8px;position:relative;color:#b6cfe3}.map-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;background:#0d2339;border-bottom:1px solid #29425d;flex-shrink:0;flex-wrap:wrap}.map-image-title{display:flex;align-items:center;gap:7px;min-width:0}.map-image-title strong{font-size:11px;font-weight:600;max-width:245px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.map-indicator{width:5px;height:5px;border-radius:50%;display:inline-block;background:#5dd1c7;box-shadow:0 0 7px #5dd1c755}.planning-chip{font-size:8px;border:1px solid #365372;padding:2px 4px;border-radius:3px;color:#a0bad1;white-space:nowrap}.map-actions{display:flex;align-items:center;gap:3px}.map-actions button{height:26px;width:27px;border:1px solid #2c4966;border-radius:4px;display:inline-flex;align-items:center;justify-content:center;color:#bdd9ef;background:#142d46;font-size:17px;line-height:1}.map-actions button:hover{background:#244969;border-color:#68abc7}.map-actions button:disabled{opacity:.35}.map-actions output{width:40px;text-align:center;font-size:10px;font-variant-numeric:tabular-nums;color:#8cabc8}.map-canvas{position:relative;flex:1 0 auto;aspect-ratio:var(--image-ratio);min-height:400px;overflow:hidden;background:radial-gradient(ellipse at center,#1e3447,#081622)}.image-space{width:100%;height:100%;min-height:0;position:absolute;inset:0;display:block;touch-action:none;cursor:grab;user-select:none}.dragging .image-space{cursor:grabbing}.building-hit,.device-marker,.incident-marker{cursor:pointer;outline:none}.building-region{fill:#2aabd31f;stroke:#85d9ed88;stroke-width:1.3;stroke-dasharray:5 3;transition:fill .15s,stroke .15s}.building-hit:hover .building-region,.building-hit:focus .building-region,.building-hit.is-selected .building-region{fill:#2cc2ec36;stroke:#a5edff;stroke-width:2;stroke-dasharray:none}.building-tag{color:#aee9fa}.building-tag rect{fill:#0b263ce8;stroke:#70c4df;stroke-width:.8}.building-tag text{fill:#e1f5ff;font-size:11px;font-weight:500;font-family:inherit;paint-order:stroke;stroke:none}.building-hit.is-selected .building-tag rect,.building-hit:focus .building-tag rect{fill:#164a65;stroke:#b4f3ff;stroke-width:1.5}.route-glow{fill:none;stroke:#36d7e6;stroke-width:9;opacity:.2}.route-line{fill:none;stroke:#7af1f0;stroke-width:2;stroke-linejoin:round}.route-line.draft{stroke-dasharray:8 6}.route-label{font:9px 'Segoe UI','Microsoft YaHei',sans-serif;fill:#dbffff;paint-order:stroke;stroke:#092033;stroke-width:3px;stroke-linejoin:round}.device-marker{color:#95dfff}.device-marker.drone{color:#8ff3df}.device-marker.robot{color:#bfc0ff}.device-marker.alarm{color:#ffbe7c}.device-marker.offline{color:#c7ac9a}.marker-halo{fill:currentColor;opacity:.13;stroke:none}.marker-base{fill:#0b283dec;stroke:currentColor;stroke-width:1.3}.device-label rect,.device-tooltip rect{fill:#082337ec;stroke:#78b3ce55;stroke-width:.7}.device-label text{font:9px 'Segoe UI',sans-serif;fill:#dbf1ff;letter-spacing:.1px}.device-tooltip text{font:11px 'Segoe UI','Microsoft YaHei',sans-serif;fill:#f0faff}.device-marker.is-selected .marker-base,.device-marker:hover .marker-base,.device-marker:focus .marker-base{stroke:#fff;stroke-width:2.5;fill:#245675}.device-marker.is-selected .marker-halo,.device-marker:focus .marker-halo{opacity:.35}.moving .marker-halo{animation:map-pulse 1.5s ease-in-out infinite}.incident-marker{color:#ff876f}.incident-marker.medium{color:#ffbd6e}.incident-marker.low{color:#f5da8e}.incident-ring{fill:currentColor;opacity:.19;stroke:currentColor;stroke-width:1}.warning-triangle{fill:#bf573bee;stroke:currentColor;stroke-width:1.5;stroke-linejoin:round}.incident-marker.medium .warning-triangle{fill:#936524}.incident-marker.is-selected .incident-ring,.incident-marker:hover .incident-ring,.incident-marker:focus .incident-ring{opacity:.38;stroke:white;stroke-width:2}.incident-marker.is-selected .warning-triangle,.incident-marker:focus .warning-triangle{stroke:#fff;stroke-width:2}.map-help{position:absolute;left:10px;bottom:9px;border:1px solid #7aa5c333;padding:5px 7px;background:#091e30cf;color:#d0e0e9;font-size:9px;pointer-events:none;border-radius:3px}.map-watermark{position:absolute;right:10px;bottom:10px;color:#d0e6f2d9;font-size:9px;letter-spacing:.06em;text-shadow:0 1px 4px #000;pointer-events:none}.map-caption{display:flex;justify-content:space-between;flex-wrap:wrap;gap:5px;padding:8px 10px;color:#9cb4ca;font-size:9px;background:#0a2034;border-top:1px solid #203b56;flex-shrink:0}.patrol-map-status{position:absolute;left:10px;top:10px;display:flex;gap:7px;align-items:center;font-size:10px;padding:7px 9px;color:#b9f9eb;background:#092f3eea;border:1px solid #478c98;border-radius:4px;pointer-events:none}.patrol-map-status b{font-variant-numeric:tabular-nums;font-weight:500;margin-left:7px}.map-image-error{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:30px;color:#f6c6b3;background:#101b2bf5;text-align:center;font-size:12px}.map-fullscreen-error{font-size:10px;background:#503923;color:#ffe0bb;padding:8px 12px}.campus-image-map:fullscreen,.campus-image-map.is-fullscreen{width:100vw;height:100vh;max-height:none;border-radius:0;border:0}.campus-image-map:fullscreen .map-canvas{min-height:0}.campus-image-map:fullscreen .image-space{min-height:0}.campus-image-map:fullscreen .map-toolbar{padding:14px 20px}.campus-image-map:fullscreen .map-caption{padding:12px 20px}.campus-image-map:fullscreen .map-image-title strong{font-size:14px;max-width:none}@keyframes map-pulse{0%,100%{opacity:.13}50%{opacity:.35}}@media(max-width:700px){.campus-image-map{min-height:350px}.map-canvas{min-height:260px}.image-space{min-height:0}.map-toolbar{padding:8px}.map-image-title strong{max-width:170px}.map-caption{font-size:8px}.map-caption>span:last-child{display:none}.planning-chip{display:none}.map-help{font-size:8px;max-width:65%}.map-watermark{font-size:8px}}@media(prefers-reduced-motion:reduce){.moving .marker-halo{animation:none}.building-region{transition:none}}
.marker-leaders line{stroke:#c3e8f2;stroke-width:1;opacity:.65;stroke-dasharray:3 2}.marker-leaders circle{fill:#c3f1ff;stroke:#143650;stroke-width:1}.incident-index{font:9px Segoe UI,Microsoft YaHei,sans-serif;fill:#ffded2}:global(.scene-grid) .map-canvas{min-height:310px}:global(.scene-grid) .campus-image-map{min-height:380px}.campus-image-map.is-fallback-fullscreen{position:fixed;inset:0;z-index:10000;height:100dvh;width:100vw;max-height:none;border:0;border-radius:0}.campus-image-map.is-fullscreen .map-canvas{aspect-ratio:auto;min-height:0;flex:1 1 0}.campus-image-map.is-fullscreen .image-space{min-height:0}.campus-image-map.is-fullscreen .map-toolbar{padding:14px 20px}.campus-image-map.is-fullscreen .map-caption{padding:12px 20px}</style>
