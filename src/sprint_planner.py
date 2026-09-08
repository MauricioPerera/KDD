"""Explain and rank executable sprint tasks without dispatch or reservations."""
import argparse
import json
from pathlib import Path

from src.sprint_admission import validate_admission
from src.sprint_graph import cyclic_components, inherited_priorities, reachable, satisfied_tasks


PRIORITIES = ('low', 'medium', 'high', 'urgent')
TASK_STATES = ('backlog', 'ready', 'in_progress', 'done', 'cancelled')
RELATIONS = ('related_to', 'duplicates', 'goal', 'contract')


def _text(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _ids(value):
    return (isinstance(value, list) and all(_text(item) for item in value)
            and len(set(value)) == len(value))


def _evidence(value):
    return value is None or (isinstance(value, dict)
                             and type(value.get('valid')) is bool
                             and _text(value.get('reference')))


def _blockers(values):
    if not isinstance(values, list):
        return False
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            return False
        if not all(_text(value.get(k)) for k in ('id', 'reason', 'owner', 'condition')):
            return False
        if value.get('status') not in ('open', 'resolved') or value['id'] in seen:
            return False
        seen.add(value['id'])
    return True


def _relations(values):
    if not isinstance(values, list):
        return False
    seen = set()
    for value in values:
        if not isinstance(value, dict) or value.get('type') not in RELATIONS:
            return False
        if not _text(value.get('target')):
            return False
        pair = (value['type'], value['target'])
        if pair in seen:
            return False
        seen.add(pair)
    return True


def _task_shape(task):
    if not isinstance(task, dict):
        return False
    return (_text(task.get('id')) and task.get('status') in TASK_STATES
            and task.get('priority') in PRIORITIES and _ids(task.get('dependencies'))
            and type(task.get('estimated_cost')) is int and task['estimated_cost'] >= 0
            and task.get('phase', 'implementation') in ('implementation', 'verification')
            and _evidence(task.get('evidence')) and _blockers(task.get('blockers', []))
            and _relations(task.get('relations', [])))


def _sprint_shape(sprint):
    if not isinstance(sprint, dict) or not _ids(sprint.get('selected_tasks')):
        return False
    derived = dict(sprint, completed_tasks=[])
    sample = {'task_id': '__schema__', 'dependencies': [], 'estimated_cost': 0,
              'phase': 'implementation'}
    result = validate_admission({'sprint': derived, 'request': sample})
    return ('INVALID_INPUT' not in result['reasons']
            and _text(sprint['budget']['unit']))


def _input_errors(data):
    if not isinstance(data, dict) or not _sprint_shape(data.get('sprint')):
        return [{'code': 'INVALID_INPUT', 'path': 'sprint'}]
    values = data.get('tasks')
    if not isinstance(values, list):
        return [{'code': 'INVALID_INPUT', 'path': 'tasks'}]
    errors, known = [], set()
    for index, task in enumerate(values):
        if not _task_shape(task):
            errors.append({'code': 'INVALID_INPUT', 'path': f'tasks[{index}]'})
        elif task['id'] in known:
            errors.append({'code': 'DUPLICATE_TASK', 'task_id': task['id']})
        else:
            known.add(task['id'])
    if errors:
        return errors
    return _reference_errors(data, known)


def _reference_errors(data, known):
    errors = []
    for key in sorted(set(data['sprint']['selected_tasks']) - known):
        errors.append({'code': 'UNKNOWN_SELECTION', 'task_id': key})
    for task in sorted(data['tasks'], key=lambda t: t['id']):
        for key in sorted(set(task['dependencies']) - known):
            errors.append({'code': 'UNKNOWN_DEPENDENCY', 'task_id': task['id'], 'target': key})
        for relation in sorted(task.get('relations', []), key=lambda r: (r['type'], r['target'])):
            if relation['type'] in ('related_to', 'duplicates') and relation['target'] not in known:
                errors.append({'code': 'UNKNOWN_RELATION', 'task_id': task['id'],
                               'target': relation['target']})
    return errors


def _local_causes(task, cyclic, satisfied):
    key = task['id']
    if key in satisfied:
        return []
    causes = []
    if key in cyclic:
        causes.append({'task_id': key, 'code': 'DEPENDENCY_CYCLE'})
    status_codes = {'backlog': 'TASK_NOT_READY', 'in_progress': 'IN_PROGRESS',
                    'cancelled': 'TASK_CANCELLED'}
    if task['status'] in status_codes:
        causes.append({'task_id': key, 'code': status_codes[task['status']]})
    proof = task.get('evidence')
    if task['status'] == 'done' and (proof is None or not proof['valid']):
        causes.append({'task_id': key, 'code': 'EVIDENCE_INVALID'})
    for blocker in task.get('blockers', []):
        if blocker['status'] == 'open':
            causes.append({'task_id': key, 'code': 'MANUAL_BLOCKER',
                           'blocker': {k: blocker[k] for k in ('id', 'reason', 'owner', 'condition', 'status')}})
    return causes


def _admission(task, sprint, satisfied):
    request = {'task_id': task['id'], 'dependencies': [d for d in task['dependencies'] if d != task['id']],
               'estimated_cost': task['estimated_cost'], 'phase': task.get('phase', 'implementation')}
    # Self dependencies are diagnosed by SCCs, rather than passed as invalid requests.
    return validate_admission({'sprint': dict(sprint, completed_tasks=sorted(satisfied)),
                               'request': request})['reasons']


def _deduplicate(causes):
    keyed = {json.dumps(c, sort_keys=True): c for c in causes}
    return sorted(keyed.values(), key=lambda c: (c['task_id'], c['code'],
                                                c.get('blocker', {}).get('id', '')))


def _root_causes(key, pending_graph, local):
    causes = list(local[key])
    seen = {key}
    pending = list(pending_graph[key])
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        causes.extend(local[current])
        if not local[current] and not pending_graph[current]:
            causes.append({'task_id': current, 'code': 'DEPENDENCY_PENDING'})
        pending.extend(pending_graph[current])
    return _deduplicate(causes)


def _task_rows(tasks, sprint, graph, cycles, satisfied, priorities):
    pending_graph = {key: [d for d in deps if d not in satisfied] for key, deps in graph.items()}
    cyclic = {key for component in cycles for key in component}
    local, reasons = {}, {}
    for key, task in tasks.items():
        local[key] = _local_causes(task, cyclic, satisfied)
        admission = [] if key in satisfied else _admission(task, sprint, satisfied)
        for code in admission:
            if code != 'DEPENDENCIES_PENDING':
                local[key].append({'task_id': key, 'code': code})
        reasons[key] = sorted(set(admission + [c['code'] for c in local[key]]))
        if pending_graph[key] and 'DEPENDENCIES_PENDING' not in reasons[key]:
            reasons[key] = sorted(reasons[key] + ['DEPENDENCIES_PENDING'])
        if key in satisfied:
            reasons[key] = ['TASK_COMPLETED']
    rows = []
    for key, task in tasks.items():
        rank, sources, unlocks = priorities[key]
        rows.append({'id': key, 'satisfied': key in satisfied,
                     'eligible': task['status'] == 'ready' and not reasons[key],
                     'reasons': reasons[key], 'blocked_by': pending_graph[key],
                     'root_causes': _root_causes(key, pending_graph, local),
                     'priority': task['priority'], 'effective_priority': PRIORITIES[rank],
                     'priority_sources': sources, 'unlocks': unlocks,
                     'relations': sorted([{'type': r['type'], 'target': r['target']}
                                          for r in task.get('relations', [])],
                                         key=lambda r: (r['type'], r['target'])),
                     'recheck_on': sorted(reachable(graph, key))})
    return rows


def plan_sprint(data: dict) -> dict:
    """Recompute a deterministic plan from a trusted snapshot. Never dispatch."""
    errors = _input_errors(data)
    result = {'valid': not errors, 'errors': errors, 'cycles': [], 'executable': [],
              'next_task': None, 'tasks': []}
    if errors:
        return result
    tasks = {t['id']: t for t in sorted(data['tasks'], key=lambda t: t['id'])}
    graph = {key: sorted(t['dependencies']) for key, t in tasks.items()}
    cycles = cyclic_components(graph)
    satisfied = satisfied_tasks(tasks, graph)
    pending_graph = {key: [d for d in deps if d not in satisfied] for key, deps in graph.items()}
    priorities = inherited_priorities(tasks, pending_graph, set(data['sprint']['selected_tasks']),
                                      satisfied, {p: i for i, p in enumerate(PRIORITIES)})
    rows = _task_rows(tasks, data['sprint'], graph, cycles, satisfied, priorities)
    eligible = [row for row in rows if row['eligible']]
    eligible.sort(key=lambda r: (-priorities[r['id']][0], -len(r['unlocks']), r['id']))
    result.update(cycles=cycles, tasks=rows, executable=[r['id'] for r in eligible],
                  next_task=eligible[0]['id'] if eligible else None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.snapshot.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError):
        data = None
    result = plan_sprint(data)
    print(json.dumps(result, sort_keys=True))
    if not result['valid']:
        return 2
    return 0 if result['next_task'] is not None else 1


if __name__ == '__main__':
    raise SystemExit(main())
