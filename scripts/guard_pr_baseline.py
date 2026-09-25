#!/usr/bin/env python3
"""Check a proposed merge using trusted code from the base branch only.

The candidate commit is read through Git object commands, never checked out or
executed. This script is intended for a ``pull_request_target`` workflow.
"""

import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys

from validate_contracts import parse_frontmatter


PROTECTED_FILES = {
    'completion-legacy.json',
    'scripts/guard_pr_baseline.py',
    'scripts/validate_completion.py',
    'scripts/validate_baseline.py',
    'scripts/validate_contracts.py',
    'scripts/validate_test_commands.py',
}
PROTECTED_PREFIXES = ('.github/workflows/',)
CONTRACTS_DIR = 'knowledge/contracts/'


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


def check(base_ref, candidate_ref, approved_ref):
    """Return findings for protected code and approved contract/oracle drift."""
    base, candidate, approved = map(_commit, (base_ref, candidate_ref, approved_ref))
    changed = _git('diff', '--name-only', '-z', base, candidate).decode('utf-8')
    findings = []
    for path in sorted(filter(None, changed.split('\0'))):
        if path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES):
            findings.append(path + ': trusted gate file changed in PR')

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
    parser.add_argument('--approved-ref', required=True)
    args = parser.parse_args(argv)
    if args.pr_number <= 0:
        parser.error('--pr-number must be positive')
    if not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', args.approved_ref):
        parser.error('--approved-ref must be a full commit SHA')
    try:
        base = _commit(args.base_ref)
        _git('fetch', '--no-tags', 'origin',
             'refs/pull/{}/merge'.format(args.pr_number))
        candidate = _commit('FETCH_HEAD')
        try:
            _commit(args.approved_ref)
        except ValueError:
            _git('fetch', '--no-tags', 'origin', args.approved_ref)
        findings = check(base, candidate, args.approved_ref)
    except (ValueError, UnicodeError) as exc:
        print('FAIL: ' + str(exc))
        return 2
    for finding in findings:
        print('FAIL: ' + finding)
    if not findings:
        print('PASS: trusted PR baseline and gate files')
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
