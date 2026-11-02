"""Verify externally approved learning links from immutable Git objects only.

Git, this reader and the supplied approval reference are trusted. Verified
references do not authenticate a person or establish test execution or meaning.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


_OID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')


class LearningError(ValueError):
    def __init__(self, rule, message):
        super().__init__(message)
        self.rule = rule


def _git(root, *args):
    try:
        result = subprocess.run(['git', '--no-replace-objects', '-C', str(root), *args], capture_output=True,
            timeout=30, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0'))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise LearningError('LEARNING_REF', 'Git could not read the immutable context') from error
    if result.returncode:
        raise LearningError('LEARNING_REF', 'Git object or ancestry is unavailable')
    return result.stdout


def _commit(root, reference):
    if not isinstance(reference, str) or not reference or any(c in reference for c in '\0\r\n'):
        raise LearningError('LEARNING_REF', 'a commit reference is required')
    rows = _git(root, 'rev-parse', '--show-object-format', '--verify',
                '--end-of-options', reference + '^{commit}').decode('ascii').splitlines()
    if len(rows) != 2 or len(rows[1]) != {'sha1': 40, 'sha256': 64}.get(rows[0]):
        raise LearningError('LEARNING_REF', 'unsupported native Git object identity')
    if not _OID.fullmatch(rows[1]):
        raise LearningError('LEARNING_REF', 'invalid commit identity')
    return rows[1]


def _canonical(value, rule):
    if not isinstance(value, str) or not _OID.fullmatch(value):
        raise LearningError(rule, 'a canonical full commit OID is required, never an alias')


def _ancestor(context, source, destination, rule):
    pair = source, destination
    if source == destination or pair in context['ancestry']:
        return
    try:
        _git(context['root'], 'merge-base', '--is-ancestor', source, destination)
    except LearningError as error:
        raise LearningError(rule, 'referenced version is not an available ancestor') from error
    context['ancestry'].add(pair)


def _epoch(root, approved, observed):
    _canonical(approved, 'LEARNING_APPROVAL')
    root = Path(root).resolve(strict=True)
    actual = Path(_git(root, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve()
    if actual != root:
        raise LearningError('LEARNING_PATH', 'repo-root must identify the repository root')
    try:
        if _commit(root, approved) != approved:
            raise LearningError('LEARNING_APPROVAL', 'approval must identify the native commit object')
    except LearningError as error:
        raise LearningError('LEARNING_APPROVAL', str(error)) from error
    observed = approved if observed == approved else _commit(root, observed if observed is not None else 'HEAD')
    context = {'root': root, 'approved': approved, 'observed': observed,
               'commits': {approved, observed}, 'ancestry': set(), 'trees': {}, 'blobs': {}}
    _ancestor(context, approved, observed, 'LEARNING_APPROVAL')
    return context


def _relative(value):
    if (not isinstance(value, str) or not value or value.startswith('/')
            or any(c in value for c in '\\:*?[]') or any(ord(c) < 32 for c in value)
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise LearningError('LEARNING_PATH', 'an exact relative Git artifact path is required')
    return value


def _tree(context, reference):
    if reference not in context['trees']:
        rows = _git(context['root'], 'ls-tree', '-r', '-z', '--full-tree', reference).split(b'\0')
        entries = {}
        for row in filter(None, rows):
            header, separator, path = row.partition(b'\t')
            fields = header.split()
            if not separator or len(fields) != 3:
                raise LearningError('LEARNING_REF', 'invalid Git tree entry')
            entries[path] = tuple(fields)
        context['trees'][reference] = entries
    return context['trees'][reference]


def _digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


def _blob(context, reference, path):
    path = _relative(path)
    entry = _tree(context, reference).get(path.encode('utf-8'))
    if entry is None:
        raise LearningError('LEARNING_REF', 'referenced artifact is absent from Git: ' + path)
    mode, kind, oid = entry
    if mode not in (b'100644', b'100755') or kind != b'blob':
        raise LearningError('LEARNING_PATH', 'referenced artifact is not a regular Git blob: ' + path)
    name = oid.decode('ascii')
    if not _OID.fullmatch(name):
        raise LearningError('LEARNING_REF', 'invalid Git blob identity')
    if name not in context['blobs']:
        raw = _git(context['root'], 'cat-file', 'blob', name)
        context['blobs'][name] = {'raw': raw, 'sha256': _digest(raw), 'blob_oid': name}
    return context['blobs'][name]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LearningError('LEARNING_POLICY', 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _entry_schema(entry):
    allowed = {'id', 'status', 'finding', 'decision', 'tests'}
    if not isinstance(entry, dict) or not {'id', 'status'}.issubset(entry) or set(entry) - allowed:
        raise LearningError('LEARNING_POLICY', 'invalid learning entry fields')
    identifier = entry['id']
    if not isinstance(identifier, str) or not identifier.strip() or '\0' in identifier:
        raise LearningError('LEARNING_POLICY', 'a nonempty learning identity is required')
    if entry['status'] not in ('accepted', 'draft', 'legacy'):
        raise LearningError('LEARNING_POLICY', 'unsupported learning status')


def _ledger(context, reference, path):
    try:
        text = _blob(context, reference, path)['raw'].decode('utf-8')
        data = json.loads(text, object_pairs_hook=_unique)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LearningError('LEARNING_POLICY', 'learning ledger must be valid UTF-8 JSON') from error
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'entries'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['entries'], list)):
        raise LearningError('LEARNING_POLICY', 'expected schema_version 1 and entries list')
    entries = {}
    for entry in data['entries']:
        _entry_schema(entry)
        if entry['id'] in entries:
            raise LearningError('LEARNING_POLICY', 'duplicate learning identity')
        entries[entry['id']] = entry
    return entries


def _reference_commit(context, value):
    _canonical(value, 'LEARNING_REF')
    if value not in context['commits']:
        if _commit(context['root'], value) != value:
            raise LearningError('LEARNING_REF', 'reference must identify the native commit object')
        context['commits'].add(value)
    _ancestor(context, value, context['approved'], 'LEARNING_REF')
    _ancestor(context, value, context['observed'], 'LEARNING_REF')
    return value


def _current_blob(context, path):
    try:
        return _blob(context, context['observed'], path)
    except LearningError as error:
        if error.rule == 'LEARNING_REF':
            raise LearningError('LEARNING_STALE', 'linked artifact is absent from the observed commit') from error
        raise


def _link(context, reference):
    if not isinstance(reference, dict) or set(reference) != {'path', 'ref', 'sha256'}:
        raise LearningError('LEARNING_REF', 'a versioned artifact reference is required')
    path = _relative(reference['path'])
    version = _reference_commit(context, reference['ref'])
    digest = reference['sha256']
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise LearningError('LEARNING_HASH', 'a canonical SHA256 LF digest is required')
    source = _blob(context, version, path)
    if source['sha256'] != digest:
        raise LearningError('LEARNING_HASH', 'referenced artifact digest differs: ' + path)
    current = _current_blob(context, path)
    if current['sha256'] != digest:
        raise LearningError('LEARNING_STALE', 'observed artifact differs from its approved version: ' + path)
    return {'path': path, 'ref': version, 'sha256': digest, 'hash_method': 'sha256-lf',
            'blob_oid': source['blob_oid'], 'observed_blob_oid': current['blob_oid'],
            'observed_ref': context['observed'], 'reference_verified': True}


def _accepted_fields(entry):
    for key, rule in (('finding', 'LEARNING_FINDING'), ('decision', 'LEARNING_DECISION')):
        if not entry.get(key):
            raise LearningError(rule, 'accepted entry requires a versioned ' + key)
    if not isinstance(entry.get('tests'), list) or not entry['tests']:
        raise LearningError('LEARNING_TESTS', 'accepted entry requires versioned tests')


def _approved_inventory(observed, approved):
    for identifier, entry in approved.items():
        if entry['status'] == 'accepted' and observed.get(identifier) != entry:
            raise LearningError('LEARNING_APPROVAL', 'candidate changed or omitted an approved accepted entry')


def _entry(context, entry, approved):
    if entry['status'] != 'accepted':
        return {'id': entry['id'], 'status': 'LEGACY_UNVERIFIED' if entry['status'] == 'legacy'
                else 'PENDING', 'approval_verified': False}
    _accepted_fields(entry)
    if approved.get(entry['id']) != entry:
        raise LearningError('LEARNING_APPROVAL', 'accepted entry is not identical in the approved ledger')
    finding, decision = _link(context, entry['finding']), _link(context, entry['decision'])
    tests = [dict(_link(context, link), execution_observed=False) for link in entry['tests']]
    return {'id': entry['id'], 'status': 'accepted', 'approval_verified': True,
            'finding': finding, 'decision': decision, 'tests': tests}


def _report():
    return {'schema_version': 1, 'status': 'PENDING', 'complete': False,
            'approved_ref': None, 'observed_ref': None, 'accepted_count': 0,
            'entries': [], 'findings': [], 'method': 'git-blobs',
            'human_identity_authenticated': False, 'product_execution_observed': False}


def _failure(report, error):
    report.update(status='FAIL', complete=False)
    report['accepted_count'] = sum(row['approval_verified'] for row in report['entries'])
    report['findings'].append({'rule': error.rule, 'message': str(error)})
    return report


def _coverage(report, required):
    report['accepted_count'] = sum(row['approval_verified'] for row in report['entries'])
    complete = bool(report['accepted_count']) and all(row['approval_verified'] for row in report['entries'])
    report.update(complete=complete, status='PASS' if complete else 'PENDING')
    if required and not complete:
        raise LearningError('LEARNING_COVERAGE', 'complete accepted coverage is required, without pending entries')


def validate(root, ledger_path, approved_ref, observed_ref=None, require_accepted=False):
    report = _report()
    try:
        context = _epoch(root, approved_ref, observed_ref)
        report.update(approved_ref=context['approved'], observed_ref=context['observed'])
        path = _relative(ledger_path)
        observed = _ledger(context, context['observed'], path)
        approved = _ledger(context, context['approved'], path)
        _approved_inventory(observed, approved)
        for entry in observed.values():
            report['entries'].append(_entry(context, entry, approved))
        _coverage(report, require_accepted)
    except LearningError as error:
        _failure(report, error)
    except (OSError, ValueError, TypeError, KeyError) as error:
        _failure(report, LearningError('LEARNING_POLICY', str(error)))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--ledger', default='knowledge/learning.json')
    parser.add_argument('--approved-ref')
    parser.add_argument('--observed-ref', default='HEAD')
    parser.add_argument('--require-accepted', action='store_true')
    parser.add_argument('--require-execution', action='store_true')
    args = parser.parse_args(argv)
    report = validate(args.repo_root, args.ledger, args.approved_ref,
                      args.observed_ref, args.require_accepted)
    if args.require_execution:
        _failure(report, LearningError('LEARNING_UNSUPPORTED',
                 'this profile verifies links; it has no test execution provenance mechanism'))
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
