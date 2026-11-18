import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
const source=await readFile(new URL('../src/assessmentSelection.ts',import.meta.url),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {matchesAssessment,selectAssessment,validPage}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
test('same devices do not permit restoring an assessment from a different event or snapshot',()=>{
 const snapshot={snapshot_id:'snapshot-B',incident:{id:'event-B'}}
 const wrongEvent={id:'run-A',incident_id:'event-A',evidence_snapshot_id:'snapshot-B'}
 const wrongSnapshot={id:'run-old-B',incident_id:'event-B',evidence_snapshot_id:'snapshot-old-B'}
 const selected={id:'run-B',incident_id:'event-B',evidence_snapshot_id:'snapshot-B'}
 assert.equal(matchesAssessment(snapshot,wrongEvent),false)
 assert.equal(matchesAssessment(snapshot,wrongSnapshot),false)
 assert.equal(selectAssessment(snapshot,[wrongEvent,wrongSnapshot,selected],'run-A'),selected)
 assert.equal(selectAssessment(snapshot,[wrongEvent,wrongSnapshot],'run-A'),null)
})
test('an explicitly selected older run on the same immutable snapshot remains selectable',()=>{
 const snapshot={snapshot_id:'snapshot-B',incident:{id:'event-B'}}
 const newest={id:'run-new',incident_id:'event-B',evidence_snapshot_id:'snapshot-B'}
 const older={id:'run-old',incident_id:'event-B',evidence_snapshot_id:'snapshot-B'}
 assert.equal(selectAssessment(snapshot,[newest,older],'run-old'),older)
 assert.equal(selectAssessment(snapshot,[newest,older],'deleted-run'),newest)
})
test('removed or corrupted persisted routes recover to an available page',()=>{
 assert.equal(validPage('legacy-removed',['workbench','risk']),'workbench')
 assert.equal(validPage(null,['workbench','risk']),'workbench')
 assert.equal(validPage('risk',['workbench','risk']),'risk')
})
