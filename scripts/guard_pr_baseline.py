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
from oracle_inventory import approved_binary_paths, inventory_paths, oracle_equal


PROTECTED_FILES = {
    'scripts/board_oracle_bridge.py',
    'acceptance.json',
    'scripts/oracle_inventory.py',
    'scripts/oracle_execution.py',
    'scripts/unittest_oracle_runner.py',
    'scripts/node_oracle_reporter.mjs',
    'scripts/verify_acceptance.py',
    'scripts/verify_quality.py',
    'scripts/validation_runtime.py',
    'scripts/run_profile.py',
    'scripts/validate_documentation_examples.py',
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


def _binary_inventory(metadata, approved):
    if 'oracle_files' not in metadata:
        return set()
    return approved_binary_paths(_git, approved, inventory_paths(metadata))


def check(base_ref, candidate_ref, approved_ref):
    """Return findings for protected code and approved contract/oracle drift."""
    base, candidate, approved = map(_commit, (base_ref, candidate_ref, approved_ref))
    changed = _git('diff', '--name-only', '-z', base, candidate).decode('utf-8')
    findings = []
    for path in sorted(filter(None, changed.split('\0'))):
        if path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES):
            findings.append(path + ': trusted gate file changed in PR')
        elif _shadows_runtime(path):
            findings.append(path + ': trusted import name changed in PR')

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
        binary = _binary_inventory(metadata, approved)
        for oracle in inventory_paths(metadata):
            expected_oracle = _blob(approved, oracle)
            mode = _git('ls-tree', approved, '--', oracle).decode().split()
            if expected_oracle is None or not mode or mode[0] not in ('100644', '100755'):
                raise ValueError(path + ': approved oracle missing or not regular: ' + oracle)
            candidate_oracle = _blob(candidate, oracle)
            candidate_mode = _git('ls-tree', candidate, '--', oracle).decode().split()
            regular = bool(candidate_mode and candidate_mode[0] in ('100644', '100755'))
            changed = (not oracle_equal(candidate_oracle or b'', expected_oracle, oracle in binary) if 'oracle_files' in metadata else
                       _normalize(candidate_oracle or b'') != _normalize(expected_oracle))
            if not regular or candidate_oracle is None or changed:
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
        findings = check(base, candidate, approved)
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
