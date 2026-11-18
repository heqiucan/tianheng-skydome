<script setup lang="ts">
import {displayText} from '../api'
import { computed } from 'vue'
import type { Location } from '../api'
const props=defineProps<{locations:Location[];activeLocationId?:string;selectedId?:string}>()
const emit=defineEmits<{select:[id:string]}>()
const sites=computed(()=>props.locations.filter(l=>l.kind!=='campus').slice(0,4))
const points=[{x:335,y:214},{x:147,y:146},{x:476,y:123},{x:524,y:287}]
const isActive=(l:Location)=>l.id===props.activeLocationId||props.locations.some(child=>child.id===props.activeLocationId&&child.parent_id===l.id)
</script>
<template>
 <div class="campus-map">
  <div class="map-label"><span class="map-dot"></span> 校园态势 <span class="map-label-divider">/</span> 模拟位置</div>
  <svg class="campus-art" viewBox="0 0 680 370" role="img" aria-label="虚构校园示意图，可点击建筑查看位置">
   <defs><pattern id="map-grid" width="32" height="32" patternUnits="userSpaceOnUse" patternTransform="skewY(-12)"><path d="M32 0H0V32" fill="none" stroke="#30445a" stroke-opacity=".35" stroke-width=".5"/></pattern><linearGradient id="ground" x2="1" y2="1"><stop stop-color="#1a3540"/><stop offset="1" stop-color="#101c2c"/></linearGradient><linearGradient id="roof" x2="0" y2="1"><stop stop-color="#486477"/><stop offset="1" stop-color="#314555"/></linearGradient><radialGradient id="alert-glow"><stop stop-color="#ff706b" stop-opacity=".32"/><stop offset="1" stop-color="#ff706b" stop-opacity="0"/></radialGradient></defs>
   <rect width="680" height="370" fill="#0b1724"/><rect width="680" height="370" fill="url(#map-grid)"/>
   <path d="m48 111 360-76 223 193-333 110L48 111Z" fill="url(#ground)" stroke="#2c454a"/>
   <g fill="none" stroke-linejoin="round"><path d="m55 233 486-101m-385-75 307 255M70 148l325 186m-44-286 248 211" stroke="#3c4c55" stroke-width="21"/><path d="m55 233 486-101m-385-75 307 255M70 148l325 186m-44-286 248 211" stroke="#75808b" stroke-opacity=".45" stroke-width="1" stroke-dasharray="8 8"/></g>
   <g fill="#244b42" stroke="#325d4c" stroke-width="1"><path d="m211 58 91-18 51 45-91 20Z"/><path d="m75 255 85-18 52 44-81 28Z"/><path d="m424 235 42-10 66 58-43 13Z"/></g>
   <g opacity=".85"><path d="m440 65 85-16 77 64-81 20Z" fill="#294b43" stroke="#466b57"/><path d="m462 69 58-11 60 51-58 14Z" fill="#193d3f" stroke="#7b7770" stroke-width="8"/><path d="m467 72 49-9 53 44-46 11Z" fill="none" stroke="#9aa687" stroke-opacity=".5"/><path d="m489 68 54 45" stroke="#92a48b" stroke-opacity=".5"/></g>
   <g v-for="(b,i) in [{x:87,y:116,w:83,h:40},{x:196,y:99,w:65,h:38},{x:342,y:96,w:64,h:33},{x:488,y:196,w:73,h:40},{x:191,y:246,w:69,h:32},{x:326,y:277,w:52,h:26}]" :key="i"><path :d="`M${b.x} ${b.y}l${b.w} -16 35 29-${b.w} 17Z`" fill="url(#roof)" stroke="#67808b" stroke-opacity=".4"/><path :d="`M${b.x} ${b.y}v${b.h}l35 28V${b.y+29}Z`" fill="#253b4b"/><path :d="`M${b.x+35} ${b.y+29}l${b.w} -17v${b.h}l-${b.w} 17Z`" fill="#1c2e3f"/><path v-for="row in 3" :key="row" :d="`M${b.x+40} ${b.y+29+row*8}l${b.w-10} -15`" stroke="#7aafbd" stroke-opacity=".38" stroke-width="2" stroke-dasharray="5 4"/></g>
   <g transform="translate(281 167)"><ellipse cx="47" cy="61" rx="110" ry="62" fill="url(#alert-glow)"/><path d="m0 24 104-23 49 42-104 25Z" fill="#5b5361" stroke="#e89a91" stroke-opacity=".65"/><path d="M0 24v43l49 42V68Z" fill="#484351"/><path d="m49 68 104-25v43l-104 23Z" fill="#392f42"/><path v-for="r in 4" :key="r" :d="`m55 ${69+r*8} 91-21`" stroke="#d29993" stroke-opacity=".65" stroke-width="3" stroke-dasharray="6 5"/><ellipse cx="50" cy="68" rx="88" ry="35" fill="none" stroke="#f47272" stroke-opacity=".4"/><ellipse cx="50" cy="68" rx="109" ry="46" fill="none" stroke="#f47272" stroke-opacity=".2"/></g>
   <g v-for="(site,i) in sites" :key="site.id" :transform="`translate(${points[i]!.x},${points[i]!.y})`" class="map-building" role="button" tabindex="0" :aria-label="`查看${site.name}`" @click="emit('select',site.id)" @keydown.enter="emit('select',site.id)">
    <line y1="0" y2="-39" :stroke="isActive(site)?'#ff8b83':'#5fcfff'" stroke-opacity=".7"/><circle r="4" :fill="isActive(site)?'#ff8b83':'#5fcfff'"/><rect x="-55" y="-67" width="110" height="30" rx="5" :fill="isActive(site)?'#713f46':selectedId===site.id?'#1d5272':'#183046'" :stroke="isActive(site)?'#ef7972':'#4c7187'"/><text y="-48" text-anchor="middle" fill="#eef5fa" font-size="12" font-family="sans-serif">{{displayText(site.name)}}</text>
   </g>
   <g transform="translate(627 302)"><path d="m0-21-7 21 7-5 7 5Z" fill="#9cb9ce"/><text y="-29" text-anchor="middle" fill="#9cb9ce" font-size="11">N</text></g>
  </svg>
  <div class="map-footer"><span><i class="legend-dot red"></i>告警区域</span><span><i class="legend-dot blue"></i>建筑位置</span><span class="map-footnote">校园示意图 · 非真实地理坐标</span></div>
 </div>
</template>
