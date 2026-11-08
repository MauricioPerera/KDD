#!/usr/bin/env python3
"""Inspect exact Git candidates and check reviews without granting approval."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

LEVELS = {'low': 0, 'medium': 1, 'high': 2}
LENSES = {'simplicity', 'oracle', 'implementation'}
FACTORS = {'api': 'medium', 'performance': 'medium', 'dependencies': 'medium',
           'security': 'high', 'data-loss': 'high', 'concurrency': 'high',
           'trust-boundary': 'high'}
TRUST_PREFIXES = ('.github/', '.agents/', 'ccdd/', 'quality/')
TRUST_PATHS = {'quality.json', 'acceptance.json', 'knowledge/quality-approval.md',
    'knowledge/acceptance.md', 'knowledge/baseline-risk-review.md'} | {
    'scripts/' + name + '.py' for name in (
        'guard_pr_baseline', 'approval_registry', 'quality_baseline', 'validate_baseline',
        'verify_quality', 'verify_acceptance', 'validation_runtime', 'validate_contracts',
        'run_test_suite', 'process_tree')}
REGULAR = {'100644', '100755'}


class ReviewError(ValueError):
    """The review inputs or Git objects cannot be validated."""


def _reject(code, message):
    raise ReviewError(code + ': ' + message)


def _git(root, *args, data=None, code='REVIEW_GIT'):
    try:
        result = subprocess.run(['git', '--no-replace-objects', '--literal-pathspecs',
            '-C', str(root), *args], input=data, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        _reject(code, 'Git could not complete: ' + str(exc))
    if result.returncode:
        _reject(code, result.stderr.decode('utf-8', 'replace').strip() or 'Git rejected the operation')
    return result.stdout


def _commit(root, ref):
    if not isinstance(ref, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', ref):
        _reject('REVIEW_REF', 'a canonical full commit OID is required')
    raw = _git(root, 'rev-parse', '--show-object-format', '--verify', '--end-of-options',
               ref + '^{commit}', code='REVIEW_REF').decode('ascii').splitlines()
    if len(raw) != 2 or len(ref) != {'sha1': 40, 'sha256': 64}.get(raw[0]) or raw[1] != ref:
        _reject('REVIEW_REF', 'reference does not identify its native commit object')
    return ref


def _path(value, code='REVIEW_SOURCE'):
    if (not isinstance(value, str) or not value or '\x00' in value or '\\' in value
            or PurePosixPath(value).is_absolute() or re.match(r'^[A-Za-z]:', value)
            or any(part in ('', '.', '..', '.git') for part in value.split('/'))):
        _reject(code, 'a repository-relative exact source path is required')
    return value


def _side(mode, oid):
    if mode == '000000':
        if set(oid) != {'0'}:
            _reject('REVIEW_GIT', 'absent path has a nonzero object')
        return None
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', oid):
        _reject('REVIEW_GIT', 'invalid object in diff')
    return {'mode': mode, 'oid': oid}


def _changes(raw):
    if not raw:
        return []
    fields = raw.split(b'\0')
    if fields.pop() != b'' or len(fields) % 2:
        _reject('REVIEW_GIT', 'incomplete Git diff')
    result = []
    try:
        for offset in range(0, len(fields), 2):
            metadata = fields[offset].decode('ascii').split()
            if len(metadata) != 5 or not metadata[0].startswith(':') or metadata[4] not in {'A', 'D', 'M', 'T'}:
                _reject('REVIEW_GIT', 'unrecognized Git diff record')
            before, after, old, new, _ = metadata
            result.append({'path': _path(fields[offset + 1].decode('utf-8')),
                           'before': _side(before[1:], old), 'after': _side(after, new)})
    except UnicodeError:
        _reject('REVIEW_GIT', 'diff paths must be valid UTF-8')
    return sorted(result, key=lambda item: item['path'])


def _path_risk(change):
    path = change['path']
    if path in TRUST_PATHS or path.startswith(TRUST_PREFIXES):
        return 'high'
    if any(side is not None and side['mode'] not in REGULAR for side in (change['before'], change['after'])):
        return 'high'
    protected = path.startswith(('tests/', 'knowledge/contracts/'))
    if protected and change['before'] is not None:
        return 'high'
    return 'low' if path.endswith('.md') and not protected else 'medium'


def _highest(levels):
    return max(levels, key=LEVELS.get, default='low')


def inspect_change(repo_root, base_ref, candidate_ref):
    """Inspect exact Git identities and derive a risk floor."""
    try:
        root = Path(repo_root).resolve(strict=True)
    except (OSError, ValueError) as exc:
        _reject('REVIEW_GIT', str(exc))
    if _git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        _reject('REVIEW_HISTORY', 'complete Git history is required')
    base, candidate = _commit(root, base_ref), _commit(root, candidate_ref)
    if base == candidate:
        _reject('REVIEW_HISTORY', 'base must be a strict ancestor')
    _git(root, 'merge-base', '--is-ancestor', base, candidate, code='REVIEW_HISTORY')
    tree = _git(root, 'rev-parse', candidate + '^{tree}').decode('ascii').strip()
    raw = _git(root, 'diff-tree', '-r', '-z', '--raw', '--no-renames', '--no-ext-diff',
               '--no-textconv', '--no-commit-id', base, candidate)
    changes = _changes(raw)
    return {'schema_version': 1, 'base_commit': base, 'candidate_commit': candidate,
            'candidate_tree': tree, 'changes': changes,
            'risk_floor': _highest(_path_risk(change) for change in changes), 'review_ready': False}


def _keys(value, names, code='REVIEW_SCHEMA'):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        _reject(code, 'unexpected or missing fields')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        _reject('REVIEW_SCHEMA', 'a nonempty string is required')
    return value


def _choice(value, choices):
    if not isinstance(value, str) or value not in choices:
        _reject('REVIEW_SCHEMA', 'unknown value')


def _list(value):
    if not isinstance(value, list):
        _reject('REVIEW_SCHEMA', 'a list is required')
    return value


def _unique_values(values):
    if len(values) != len(set(values)):
        _reject('REVIEW_SCHEMA', 'duplicate identifiers or entries')


def _source_specs(value):
    keys = []
    for source in _list(value):
        _keys(source, 'revision path', 'REVIEW_SOURCE')
        if source['revision'] not in ('base', 'candidate'):
            _reject('REVIEW_SOURCE', 'source revision must be base or candidate')
        keys.append((source['revision'], _path(source['path'])))
    _unique_values(keys)
    return keys


def _lens_schema(lenses):
    names = []
    for lens in _list(lenses):
        _keys(lens, 'name assessment rationale')
        _choice(lens['name'], LENSES)
        _choice(lens['assessment'], {'pass', 'blocked'})
        _text(lens['rationale'])
        names.append(lens['name'])
    _unique_values(names)


def _review_schema(reviews):
    for review in _list(reviews):
        _keys(review, 'id reviewer kind fresh_context status lenses read_set')
        _text(review['id']); _text(review['reviewer'])
        _choice(review['kind'], {'human', 'agent'})
        _choice(review['status'], {'completed', 'not_run'})
        if type(review['fresh_context']) is not bool:
            _reject('REVIEW_SCHEMA', 'fresh_context must be a boolean')
        _lens_schema(review['lenses'])
        _source_specs(review['read_set'])
    for key in ('id', 'reviewer'):
        _unique_values([review[key] for review in reviews])


def _finding_schema(findings):
    for finding in _list(findings):
        _keys(finding, 'id severity status scope rationale decided_by evidence')
        _text(finding['id']); _text(finding['rationale'])
        _choice(finding['severity'], {'blocker', 'major', 'nit'})
        _choice(finding['status'], {'open', 'fixed', 'accepted', 'contested'})
        _path(finding['scope'])
        if finding['decided_by'] is not None:
            _text(finding['decided_by'])
        if finding['status'] == 'open' and finding['decided_by'] is not None:
            _reject('REVIEW_SCHEMA', 'an open finding cannot contain a decision')
        _source_specs(finding['evidence'])
    _unique_values([finding['id'] for finding in findings])


def _json_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            _reject('REVIEW_SCHEMA', 'duplicate JSON key')
        data[key] = value
    return data


def _nonfinite(value):
    _reject('REVIEW_SCHEMA', 'non-finite JSON numbers are not supported')


def _document(raw):
    try:
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > 262144:
            _reject('REVIEW_SCHEMA', 'review must be at most 262144 UTF-8 bytes')
        data = json.loads(raw, object_pairs_hook=_json_pairs, parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        _reject('REVIEW_SCHEMA', str(exc))
    _keys(data, 'schema_version base_commit candidate_commit candidate_tree author risk risk_rationale risk_factors reviews findings')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        _reject('REVIEW_SCHEMA', 'schema_version 1 is required')
    _text(data['author']); _text(data['risk_rationale'])
    _choice(data['risk'], LEVELS)
    factors = _list(data['risk_factors'])
    for factor in factors:
        _choice(factor, FACTORS)
    _unique_values(factors)
    _review_schema(data['reviews'])
    _finding_schema(data['findings'])
    return data


def _identity(data, context):
    for key in ('base_commit', 'candidate_commit', 'candidate_tree'):
        if data[key] != context[key]:
            _reject('REVIEW_IDENTITY', 'review does not match ' + key)
    paths = {change['path'] for change in context['changes']}
    if any(finding['scope'] not in paths for finding in data['findings']):
        _reject('REVIEW_SCHEMA', 'finding scope must be a changed path')


def _tree_sources(root, commit, paths):
    if not paths:
        return {}
    raw = _git(root, 'ls-tree', '-z', '--full-tree', commit, '--', *sorted(paths))
    result = {}
    for record in raw.split(b'\0'):
        if not record:
            continue
        try:
            metadata, path = record.split(b'\t', 1)
            mode, kind, oid = metadata.decode('ascii').split()
            path = path.decode('utf-8')
        except (ValueError, UnicodeError):
            _reject('REVIEW_GIT', 'unrecognized tree record')
        if kind != 'blob' or mode not in REGULAR:
            _reject('REVIEW_SOURCE', 'source must be a regular committed blob: ' + path)
        result[path] = {'mode': mode, 'oid': oid}
    if set(result) != paths:
        _reject('REVIEW_SOURCE', 'review contains a missing source')
    return result


def _blob_contents(root, oids):
    if not oids:
        return {}
    ordered = sorted(oids)
    raw = _git(root, 'cat-file', '--batch', data=('\n'.join(ordered) + '\n').encode('ascii'))
    offset, result = 0, {}
    for oid in ordered:
        end = raw.find(b'\n', offset)
        header = raw[offset:end].split() if end >= offset else []
        if len(header) != 3 or header[0] != oid.encode('ascii') or header[1] != b'blob' or not header[2].isdigit():
            _reject('REVIEW_GIT', 'missing or malformed blob header')
        start = end + 1
        offset = start + int(header[2])
        if raw[offset:offset + 1] != b'\n':
            _reject('REVIEW_GIT', 'incomplete blob content')
        result[oid] = raw[start:offset]
        offset += 1
    if offset != len(raw):
        _reject('REVIEW_GIT', 'unexpected trailing blob output')
    return result


def _sources(root, data, context):
    keys = set()
    for review in data['reviews']:
        keys.update(_source_specs(review['read_set']))
    for finding in data['findings']:
        keys.update(_source_specs(finding['evidence']))
    entries = []
    for revision in ('base', 'candidate'):
        paths = {path for rev, path in keys if rev == revision}
        commit = context[revision + '_commit']
        rows = _tree_sources(root, commit, paths)
        entries.extend(dict(revision=revision, path=path, **row) for path, row in sorted(rows.items()))
    contents = _blob_contents(root, {row['oid'] for row in entries})
    for row in entries:
        raw = contents[row['oid']]
        row.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    return entries


def _problem(findings, code, message):
    findings.append({'code': code, 'message': message})


def _independent(review, data):
    if review['reviewer'] == data['author'] or review['status'] != 'completed':
        return False
    return data['risk'] == 'low' or review['kind'] == 'human' or review['fresh_context']


def _check_reviews(data, context, findings):
    required = 2 if data['risk'] == 'high' else 1
    active = [review for review in data['reviews'] if _independent(review, data)]
    if len(active) < required:
        _problem(findings, 'REVIEW_INDEPENDENCE', 'not enough independent completed reviewers')
    if any(review['status'] != 'completed' for review in data['reviews']):
        _problem(findings, 'REVIEW_INCOMPLETE', 'a requested reviewer did not complete')
    lenses = [lens for review in active for lens in review['lenses']]
    if {lens['name'] for lens in lenses} != LENSES:
        _problem(findings, 'LENS_MISSING', 'all three review perspectives are required')
    requested_lenses = (lens for review in data['reviews'] for lens in review['lenses'])
    if any(lens['assessment'] != 'pass' for lens in requested_lenses):
        _problem(findings, 'LENS_BLOCKED', 'a review perspective remains blocked')
    read = {key for review in active for key in _source_specs(review['read_set'])}
    changed = {('candidate' if row['after'] else 'base', row['path']) for row in context['changes']}
    if not changed.issubset(read):
        _problem(findings, 'SOURCE_COVERAGE', 'changed paths are missing from the review read set')
    return required, active


def _check_decisions(data, active, findings):
    reviewers = {review['reviewer']: review for review in active}
    for finding in data['findings']:
        if finding['status'] == 'open':
            if finding['severity'] in {'blocker', 'major'}:
                _problem(findings, 'OPEN_FINDING', 'unresolved finding: ' + finding['id'])
            continue
        decision = reviewers.get(finding['decided_by'])
        valid = decision is not None and bool(finding['evidence'])
        if finding['status'] == 'accepted':
            valid = valid and decision['kind'] == 'human'
        if not valid:
            _problem(findings, 'DECISION_INVALID', 'explicit reviewed decision required: ' + finding['id'])


def verify_review(repo_root, base_ref, candidate_ref, review_json):
    """Verify an externally supplied review without granting approval."""
    data = _document(review_json)
    context = inspect_change(repo_root, base_ref, candidate_ref)
    _identity(data, context)
    floor = _highest([context['risk_floor'], *(FACTORS[factor] for factor in data['risk_factors'])])
    sources = _sources(repo_root, data, context)
    findings = []
    if LEVELS[data['risk']] < LEVELS[floor]:
        _problem(findings, 'RISK_TOO_LOW', 'declared risk is below the change and factor floor')
    required, active = _check_reviews(data, context, findings)
    _check_decisions(data, active, findings)
    return dict(context, risk_floor=floor, risk=data['risk'], required_reviewers=required,
        review_ready=not findings, sources=sources, findings=findings,
        reviewers=data['reviews'], review_findings=data['findings'],
        review_sha256=hashlib.sha256(review_json.encode('utf-8')).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--base-ref', required=True)
    parser.add_argument('--candidate-ref', required=True)
    parser.add_argument('--review')
    args = parser.parse_args(argv)
    try:
        if args.review:
            with open(args.review, encoding='utf-8') as stream:
                result = verify_review(args.repo_root, args.base_ref,
                                       args.candidate_ref, stream.read(262145))
        else:
            result = inspect_change(args.repo_root, args.base_ref, args.candidate_ref)
    except (ReviewError, OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if not args.review or result['review_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
