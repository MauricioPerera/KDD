"""Select externally reviewed references for an exact Git tree, without writes."""
import argparse
import json
import os
import re
import subprocess
import sys


class ApprovalError(ValueError):
    """An external approval cannot be selected safely."""


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
        raise ApprovalError('APPROVAL_SHA: a full hexadecimal SHA is required')
    return value.lower()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ApprovalError('APPROVAL_JSON: duplicate key: ' + key)
        result[key] = value
    return result


def _schema(data):
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'trees'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['trees'], dict) or not data['trees']):
        raise ApprovalError('APPROVAL_SCHEMA: expected schema_version 1 and nonempty trees')


def _records(raw):
    try:
        data = json.loads(raw, object_pairs_hook=_unique)
    except ApprovalError:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise ApprovalError('APPROVAL_JSON: invalid registry JSON') from exc
    _schema(data)
    result = {}
    for key, row in data['trees'].items():
        tree = _sha(key)
        if tree in result:
            raise ApprovalError('APPROVAL_SCHEMA: tree keys collide after normalization')
        if (not isinstance(row, dict) or 'baseline_ref' not in row
                or set(row) - {'baseline_ref', 'quality_ref'}):
            raise ApprovalError('APPROVAL_SCHEMA: invalid approval entry')
        result[tree] = {'baseline_ref': _sha(row['baseline_ref']),
                        'quality_ref': _sha(row['quality_ref']) if 'quality_ref' in row else None}
    return result


def _git(root, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args],
            stderr=subprocess.PIPE, timeout=30).decode('ascii').strip()
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise ApprovalError('APPROVAL_REF: Git could not resolve an approval context') from exc


def _commit(root, ref):
    if not isinstance(ref, str) or not ref:
        raise ApprovalError('APPROVAL_REF: a candidate or approved commit is required')
    value = _git(root, 'rev-parse', '--verify', '--end-of-options', ref)
    if _git(root, 'cat-file', '-t', value) != 'commit':
        raise ApprovalError('APPROVAL_REF: the reference must identify a commit')
    return _sha(value)


def _approved_commit(root, ref):
    commit = _commit(root, ref)
    if commit != ref:
        raise ApprovalError('APPROVAL_REF: an approval must be the canonical commit OID, not an alias')
    return commit


def _registry_text(registry_json):
    raw = '' if registry_json is None else registry_json
    if not isinstance(raw, str):
        raise ApprovalError('APPROVAL_JSON: registry must be JSON text')
    try:
        size = len(raw.encode('utf-8'))
    except UnicodeError as exc:
        raise ApprovalError('APPROVAL_JSON: registry must be valid UTF-8') from exc
    if size > 48000:
        raise ApprovalError('APPROVAL_LIMIT: registry exceeds 48000 UTF-8 bytes')
    return raw


def _inputs(registry_json, explicit_baseline, explicit_quality):
    raw = _registry_text(registry_json)
    if raw and (explicit_baseline or explicit_quality):
        raise ApprovalError('APPROVAL_AMBIGUOUS: registry and explicit modes cannot be mixed')
    records = _records(raw) if raw else None
    if records is None and not explicit_baseline:
        raise ApprovalError('APPROVAL_REQUIRED: an external approval is required')
    explicit = None if records is not None else {
        'baseline_ref': _sha(explicit_baseline),
        'quality_ref': _sha(explicit_quality) if explicit_quality else None}
    return records, explicit


def resolve(repo_root, candidate_ref, registry_json, *, explicit_baseline=None,
            explicit_quality=None, require_quality=False):
    """Return the selected refs; only the selected row needs local Git objects."""
    records, explicit = _inputs(registry_json, explicit_baseline, explicit_quality)
    candidate = _commit(repo_root, candidate_ref)
    tree = _sha(_git(repo_root, 'rev-parse', candidate + '^{tree}'))
    if records is not None and tree not in records:
        raise ApprovalError('APPROVAL_UNKNOWN_TREE: no reviewed entry for ' + tree)
    row = records[tree] if records is not None else explicit
    if require_quality and not row['quality_ref']:
        raise ApprovalError('APPROVAL_QUALITY: this context requires an approved quality reference')
    baseline = _approved_commit(repo_root, row['baseline_ref'])
    quality = _approved_commit(repo_root, row['quality_ref']) if row['quality_ref'] else None
    return {'candidate_commit': candidate, 'candidate_tree': tree,
            'baseline_ref': baseline, 'quality_ref': quality,
            'source': 'registry' if records is not None else 'explicit'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--candidate-ref', default='HEAD')
    parser.add_argument('--explicit-baseline')
    parser.add_argument('--explicit-quality')
    parser.add_argument('--require-quality', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = resolve(args.repo_root, args.candidate_ref,
                         os.environ.get('KDD_APPROVAL_REGISTRY', ''),
                         explicit_baseline=args.explicit_baseline,
                         explicit_quality=args.explicit_quality,
                         require_quality=args.require_quality)
    except ApprovalError as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
