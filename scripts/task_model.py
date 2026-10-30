"""Pure Task v1 nodes; Git is the history, not an embedded event list."""
import re
from pathlib import PurePosixPath

from validate_contracts import parse_frontmatter


class TaskError(ValueError):
    """A task operation was rejected."""


STATES = ('backlog', 'ready', 'in_progress', 'needs_human_input', 'done')
EDGES = {('backlog', 'ready'), ('ready', 'in_progress'),
         ('in_progress', 'needs_human_input'), ('needs_human_input', 'ready'),
         ('in_progress', 'done')}
FIELDS = ('type', 'title', 'description', 'tags', 'task_id', 'status',
          'branch', 'contract', 'assignee', 'depends_on', 'approved_ref',
          'branch_base', 'reason', 'verified_ref', 'evidence', 'evidence_sha256')
ID = re.compile(r'TASK-[0-9]{3,}\Z')
SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


def text(value, required=True):
    return (isinstance(value, str) and (bool(value.strip()) or not required)
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def valid_id(value):
    return isinstance(value, str) and bool(ID.fullmatch(value))


def valid_sha(value):
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def task_path(task_id):
    if not valid_id(task_id):
        raise TaskError('TASK_ID: expected TASK-NNN')
    return 'knowledge/tasks/{}.md'.format(task_id)


def _list_errors(data):
    errors = []
    tags, dependencies = data.get('tags'), data.get('depends_on')
    if not isinstance(tags, list) or not tags:
        errors.append('TASK_TAGS: expected a nonempty list')
    elif any(not isinstance(t, str) or not re.fullmatch(r'[a-z0-9_-]+', t) for t in tags):
        errors.append('TASK_TAGS: expected lowercase tags')
    if not isinstance(dependencies, list) or any(not valid_id(d) for d in dependencies):
        errors.append('TASK_DEPENDENCIES: expected task IDs')
    elif len(set(dependencies)) != len(dependencies) or data.get('task_id') in dependencies:
        errors.append('TASK_DEPENDENCIES: duplicate or self dependency')
    return errors


def _identity_errors(data):
    errors = []
    if not valid_id(data.get('task_id')):
        errors.append('TASK_ID: expected TASK-NNN')
    if data.get('branch') != 'task/{}'.format(data.get('task_id')):
        errors.append('TASK_BRANCH: branch must match the task ID')
    contract = data.get('contract')
    if not isinstance(contract, str) or not re.fullmatch(r'knowledge/contracts/[\w.-]+\.md', contract):
        errors.append('TASK_CONTRACT: expected an exact contract path')
    elif PurePosixPath(contract).name.startswith('TEMPLATE-'):
        errors.append('TASK_CONTRACT: a template is not an approved contract')
    return errors


def _state_errors(data):
    errors = []
    status = data.get('status')
    if status not in STATES:
        errors.append('TASK_STATUS: unknown status')
    for name in ('approved_ref', 'branch_base', 'verified_ref'):
        if data.get(name) and not valid_sha(data[name]):
            errors.append('TASK_REF: {} requires a full commit SHA'.format(name))
    if status != 'backlog' and not data.get('approved_ref'):
        errors.append('TASK_APPROVAL: an explicit approved reference is required')
    if status in ('in_progress', 'needs_human_input', 'done'):
        if not data.get('assignee') or not data.get('branch_base'):
            errors.append('TASK_OWNER: owner and branch base are required')
    if status == 'backlog' and any(data.get(k) for k in ('approved_ref', 'branch_base', 'assignee')):
        errors.append('TASK_BACKLOG: approval and execution have not started')
    return errors


def _evidence_errors(data):
    fields = ('verified_ref', 'evidence', 'evidence_sha256')
    if data.get('status') != 'done':
        return ['TASK_EVIDENCE: only done may contain proof'] if any(data.get(k) for k in fields) else []
    expected = 'docs/task-evidence/{}-{}.json'.format(data.get('task_id'), data.get('verified_ref'))
    valid = (valid_sha(data.get('verified_ref')) and data.get('evidence') == expected
             and isinstance(data.get('evidence_sha256'), str)
             and bool(re.fullmatch(r'[0-9a-f]{64}', data['evidence_sha256'])))
    return [] if valid else ['TASK_EVIDENCE: done requires a tested SHA and sealed evidence']


def validate_task(data):
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        return ['TASK_SCHEMA: unexpected or missing fields']
    required = {'title', 'description', 'task_id', 'reason', 'contract', 'branch'}
    errors = ['TASK_TEXT: invalid {}'.format(k) for k in FIELDS
              if k not in ('tags', 'depends_on') and not text(data[k], k in required)]
    if data['type'] != 'Task':
        errors.append('TASK_TYPE: expected Task')
    return errors + _list_errors(data) + _identity_errors(data) + _state_errors(data) + _evidence_errors(data)


def new_task(task_id, title, description, contract, dependencies=()):
    data = dict.fromkeys(FIELDS, '')
    data.update(type='Task', title=title, description=description, tags=['task'],
                task_id=task_id, status='backlog', branch='task/' + task_id,
                contract=contract, depends_on=list(dependencies), reason='Created')
    errors = validate_task(data)
    if errors:
        raise TaskError('; '.join(errors))
    return data


def _quote(value):
    return "'{}'".format(value.replace("'", "''"))


def render_task(data, body=None):
    errors = validate_task(data)
    if errors:
        raise TaskError('; '.join(errors))
    lines = ['---']
    for key in FIELDS:
        value = data[key]
        encoded = '[' + ', '.join(_quote(v) for v in value) + ']' if isinstance(value, list) else _quote(value)
        lines.append('{}: {}'.format(key, encoded))
    if body is None:
        body = '\n# {}\n\n[Approved contract](../contracts/{})\n'.format(
            data['title'], PurePosixPath(data['contract']).name)
    return '\n'.join(lines + ['---']) + '\n' + body


def parse_task(source, filename=None):
    lines = source.lstrip('\n').splitlines()
    if not lines or lines[0] != '---' or '---' not in lines[1:]:
        raise TaskError('TASK_FRONTMATTER: missing frontmatter')
    end = lines.index('---', 1)
    keys = [line.split(':', 1)[0] for line in lines[1:end] if ':' in line]
    if len(keys) != len(set(keys)):
        raise TaskError('TASK_FRONTMATTER: duplicate metadata')
    data, body = parse_frontmatter(source)
    errors = validate_task(data)
    if filename and isinstance(data, dict) and PurePosixPath(filename).name != str(data.get('task_id')) + '.md':
        errors.append('TASK_FILENAME: node name does not match task_id')
    if errors:
        raise TaskError('; '.join(errors))
    return data, body


def validate_transition(before, after, completed=()):
    """Return violations without mutation; creation starts in backlog, done is terminal."""
    if after is None:
        return ['TASK_DELETE: task history cannot be deleted']
    errors = validate_task(after)
    if errors:
        return errors
    if before is None:
        return [] if after['status'] == 'backlog' else ['TASK_CREATE: start in backlog']
    errors = _transition_fields(before, after)
    if (before['status'], after['status']) not in EDGES:
        errors.append('TASK_TRANSITION: {} -> {} is forbidden'.format(before['status'], after['status']))
    if after['status'] == 'in_progress' and not set(after['depends_on']).issubset(completed):
        errors.append('TASK_DEPENDENCIES: prerequisites are not done')
    return errors


def _transition_fields(before, after):
    errors = []
    for key in ('task_id', 'type', 'branch', 'contract', 'depends_on'):
        if before[key] != after[key]:
            errors.append('TASK_IMMUTABLE: ' + key)
    for key in ('approved_ref', 'branch_base'):
        if before[key] and before[key] != after[key]:
            errors.append('TASK_IMMUTABLE: ' + key)
    if before['status'] == 'done':
        errors.append('TASK_TERMINAL: done is immutable')
    return errors
