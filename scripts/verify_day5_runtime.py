"""Read-only verification of the browser-created EVT-008 delivery chain."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def get(path):
    with urlopen('http://127.0.0.1:8000/api/v1/' + path, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/day5-runtime-verification.json')
    args = parser.parse_args()
    baseline = json.loads((ROOT / 'docs/day5-baseline.json').read_text(encoding='utf-8'))
    scene = get('demo-scenarios/evt-008')
    incident = get('incidents/' + scene['incident_id'])
    task = get('execution-tasks/' + scene['root_task_id'])
    run = get('runs/' + task['source_run_id'])
    snapshot = get('evidence-snapshots/' + task['evidence_snapshot_id'])
    report = get('runs/' + run['id'] + '/assessment-report')
    execution_report = get('execution-tasks/' + task['id'] + '/report')
    situation = get('situation')
    current_incidents, current_runs, current_tasks = get('incidents'), get('runs'), get('execution-tasks')
    restored_snapshots = {sid: get('evidence-snapshots/' + sid) for sid in baseline['snapshots']}
    checks = {
        'event_code': incident.get('code') == 'EVT-008',
        'task_code': task['code'] == 'TASK-008',
        'device_link': 'dev-temp-01' in task['device_ids'],
        'building_link': task['target_building_id'] == 'loc-training',
        'resource_link': task['resource_code'] == 'UAV-003',
        'task_completed': task['status'] == 'completed' and task['progress'] == 100,
        'event_links': all(item['incident_id'] == incident['id'] for item in [task, run, report, execution_report]),
        'snapshot_links': all(item['evidence_snapshot_id'] == snapshot['snapshot_id'] for item in [task, run, report, execution_report]),
        'report_link': run['result']['report_id'] == report['id'],
        'rule_analysis_explicit': report['analysis_kind'] == 'rule_based' and report['is_simulated'],
        'event_not_auto_closed': incident['status'] == 'open',
        'execution_needs_review': execution_report['verification_status'] == 'requires_human_review',
        'map_has_task': any(item['id'] == task['id'] and item['status'] == 'completed' for item in situation['execution_tasks']),
        'old_snapshots_unchanged': baseline['snapshots'] == restored_snapshots,
        'old_incidents_preserved': {item['id'] for item in baseline['incidents']} <= {item['id'] for item in current_incidents},
        'old_runs_preserved': {item['id'] for item in baseline['runs']} <= {item['id'] for item in current_runs},
        'old_tasks_preserved': {item['id'] for item in baseline['execution_tasks']} <= {item['id'] for item in current_tasks},
        'old_map_tasks_preserved': {item['id'] for item in baseline['situation']['tasks']} <= {item['id'] for item in situation['tasks']},
        'old_patrols_preserved': {item['id'] for item in baseline['situation']['patrols']} <= {item['id'] for item in situation['patrols']},
    }
    data = {'checked_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
            'scenario': scene, 'incident': incident, 'task': task, 'run': run,
            'assessment_report': report, 'execution_report': execution_report,
            'counts': {'incidents': len(current_incidents), 'runs': len(current_runs), 'execution_tasks': len(current_tasks)}}
    output = ROOT / args.output
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checks': checks, 'output': str(output)}, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise SystemExit('Runtime verification failed; see output.')


if __name__ == '__main__':
    main()
