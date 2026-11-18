import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source=await readFile(new URL('../src/runProgress.ts',import.meta.url),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {pollRunProgress}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))
const event=(sequence,type='stage')=>({run_id:'r1',sequence,type})

test('polling collects ordered unique events and waits for the terminal record',async()=>{
 const original=globalThis.fetch, requests=[],updates=[]
 let historyReads=0,handle
 globalThis.fetch=async url=>{
  requests.push(url)
  if(url.includes('event-history')){historyReads++;return Response.json(historyReads===1?[event(2),event(1),event(2)]:historyReads===2?[]:[event(3,'terminal')])}
  return Response.json({id:'r1',status:historyReads?'completed':'running'})
 }
 try{
  handle=pollRunProgress('r1',{intervalMs:1,onUpdate:batch=>updates.push(...batch.map(item=>item.sequence)),onNotice:()=>{}})
  for(let n=0;n<100&&historyReads<3;n++)await pause(2)
  await pause(5)
  assert.deepEqual(updates,[1,2,3])
  assert.equal(historyReads,3)
  assert.ok(requests.includes('/api/v1/runs/r1/event-history?after=2'))
 }finally{handle?.close();globalThis.fetch=original}
})

test('closing a poll discards a response already in flight',async()=>{
 const original=globalThis.fetch,updates=[]
 let release,handle
 globalThis.fetch=()=>new Promise(resolve=>{release=resolve})
 try{
  handle=pollRunProgress('r1',{intervalMs:1,onUpdate:value=>updates.push(value),onNotice:()=>{}})
  handle.close()
  release(Response.json({id:'r1',status:'running'}))
  await pause(5)
  assert.deepEqual(updates,[])
 }finally{handle?.close();globalThis.fetch=original}
})

test('consecutive request failures stop after four attempts and offer recovery',async()=>{
 const original=globalThis.fetch,notices=[]
 let attempts=0,handle
 globalThis.fetch=async()=>{attempts++;throw new Error('offline')}
 try{
  handle=pollRunProgress('r1',{intervalMs:1,onUpdate:()=>assert.fail('must not update'),onNotice:message=>notices.push(message)})
  for(let n=0;n<100&&attempts<4;n++)await pause(2)
  await pause(10)
  assert.equal(attempts,4)
  assert.match(notices.at(-1),/已暂停重试/)
 }finally{handle?.close();globalThis.fetch=original}
})
