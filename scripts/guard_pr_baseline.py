#!/usr/bin/env python3
"""Check a proposed merge using trusted code from the base branch only.

The candidate commit is read through Git object commands, never checked out or
executed. This script is intended for a ``pull_request_target`` workflow.
"""

import argparse
import json
import os
from pathlib import PurePosixPath
import re
import subprocess
import sys

from validate_contracts import parse_frontmatter


PROTECTED_FILES = {
    'scripts/approval_registry.py',
    'scripts/check_mcp_sdk.py',
    'tools/mcp-sdk/pins.json',
    'tools/mcp-sdk/ubuntu.txt',
    'tools/mcp-sdk/windows.txt',
    'completion-legacy.json',
    'requirements-change-audit.txt',
    'scripts/optional_evidence.py',
    'scripts/guard_pr_baseline.py',
    'scripts/validate_completion.py',
    'scripts/verify_completion_runs.py',
    'scripts/validate_change_contract.py',
    'scripts/change_contract_multilang.py',
    'scripts/validate_baseline.py',
    'scripts/validate_contracts.py',
    'scripts/validate_test_commands.py',
    'scripts/run_test_suite.py',
    'scripts/trusted_ci.py',
    'scripts/process_tree.py',
    'scripts/execution_profile.py',
    'scripts/validate_workflows.py',
    'tools/workflow-syntax/actionlint.json',
}
PROTECTED_PREFIXES = ('.github/workflows/',)
CONTRACTS_DIR = 'knowledge/contracts/'
IMPORT_NAMES = set(sys.stdlib_module_names) | {
    'trusted_ci', 'run_test_suite', 'validate_test_commands', 'validate_contracts',
    'process_tree', 'execution_profile', 'approval_registry', 'check_mcp_sdk',
}


def _shadows_runtime(path):
    parts = PurePosixPath(path).parts
    if parts and parts[0] == 'scripts':
        parts = parts[1:]
    return bool(parts) and parts[0].split('.')[0] in IMPORT_NAMES


def _git(*args):
    try:
        return subprocess.check_output(['git', *args], stderr=subprocess.PIPE,
                                       timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('Git operation failed: {}'.format(' '.join(args))) from exc


def _commit(ref):
    commit = _git('rev-parse', '--verify', '--end-of-options',
                  ref).decode('ascii').strip()
    if _git('cat-file', '-t', commit).decode('ascii').strip() != 'commit':
        raise ValueError('Reference is not a commit: ' + ref)
    return commit


def _blob(ref, path):
    try:
        return _git('show', ref + ':' + path)
    except ValueError:
        return None


def _paths(ref):
    return set(_git('ls-tree', '-r', '--name-only', '-z', ref, '--',
                    'knowledge/contracts').decode('utf-8').strip('\0').split('\0')) - {''}


def _contracts(ref):
    return {path for path in _paths(ref)
            if path.startswith(CONTRACTS_DIR)
            and '/' not in path[len(CONTRACTS_DIR):]
            and path.endswith('.md')
            and not PurePosixPath(path).name.startswith('TEMPLATE-')}


def _normalize(content):
    return content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _unique_review(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate review key: ' + key)
        result[key] = value
    return result


def _review_object(ref, path):
    raw = _git('ls-tree', '-z', ref, '--', ':(literal)' + path)
    if not raw:
        return None
    records = raw.split(b'\0')
    if len(records) != 2 or records[-1]:
        raise ValueError('ambiguous reviewed path')
    metadata, name = records[0].split(b'\t', 1)
    mode, kind, oid = metadata.decode('ascii').split(' ')
    if (name.decode('utf-8') != path or kind != 'blob'
            or mode not in ('100644', '100755')):
        raise ValueError('reviewed path is not a regular file')
    return {'mode': mode, 'oid': oid}


def _review_header(raw, base, candidate):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > 48000:
        raise ValueError('invalid review data')
    try:
        review = json.loads(raw, object_pairs_hook=_unique_review)
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid review JSON') from exc
    if (not isinstance(review, dict) or set(review) !=
            {'schema_version', 'base_commit', 'candidate_tree', 'files'}
            or type(review['schema_version']) is not int or review['schema_version'] != 1):
        raise ValueError('invalid review schema')
    tree = _git('rev-parse', candidate + '^{tree}').decode('ascii').strip()
    if review['base_commit'] != base or review['candidate_tree'] != tree:
        raise ValueError('review does not identify the exact base and tree')
    return review['files']


def _reviewed_protected(raw, base, candidate, protected):
    entries = _review_header(raw, base, candidate)
    if not isinstance(entries, list) or not entries:
        raise ValueError('review must contain protected paths')
    reviewed = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'before', 'after'}:
            raise ValueError('invalid reviewed file')
        path = entry['path']
        if not isinstance(path, str) or path not in protected or path in reviewed:
            raise ValueError('unknown or duplicate reviewed path')
        if (entry['before'] != _review_object(base, path)
                or entry['after'] != _review_object(candidate, path)):
            raise ValueError('reviewed file mode or object differs')
        reviewed.add(path)
    if reviewed != protected:
        raise ValueError('review does not cover every protected change')
    return reviewed


def _protected_findings(paths, base, candidate, reviewed_changes):
    protected = {path for path in paths
                 if path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)}
    reviewed, findings = set(), []
    if reviewed_changes and protected:
        try:
            reviewed = _reviewed_protected(reviewed_changes, base, candidate, protected)
        except (ValueError, UnicodeError) as exc:
            findings.append('TRUSTED_REVIEW: ' + str(exc))
    for path in sorted(paths):
        if path in protected and path not in reviewed:
            findings.append(path + ': trusted gate file changed in PR')
        elif path not in protected and _shadows_runtime(path):
            findings.append(path + ': trusted import name changed in PR')
    return findings


def check(base_ref, candidate_ref, approved_ref, *, reviewed_changes=None):
    """Return findings for protected code and approved contract/oracle drift."""
    base, candidate, approved = map(_commit, (base_ref, candidate_ref, approved_ref))
    changed = _git('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z',
                   base, candidate).decode('utf-8')
    paths = set(filter(None, changed.split('\0')))
    findings = _protected_findings(paths, base, candidate, reviewed_changes)

    expected_contracts = _contracts(approved)
    candidate_contracts = _contracts(candidate)
    for path in sorted(expected_contracts ^ candidate_contracts):
        findings.append(path + ': contract added or removed from approved baseline')
    for path in sorted(expected_contracts & candidate_contracts):
        expected = _blob(approved, path)
        actual = _blob(candidate, path)
        if _normalize(actual) != _normalize(expected):
            findings.append(path + ': contract differs from approved baseline')
        metadata, _ = parse_frontmatter(expected.decode('utf-8'))
        oracle = metadata.get('tests') if isinstance(metadata, dict) else None
        if not isinstance(oracle, str) or not oracle:
            raise ValueError(path + ': approved contract has no tests path')
        oracle_path = PurePosixPath(oracle)
        if oracle_path.is_absolute() or '..' in oracle_path.parts:
            raise ValueError(path + ': approved tests path escapes repository')
        oracle = oracle_path.as_posix()
        expected_oracle = _blob(approved, oracle)
        if expected_oracle is None:
            raise ValueError(path + ': approved oracle missing')
        candidate_oracle = _blob(candidate, oracle)
        if candidate_oracle is None or _normalize(candidate_oracle) != _normalize(expected_oracle):
            findings.append(oracle + ': oracle differs from approved baseline')
    if not expected_contracts:
        raise ValueError('Approved baseline contains no contracts')
    return sorted(set(findings))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pr-number', required=True, type=int)
    parser.add_argument('--base-ref', required=True)
    approvals = parser.add_mutually_exclusive_group(required=True)
    approvals.add_argument('--approved-ref')
    approvals.add_argument('--approval-registry')
    args = parser.parse_args(argv)
    if args.pr_number <= 0:
        parser.error('--pr-number must be positive')
    if args.approved_ref is not None and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', args.approved_ref):
        parser.error('--approved-ref must be a full commit SHA')
    try:
        base = _commit(args.base_ref)
        _git('fetch', '--no-tags', 'origin',
             'refs/pull/{}/merge'.format(args.pr_number))
        candidate = _commit('FETCH_HEAD')
        if args.approval_registry is not None:
            from approval_registry import resolve
            approved = resolve('.', candidate, args.approval_registry)['baseline_ref']
        else:
            approved = args.approved_ref
            try:
                _commit(approved)
            except ValueError:
                _git('fetch', '--no-tags', 'origin', approved)
        findings = check(base, candidate, approved,
                         reviewed_changes=os.environ.get('KDD_TRUSTED_CHANGE_REVIEW'))
    except (ValueError, UnicodeError, ImportError) as exc:
        print('FAIL: ' + str(exc))
        return 2
    for finding in findings:
        print('FAIL: ' + finding)
    if not findings:
        print('PASS: trusted PR baseline and gate files')
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
