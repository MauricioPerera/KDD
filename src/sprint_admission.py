"""Read-only sprint admission checks. No dispatch or budget reservation."""
import argparse
import json
from pathlib import Path


def _identifier(value):
    return isinstance(value, str) and bool(value.strip())


def _identifiers(value):
    return (isinstance(value, list) and all(_identifier(item) for item in value)
            and len(set(value)) == len(value))


def _amount(value):
    return type(value) is int and value >= 0


def _valid_budget(budget):
    if not isinstance(budget, dict):
        return False
    amounts = ('limit', 'consumed', 'verification_reserve')
    return (_identifier(budget.get('unit'))
            and all(_amount(budget.get(key)) for key in amounts)
            and budget['verification_reserve'] <= budget['limit'])


def _valid_input(data):
    if not isinstance(data, dict):
        return False
    sprint, request = data.get('sprint'), data.get('request')
    if not isinstance(sprint, dict) or not isinstance(request, dict):
        return False
    return (
        sprint.get('status') in ('draft', 'active', 'paused', 'closed', 'cancelled')
        and _identifiers(sprint.get('selected_tasks'))
        and _identifiers(sprint.get('completed_tasks'))
        and _valid_budget(sprint.get('budget'))
        and _identifier(request.get('task_id'))
        and _identifiers(request.get('dependencies'))
        and request['task_id'] not in request['dependencies']
        and _amount(request.get('estimated_cost'))
        and request.get('phase') in ('implementation', 'verification')
    )


def validate_admission(data: dict) -> dict:
    """Return an ordered decision about a trusted, non-reserving snapshot."""
    if not _valid_input(data):
        return {'admitted': False, 'reasons': ['INVALID_INPUT']}
    sprint, request = data['sprint'], data['request']
    budget = sprint['budget']
    cost = request['estimated_cost']
    reserve = budget['verification_reserve']
    if request['phase'] == 'verification':
        reserve = max(0, reserve - cost)
    checks = (
        ('SPRINT_NOT_ACTIVE', sprint['status'] != 'active'),
        ('TASK_NOT_SELECTED', request['task_id'] not in sprint['selected_tasks']),
        ('DEPENDENCIES_PENDING', not set(request['dependencies']).issubset(
            sprint['completed_tasks'])),
        ('BUDGET_EXCEEDED', budget['consumed'] + cost + reserve > budget['limit']),
    )
    reasons = [code for code, failed in checks if failed]
    return {'admitted': not reasons, 'reasons': reasons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.snapshot.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError):
        data = None
    result = validate_admission(data)
    print(json.dumps(result, sort_keys=True))
    if 'INVALID_INPUT' in result['reasons']:
        return 2
    return 0 if result['admitted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
