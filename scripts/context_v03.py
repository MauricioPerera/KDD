"""Opt-in, fail-closed compatibility profile for CCDD context contracts v0.3."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:
    yaml = None
    Draft202012Validator = None


class ContextError(ValueError):
    def __init__(self, code, status='INVALID'):
        super().__init__(code)
        self.code = code
        self.status = status


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ContextError('INVALID_ARGUMENTS')


def _mapping(value, required, allowed):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - allowed:
        raise ContextError('INVALID_STRUCTURE')
    if any(not isinstance(key, str) for key in value):
        raise ContextError('INVALID_STRUCTURE')
    return value


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ContextError('INVALID_STRUCTURE')
    return value


def _integer(value, minimum):
    if type(value) is not int or value < minimum:
        raise ContextError('INVALID_STRUCTURE')
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ContextError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ContextError('INVALID_JSON')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContextError('INVALID_JSON') from exc


def _yaml(raw):
    if yaml is None:
        raise ContextError('DEPENDENCIES_MISSING')

    class StrictLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            pairs = []
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str):
                    raise ContextError('INVALID_YAML')
                pairs.append((key, self.construct_object(value_node, deep=deep)))
            return _pairs(pairs)

    try:
        text = raw.decode('utf-8')
        if any(getattr(event, 'anchor', None) is not None for event in yaml.parse(text, Loader=StrictLoader)):
            raise ContextError('YAML_ALIAS_OR_ANCHOR')
        return yaml.load(text, Loader=StrictLoader)
    except (UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise ContextError('INVALID_YAML') from exc


def _regular(root, relative):
    if (not isinstance(relative, str) or not relative or relative.startswith('/')
            or any(char in relative for char in '\\:\0\r\n')
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ContextError('UNSAFE_PATH')
    path = root
    try:
        for part in relative.split('/'):
            path = path / part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ContextError('UNSAFE_PATH')
        if not path.is_file():
            raise ContextError('INVALID_FILE')
    except OSError as exc:
        raise ContextError('INVALID_FILE') from exc
    return path


def _read(root, relative, snapshot):
    try:
        raw = _regular(root, relative).read_bytes()
    except OSError as exc:
        raise ContextError('INVALID_FILE') from exc
    if relative in snapshot and snapshot[relative] != raw:
        raise ContextError('INPUTS_CHANGED')
    snapshot[relative] = raw
    return raw


def _optional(root, relative, snapshot):
    path = root / relative
    if not os.path.lexists(path):
        snapshot[relative] = None
        return None
    return _read(root, relative, snapshot)


def _check_snapshot(root, snapshot):
    for relative, original in snapshot.items():
        if original is None:
            if os.path.lexists(root / relative):
                raise ContextError('INPUTS_CHANGED')
        else:
            try:
                if _regular(root, relative).read_bytes() != original:
                    raise ContextError('INPUTS_CHANGED')
            except OSError as exc:
                raise ContextError('INPUTS_CHANGED') from exc


def _unicode(raw):
    try:
        return raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    except UnicodeError as exc:
        raise ContextError('INVALID_UTF8') from exc


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _forbid_refs(value):
    if isinstance(value, dict):
        if '$ref' in value or '$dynamicRef' in value:
            raise ContextError('SCHEMA_REFERENCE_UNSUPPORTED')
        for child in value.values():
            _forbid_refs(child)
    elif isinstance(value, list):
        for child in value:
            _forbid_refs(child)


def _schema(raw):
    if Draft202012Validator is None:
        raise ContextError('DEPENDENCIES_MISSING')
    data = _json(raw)
    if not isinstance(data, (dict, bool)):
        raise ContextError('INVALID_SCHEMA')
    if isinstance(data, dict) and data.get('$schema', 'https://json-schema.org/draft/2020-12/schema') != 'https://json-schema.org/draft/2020-12/schema':
        raise ContextError('UNSUPPORTED_SCHEMA_DRAFT')
    _forbid_refs(data)
    try:
        Draft202012Validator.check_schema(data)
    except Exception as exc:
        raise ContextError('INVALID_SCHEMA') from exc
    return data


def _budget(budget):
    _mapping(budget, {'model', 'max_tokens'}, {'model', 'max_tokens', 'reserve_output'})
    _text(budget['model'])
    maximum = _integer(budget['max_tokens'], 1)
    reserve = _integer(budget.get('reserve_output', 0), 0)
    if maximum <= reserve:
        raise ContextError('INVALID_BUDGET')
    return maximum - reserve


def _slot(slot, ids):
    _mapping(slot, {'id', 'priority', 'source', 'compaction'},
             {'id', 'priority', 'source', 'compaction', 'min_tokens', 'max_tokens', 'review_quorum'})
    sid = _text(slot['id'])
    if not re.fullmatch(r'[a-z][a-z0-9_]*', sid) or sid in ids:
        raise ContextError('INVALID_SLOT_ID')
    ids.add(sid)
    _integer(slot['priority'], 0)
    if slot['compaction'] not in ('none', 'truncate', 'summarize'):
        raise ContextError('UNSUPPORTED_COMPACTION')
    for field, minimum in (('min_tokens', 0), ('max_tokens', 1), ('review_quorum', 1)):
        if field in slot:
            _integer(slot[field], minimum)
    source = _mapping(slot['source'], {'type'}, {'type', 'path', 'sign', 'provider'})
    if source['type'] == 'static':
        _mapping(source, {'type', 'path'}, {'type', 'path', 'sign'})
        _text(source['path'])
        if 'sign' in source and type(source['sign']) is not bool:
            raise ContextError('INVALID_STRUCTURE')
    elif source['type'] == 'dynamic':
        _mapping(source, {'type', 'provider'}, {'type', 'provider'})
        _text(source['provider'])
    elif source['type'] == 'runtime':
        _mapping(source, {'type'}, {'type'})
    else:
        raise ContextError('UNSUPPORTED_SOURCE')


def _guard(guard, ids, seen, root, snapshot, schemas):
    _mapping(guard, {'id', 'type', 'on_fail'},
             {'id', 'type', 'on_fail', 'pattern', 'target_slot', 'schema_path'})
    gid = _text(guard['id'])
    if gid in seen:
        raise ContextError('DUPLICATE_GUARDRAIL')
    seen.add(gid)
    if guard['on_fail'] not in ('abort', 'warn'):
        raise ContextError('UNSUPPORTED_GUARDRAIL_ACTION')
    kind = guard['type']
    if kind == 'regex_deny':
        _mapping(guard, {'id', 'type', 'on_fail', 'pattern'}, {'id', 'type', 'on_fail', 'pattern'})
        try:
            re.compile(_text(guard['pattern']))
        except re.error as exc:
            raise ContextError('INVALID_REGEX') from exc
    elif kind == 'json_schema':
        _mapping(guard, {'id', 'type', 'on_fail', 'target_slot', 'schema_path'},
                 {'id', 'type', 'on_fail', 'target_slot', 'schema_path'})
        if guard['target_slot'] not in ids:
            raise ContextError('INVALID_SLOT_REFERENCE')
        schemas[gid] = _schema(_read(root, guard['schema_path'], snapshot))
    elif kind == 'reference_check':
        _mapping(guard, {'id', 'type', 'on_fail'}, {'id', 'type', 'on_fail', 'target_slot'})
        if 'target_slot' in guard and guard['target_slot'] not in ids:
            raise ContextError('INVALID_SLOT_REFERENCE')
    else:
        raise ContextError('UNSUPPORTED_GUARDRAIL')


def _load(directory):
    if yaml is None or Draft202012Validator is None:
        raise ContextError('DEPENDENCIES_MISSING')
    try:
        root = Path(directory).resolve(strict=True)
    except OSError as exc:
        raise ContextError('INVALID_DIRECTORY') from exc
    if not root.is_dir():
        raise ContextError('INVALID_DIRECTORY')
    snapshot, schemas = {}, {}
    data = _yaml(_read(root, 'context.yaml', snapshot))
    _mapping(data, {'ccdd_version', 'contract'}, {'ccdd_version', 'contract'})
    if data['ccdd_version'] != '0.3':
        raise ContextError('UNSUPPORTED_VERSION')
    contract = _mapping(data['contract'], {'name', 'budget', 'slots'}, {'name', 'budget', 'slots', 'guardrails'})
    _text(contract['name'])
    available = _budget(contract['budget'])
    slots = contract['slots']
    if not isinstance(slots, list) or not slots:
        raise ContextError('INVALID_SLOTS')
    ids, signed, static = set(), {}, {}
    for slot in slots:
        _slot(slot, ids)
        source = slot['source']
        if source['type'] == 'static':
            content = _unicode(_read(root, source['path'], snapshot))
            static[slot['id']] = content
            if source.get('sign', False):
                signed[slot['id']] = _digest(content)
    manifest = _optional(root, 'expected-hashes.json', snapshot)
    if (signed and manifest is None) or (manifest is not None and _json(manifest) != signed):
        raise ContextError('STATIC_HASH_MISMATCH')
    guards = contract.get('guardrails', [])
    if not isinstance(guards, list):
        raise ContextError('INVALID_GUARDRAILS')
    seen = set()
    for guard in guards:
        _guard(guard, ids, seen, root, snapshot, schemas)
    for name in ('reviewers.json', 'attestations.json'):
        _optional(root, name, snapshot)
    _check_snapshot(root, snapshot)
    return {'root': root, 'contract': contract, 'available': available, 'slots': slots,
            'guards': guards, 'schemas': schemas, 'static': static, 'snapshot': snapshot}


def _inputs(path, slots):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ContextError('INVALID_INPUTS') from exc
    inputs = _json(raw)
    expected = {slot['id'] for slot in slots if slot['source']['type'] != 'static'}
    if not isinstance(inputs, dict) or set(inputs) != expected or any(not isinstance(v, str) for v in inputs.values()):
        raise ContextError('INVALID_INPUTS')
    return inputs, raw


def _tokens(text):
    return (len(text) + 3) // 4


def _allocate(loaded, inputs):
    used, values = 0, {}
    for slot in sorted(loaded['slots'], key=lambda item: item['priority']):
        sid = slot['id']
        text = (loaded['static'][sid] if slot['source']['type'] == 'static' else inputs[sid]).strip()
        wanted = _tokens(text)
        remaining = loaded['available'] - used
        grant = min(wanted, slot.get('max_tokens', wanted), remaining)
        if slot['compaction'] == 'none':
            if wanted > remaining:
                raise ContextError('BUDGET_EXCEEDED', 'BLOCKED')
            grant = wanted
        if grant < min(wanted, slot.get('min_tokens', 0)):
            raise ContextError('SLOT_FLOOR', 'BLOCKED')
        kept = text if grant >= wanted else text[:grant * 4]
        values[sid] = kept
        used += _tokens(kept)
    return values, used


def _guardrails(loaded, values):
    results = []
    joined = '\n'.join(values.values())
    for guard in loaded['guards']:
        kind = guard['type']
        passed = True
        if kind == 'regex_deny':
            passed = re.search(guard['pattern'], joined) is None
        elif kind == 'json_schema':
            try:
                instance = _json(values[guard['target_slot']].encode('utf-8'))
                passed = Draft202012Validator(loaded['schemas'][guard['id']]).is_valid(instance)
            except (ContextError, ValueError, RecursionError):
                passed = False
        results.append({'id': guard['id'], 'passed': passed})
        if not passed and guard['on_fail'] == 'abort':
            raise ContextError('GUARDRAIL_BLOCKED', 'BLOCKED')
    return results


def _assemble(loaded, path):
    inputs, original = _inputs(path, loaded['slots'])
    values, used = _allocate(loaded, inputs)
    guards = _guardrails(loaded, values)
    payload = '\n\n'.join('<<{}>>\n{}'.format(slot['id'], values[slot['id']])
                           for slot in loaded['slots'] if values[slot['id']])
    try:
        if Path(path).read_bytes() != original:
            raise ContextError('INPUTS_CHANGED')
    except OSError as exc:
        raise ContextError('INPUTS_CHANGED') from exc
    _check_snapshot(loaded['root'], loaded['snapshot'])
    return {'payload': payload, 'payload_sha256': _digest(payload), 'tokens_used': used,
            'tokens_available': loaded['available'], 'guardrails': guards}


def _slot_diff(base, candidate, old, new, findings):
    old_source, new_source = old['source'], new['source']
    if old_source.get('type') != new_source.get('type'):
        findings.add('SLOT_SOURCE_CHANGED')
    elif old_source.get('provider') != new_source.get('provider') or old_source.get('path') != new_source.get('path'):
        findings.add('SLOT_SOURCE_CHANGED')
    if old_source.get('sign', False) and not new_source.get('sign', False):
        findings.add('SLOT_SIGNATURE_REMOVED')
    if new.get('review_quorum', 1) < old.get('review_quorum', 1):
        findings.add('QUORUM_DECREASED')
    if old['compaction'] == 'none':
        if new['compaction'] != 'none' or new['priority'] > old['priority']:
            findings.add('CRITICAL_SLOT_WEAKENED')
        if new.get('min_tokens', 0) < old.get('min_tokens', 0):
            findings.add('CRITICAL_FLOOR_DECREASED')
    sid = old['id']
    if sid in base['static'] and sid in candidate['static'] and base['static'][sid] != candidate['static'][sid]:
        findings.add('REVIEW_REQUIRED')


def _guard_diff(base, candidate, findings):
    before = {guard['id']: guard for guard in base['guards']}
    after = {guard['id']: guard for guard in candidate['guards']}
    strength = {'warn': 0, 'abort': 1}
    for gid, old in before.items():
        new = after.get(gid)
        if new is None:
            findings.add('GUARDRAIL_REMOVED')
            continue
        if strength[new['on_fail']] < strength[old['on_fail']]:
            findings.add('GUARDRAIL_WEAKENED')
        old_shape = {k: v for k, v in old.items() if k != 'on_fail'}
        new_shape = {k: v for k, v in new.items() if k != 'on_fail'}
        if old_shape != new_shape:
            findings.add('GUARDRAIL_CHANGED')
        if gid in base['schemas'] and gid in candidate['schemas'] and base['schemas'][gid] != candidate['schemas'][gid]:
            findings.add('GUARDRAIL_SCHEMA_CHANGED')


def _diff(base, candidate):
    findings = set()
    if candidate['available'] < base['available']:
        findings.add('BUDGET_DECREASED')
    old_slots = {slot['id']: slot for slot in base['slots']}
    new_slots = {slot['id']: slot for slot in candidate['slots']}
    if set(old_slots) - set(new_slots):
        findings.add('SLOT_REMOVED')
    if [slot['id'] for slot in base['slots'] if slot['id'] in new_slots] != [slot['id'] for slot in candidate['slots'] if slot['id'] in old_slots]:
        findings.add('SLOT_ORDER_CHANGED')
    for sid in old_slots.keys() & new_slots.keys():
        _slot_diff(base, candidate, old_slots[sid], new_slots[sid], findings)
    old_critical = max((slot['priority'] for slot in base['slots'] if slot['compaction'] == 'none'), default=-1)
    new_critical = max((slot['priority'] for slot in candidate['slots'] if slot['compaction'] == 'none'), default=-1)
    for sid, slot in new_slots.items():
        old = old_slots.get(sid)
        if old is None and slot['source']['type'] == 'static' and slot['compaction'] == 'none':
            findings.add('REVIEW_REQUIRED')
        if slot['source']['type'] == 'dynamic' and slot['priority'] <= new_critical:
            if old is None or old['priority'] > old_critical:
                findings.add('DYNAMIC_IN_CRITICAL_ZONE')
    _guard_diff(base, candidate, findings)
    for name in ('reviewers.json', 'attestations.json'):
        if base['snapshot'][name] != candidate['snapshot'][name]:
            findings.add('REVIEW_REQUIRED')
    _check_snapshot(base['root'], base['snapshot'])
    _check_snapshot(candidate['root'], candidate['snapshot'])
    return sorted(findings)


def main():
    parser = Parser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    lint = sub.add_parser('lint')
    lint.add_argument('directory')
    assembly = sub.add_parser('assemble')
    assembly.add_argument('directory')
    assembly.add_argument('--inputs', required=True)
    diff = sub.add_parser('diff')
    diff.add_argument('baseline')
    diff.add_argument('candidate')
    try:
        args = parser.parse_args()
        if args.command == 'lint':
            _load(args.directory)
            output = {}
        elif args.command == 'assemble':
            output = _assemble(_load(args.directory), args.inputs)
        else:
            findings = _diff(_load(args.baseline), _load(args.candidate))
            if findings:
                print(json.dumps({'status': 'BLOCKED', 'findings': findings,
                                  'governance_verified': False}, sort_keys=True))
                return 3
            output = {}
        output.update(status='PASS', governance_verified=False)
        code = 0
    except ContextError as exc:
        output = {'status': exc.status, 'findings': [exc.code], 'governance_verified': False}
        code = 3 if exc.status == 'BLOCKED' else 2
    except (OSError, ValueError, TypeError, RecursionError):
        output = {'status': 'INVALID', 'findings': ['INVALID_CONTEXT'], 'governance_verified': False}
        code = 2
    print(json.dumps(output, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
