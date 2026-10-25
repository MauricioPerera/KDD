"""Strict, pure model for explicitly declared requirement relationships."""
import hashlib
import json
import re

from validate_contracts import parse_frontmatter


REQUIREMENT = re.compile(r'REQ-[0-9]{3,}\Z')
TASK = re.compile(r'TASK-[0-9]{3,}\Z')


def _fail(code, message):
    raise ValueError(code + ': ' + message)


def exact_path(value):
    """Accept an exact relative object path without normalizing an escape away."""
    if not isinstance(value, str) or not value:
        _fail('TRACE_INPUT', 'expected a nonempty relative path')
    if value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        _fail('TRACE_INPUT', 'path must be exact and relative: ' + repr(value))
    if re.search(r'[\x00-\x1f\x7f\\:*?\[\]]', value):
        _fail('TRACE_INPUT', 'unsupported path character: ' + repr(value))
    return value


def _schema_path(value, contract=False):
    try:
        path = exact_path(value)
    except ValueError as error:
        _fail('TRACE_SCHEMA', str(error))
    if not path.startswith('knowledge/') or not path.endswith('.md'):
        _fail('TRACE_SCHEMA', 'expected a knowledge Markdown path')
    if contract and (not path.startswith('knowledge/contracts/') or len(path.split('/')) != 3):
        _fail('TRACE_SCHEMA', 'expected a direct task contract path')
    return path


def _single_line(value):
    return (isinstance(value, str) and bool(value.strip())
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _document_body(text):
    if not isinstance(text, str):
        _fail('TRACE_SPEC', 'spec must be text')
    metadata, body = parse_frontmatter(text)
    if not isinstance(metadata, dict) or metadata.get('type') != 'Concept':
        _fail('TRACE_SPEC', 'spec requires Concept frontmatter')
    if not all(_single_line(metadata.get(k)) for k in ('title', 'description')):
        _fail('TRACE_SPEC', 'spec requires title and description')
    tags = metadata.get('tags')
    if not isinstance(tags, list) or not tags or not all(_single_line(t) for t in tags):
        _fail('TRACE_SPEC', 'spec requires nonempty tags')
    return body


def _outside_fences(body):
    fence = None
    for line in body.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            run, tail = marker.groups()
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not tail.strip():
                fence = None
            continue
        if fence is None:
            yield line


def _requirements(text):
    result, sections, active = {}, 0, False
    for line in _outside_fences(_document_body(text)):
        if line.strip() == '## Requisitos':
            sections += 1
            active = True
            continue
        if line.startswith('## '):
            active = False
        if not active or not line.strip():
            continue
        item = re.fullmatch(r'\s*- \[(REQ-[0-9]{3,})\] (.+)', line)
        if not item or not _single_line(item[2]):
            _fail('TRACE_SPEC', 'expected - [REQ-NNN] nonempty text')
        identifier, description = item[1], item[2].strip()
        if identifier in result:
            _fail('TRACE_SPEC', 'duplicate requirement: ' + identifier)
        result[identifier] = description
    if sections != 1 or not result:
        _fail('TRACE_SPEC', 'expected one nonempty Requisitos section')
    return result


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('TRACE_SCHEMA', 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _manifest(text):
    try:
        data = json.loads(text, object_pairs_hook=_unique)
    except (ValueError, TypeError) as error:
        _fail('TRACE_SCHEMA', str(error))
    if not isinstance(data, dict) or set(data) != {'schema_version', 'spec', 'bindings'}:
        _fail('TRACE_SCHEMA', 'expected schema_version, spec and bindings')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        _fail('TRACE_SCHEMA', 'schema_version must be integer 1')
    _schema_path(data['spec'])
    if not isinstance(data['bindings'], list) or not data['bindings']:
        _fail('TRACE_SCHEMA', 'bindings must be a nonempty list')
    return data


def manifest_spec(text):
    """Validate the envelope before the Git reader opens the declared spec."""
    return _manifest(text)['spec']


def _binding(data, requirements):
    if not isinstance(data, dict) or set(data) != {'requirement', 'contract', 'tasks'}:
        _fail('TRACE_SCHEMA', 'expected requirement, contract and tasks')
    identifier = data['requirement']
    if not isinstance(identifier, str) or identifier not in requirements:
        _fail('TRACE_SCHEMA', 'binding references an unknown requirement')
    contract = _schema_path(data['contract'], contract=True)
    tasks = data['tasks']
    if not isinstance(tasks, list) or any(not isinstance(t, str) or not TASK.fullmatch(t) for t in tasks):
        _fail('TRACE_SCHEMA', 'tasks must contain TASK-NNN identifiers')
    if len(set(tasks)) != len(tasks):
        _fail('TRACE_SCHEMA', 'duplicate task assignment')
    return identifier, {'contract': contract, 'tasks': sorted(tasks)}


def _bindings(data, requirements):
    result = {identifier: [] for identifier in requirements}
    pairs, owners = set(), {}
    for item in data:
        identifier, binding = _binding(item, requirements)
        pair = (identifier, binding['contract'])
        if pair in pairs:
            _fail('TRACE_SCHEMA', 'duplicate requirement/contract binding')
        pairs.add(pair)
        for task in binding['tasks']:
            if task in owners and owners[task] != binding['contract']:
                _fail('TRACE_SCHEMA', 'one task cannot name two contracts: ' + task)
            owners[task] = binding['contract']
        result[identifier].append(binding)
    if any(not links for links in result.values()):
        _fail('TRACE_SCHEMA', 'every requirement must have a binding')
    return result


def parse_plan(spec_text, manifest_text):
    """Parse declared requirements and bindings; never infer coverage."""
    manifest = _manifest(manifest_text)
    requirements = _requirements(spec_text)
    bindings = _bindings(manifest['bindings'], requirements)
    records = []
    for identifier, description in sorted(requirements.items()):
        links = sorted(bindings[identifier], key=lambda item: item['contract'])
        payload = dict(spec=manifest['spec'], id=identifier, text=description, bindings=links)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        records.append(dict(id=identifier, text=description, bindings=links,
                            fingerprint=hashlib.sha256(raw).hexdigest()))
    return dict(spec=manifest['spec'], requirements=records)
