import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source=await readFile(new URL('../src/api.ts',import.meta.url),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {displayText,ruleVersionText}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('presentation labels change without breaking event IDs embedded in task logs',()=>{
 const log='天穹 · DEMO\n已关联事件 inc-demo-evt-008；字段 is_demo，规则 demo-risk-v2。\n中文DEMO标签；（demo）；DEMO演示；设备 demoSensor、demo2、sensor_demo。'
 assert.equal(displayText(log),'天亨 · 模拟\n已关联事件 inc-demo-evt-008；字段 is_demo，规则 demo-risk-v2。\n中文模拟标签；（模拟）；模拟演示；设备 demoSensor、demo2、sensor_demo。')
 assert.equal(ruleVersionText('demo-risk-v2'),'模拟规则 v2')
})
