// IDs, not device overlap or current readings, establish an assessment context.
export type AssessmentIdentity={id:string;incident_id:string;evidence_snapshot_id?:string|null}
export type SnapshotIdentity={snapshot_id:string;incident:{id:string}}
export function matchesAssessment(snapshot:SnapshotIdentity,run:AssessmentIdentity|null|undefined):boolean{return !!run&&run.evidence_snapshot_id===snapshot.snapshot_id&&run.incident_id===snapshot.incident.id}
export function selectAssessment<T extends AssessmentIdentity>(snapshot:SnapshotIdentity,runs:T[],preferredId?:string|null):T|null{return runs.find(run=>run.id===preferredId&&matchesAssessment(snapshot,run))||runs.find(run=>matchesAssessment(snapshot,run))||null}
export function validPage(value:string|null,available:string[],fallback='workbench'):string{return value&&available.includes(value)?value:fallback}
