import type {Run, RunEvent} from './api'

// Temporary public tunnels cannot carry SSE. Read the same persisted events instead.
export function pollRunProgress(runId:string, options:{
  onUpdate:(events:RunEvent[], run:Run)=>void|Promise<void>
  onNotice:(message:string)=>void
  intervalMs?:number
}):{close:()=>void} {
  let closed=false, cursor=0, failures=0, terminalWaits=0
  let timer:ReturnType<typeof setTimeout>|undefined
  const controller=new AbortController(), interval=options.intervalMs??900
  const base=`/api/v1/runs/${encodeURIComponent(runId)}`
  const close=()=>{closed=true;clearTimeout(timer);controller.abort()}
  async function read<T>(url:string):Promise<T>{
    const requestController=new AbortController()
    const abort=()=>requestController.abort()
    controller.signal.addEventListener('abort',abort,{once:true})
    const timeout=setTimeout(abort,10000)
    try{
      const response=await fetch(url,{signal:requestController.signal,cache:'no-store'})
      if(!response.ok)throw new Error(`请求失败 (${response.status})`)
      return await response.json() as T
    }finally{clearTimeout(timeout);controller.signal.removeEventListener('abort',abort)}
  }
  async function tick(){
    if(closed)return
    try{
      let latest=await read<Run>(base)
      if(closed)return
      const history=await read<RunEvent[]>(`${base}/event-history?after=${cursor}`)
      if(closed)return
      const seen=new Set<number>()
      const batch=history.filter(event=>{
        if(event.run_id!==runId||event.sequence<=cursor||seen.has(event.sequence))return false
        seen.add(event.sequence)
        return true
      }).sort((a,b)=>a.sequence-b.sequence)
      if(batch.some(event=>event.type==='terminal')&&['queued','running'].includes(latest.status)){
        latest=await read<Run>(base)
        if(closed)return
      }
      await options.onUpdate(batch,latest)
      if(closed)return
      cursor=batch.at(-1)?.sequence??cursor
      failures=0;options.onNotice('')
      if(batch.some(event=>event.type==='terminal')){close();return}
      // The final database update and its terminal event are separate writes.
      // Keep reading until the event arrives, so completion never drops the last record.
      terminalWaits=['queued','running'].includes(latest.status)?0:terminalWaits+1
      if(terminalWaits>=10){options.onNotice('任务状态已保存，但末尾过程记录尚未读到，请刷新或重连过程记录。');close();return}
      timer=setTimeout(tick,interval)
    }catch(error){
      if(closed)return
      failures++
      options.onNotice(failures>=4?'过程读取连续失败，已暂停重试。请刷新或重连过程记录；后台任务与已保存记录不受影响。':`过程读取暂时中断，正在重试（${failures}/4）。`)
      if(failures>=4){close();return}
      timer=setTimeout(tick,interval*Math.min(4,2**failures))
    }
  }
  void tick()
  return {close}
}
