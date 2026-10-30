"""Execute approved obligation oracles and emit a fail-closed acceptance matrix.

The reviewer owns semantic coverage and inventory completeness. This runner
proves execution/integrity, not the truth of arbitrarily named assertions.
"""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from oracle_execution import declared_timeout, execute_oracle
from oracle_inventory import approved_binary_paths, inventory_paths, local_file
from validate_contracts import parse_frontmatter, validate_file
from validation_runtime import prepare_runtime
from verify_quality import git, integrity, safe_path, strings, unique_object


REQUIRED = ('signature', 'dependencies', 'budget', 'forbids', 'invariants')
INTERNAL = ('oracle-integrity', 'oracle-execution', 'perimeter')


def _hash(content):
    return hashlib.sha256(content).hexdigest()


def _json_hash(data):
    return _hash(json.dumps(data, sort_keys=True, separators=(',', ':')).encode())


def _policy(root, data):
    fields = {'schema_version', 'contracts', 'implementation', 'pm'}
    if (not isinstance(data, dict) or set(data) != fields
            or type(data['schema_version']) is not int or data['schema_version'] != 1):
        raise ValueError('Invalid acceptance policy schema')
    for key in ('implementation', 'pm'):
        names = strings(data[key], key)
        if len(set(names)) != len(names):
            raise ValueError('Duplicate policy path: ' + key)
        for name in names:
            safe_path(root, name)
    if set(data['implementation']) & set(data['pm']):
        raise ValueError('Implementation and PM paths must be disjoint')
    _policy_contracts(root, data['contracts'])
    return data


def _policy_contracts(root, contracts):
    if not isinstance(contracts, list) or not contracts:
        raise ValueError('Policy requires contracts')
    seen = set()
    for item in contracts:
        if not isinstance(item, dict) or set(item) != {'path', 'checks'}:
            raise ValueError('Invalid acceptance contract schema')
        safe_path(root, item['path'])
        if item['path'] in seen:
            raise ValueError('Duplicate acceptance contract')
        seen.add(item['path'])
        if not isinstance(item['checks'], list):
            raise ValueError('Expected obligation checks list')


def _obligations(data, item):
    additional = strings(data.get('acceptance_obligations', []), 'acceptance_obligations')
    required = set(REQUIRED) | set(additional)
    if set(additional) & set(INTERNAL):
        raise ValueError('Internal obligations cannot be overridden')
    checks = {}
    for check in item['checks']:
        fields = {'obligation', 'tests', 'test_runner', 'test_command', 'timeout'}
        if not isinstance(check, dict) or set(check) != fields:
            raise ValueError('Invalid obligation check schema')
        name = check['obligation']
        if name not in required or name in checks:
            raise ValueError('Duplicate or undeclared obligation: ' + str(name))
        if type(check['timeout']) is not int or not 0 < check['timeout'] <= 3600:
            raise ValueError('Invalid obligation timeout')
        if check['tests'] not in inventory_paths(data, required=True):
            raise ValueError('Obligation oracle must be in protected inventory')
        checks[name] = check
    return checks


def _load(root, policy_path, reference):
    if not isinstance(reference, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', reference):
        raise ValueError('An explicitly approved full commit SHA is required')
    actual = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if actual != root:
        raise ValueError('repo-root must be the Git root')
    safe_path(root, policy_path)
    commit = git(root, 'rev-parse', '--verify', '--end-of-options', reference + '^{commit}').decode().strip()
    raw = git(root, 'show', commit + ':' + policy_path)
    policy = _policy(root, json.loads(raw, object_pairs_hook=unique_object))
    protected = {policy_path: raw}
    contracts = []
    for item in policy['contracts']:
        text = git(root, 'show', commit + ':' + item['path'])
        data, _ = parse_frontmatter(text.decode('utf-8'))
        files = inventory_paths(data, required=True)
        if data.get('test_runner') not in ('python-unittest', 'node-test'):
            raise ValueError('Acceptance requires a managed contract runner')
        if not isinstance(data.get('forbids'), list):
            raise ValueError('Acceptance requires explicit forbids, including an empty list if none')
        safe_path(root, data['target'])
        protected[item['path']] = text
        for name in files:
            mode = git(root, 'ls-tree', commit, '--', name).decode().split()
            if not mode or mode[0] not in ('100644', '100755'):
                raise ValueError('Inventory file missing or not regular at approved SHA: ' + name)
            protected[name] = git(root, 'show', commit + ':' + name)
        contracts.append((item, data, _obligations(data, item)))
    if set(protected) & (set(policy['implementation']) | set(policy['pm'])):
        raise ValueError('Protected files cannot be implementation or PM paths')
    for name in policy['implementation']:
        if not any(fnmatch.fnmatchcase(name, pattern) for _, data, _ in contracts
                   for pattern in data['touch_only']):
            raise ValueError('Implementation path outside contract perimeter: ' + name)
    return commit, policy, contracts, protected


def _snapshot(root, policy, contracts):
    names = set(policy['implementation']) | {data['target'] for _, data, _ in contracts}
    return {name: _hash(local_file(root, name).read_bytes()) for name in sorted(names)}


def _intact(root, context):
    commit, policy_path, policy, protected, contracts, snapshot = context
    inventory_policy = {'protected': list(protected),
                        'implementation': policy['implementation'], 'pm': policy['pm']}
    names = {name for _, data, _ in contracts for name in inventory_paths(data, required=True)}
    exact = approved_binary_paths(lambda *args: git(root, *args), commit, sorted(names))
    integrity(root, commit, policy_path, inventory_policy, protected, exact_paths=exact)
    if _snapshot(root, policy, contracts) != snapshot:
        raise ValueError('Implementation changed during verification')


def _matrix(item, data, protected, snapshot):
    required = list(INTERNAL) + sorted(set(REQUIRED) | set(data.get('acceptance_obligations', [])))
    return {'path': item['path'], 'contract_sha256': _hash(protected[item['path']]),
            'target_sha256': snapshot[data['target']],
            'oracle_hashes': {name: _hash(protected[name]) for name in inventory_paths(data, True)},
            'obligations': [{'obligation': name, 'status': 'NOT_RUN', 'evidence': []} for name in required]}


def _run(row, metadata, root, timeout, recheck):
    row['status'] = 'FAIL'
    for iteration in (1, 2):
        outcome = execute_oracle(metadata, root, timeout)
        row['evidence'].append({'iteration': iteration, 'command': metadata['test_command'],
                                'runner': metadata['test_runner'], 'exit_code': outcome['exit_code'],
                                'executed_tests': outcome['executed_tests'], 'error': outcome['error'],
                                'stdout': outcome['stdout'], 'stderr': outcome['stderr'],
                                'runner_evidence': outcome.get('evidence'),
                                'instrumented_argv': outcome.get('instrumented_argv'),
                                'runtime_version': outcome.get('runtime_version'),
                                'output_sha256': _hash((outcome['stdout'] + outcome['stderr']).encode())})
        recheck()
        if not outcome['ok']:
            row['status'] = 'FAIL'
            return False
    row['status'] = 'PASS'
    return True


def verify_acceptance(repo_root, policy_path, approved_ref):
    """Verify an approved policy; failure always returns an unapproved matrix."""
    result = {'schema_version': 1, 'ok': False, 'state': 'structure_invalid', 'contracts': []}
    try:
        root = Path(repo_root).resolve(strict=True)
        commit, policy, contracts, protected = _load(root, policy_path, approved_ref)
        snapshot = _snapshot(root, policy, contracts)
        result.update(approved_ref=commit, policy_sha256=_hash(protected[policy_path]),
                      implementation_hashes=snapshot, snapshot_sha256=_json_hash(snapshot))
        result['contracts'] = [_matrix(item, data, protected, snapshot) for item, data, _ in contracts]
        context = (commit, policy_path, policy, protected, contracts, snapshot)
        recheck = lambda: _intact(root, context)
        recheck()
        for item, _, _ in contracts:
            errors = [str(f) for f in validate_file(root / item['path'], root) if f.level == 'ERROR']
            if errors:
                raise ValueError('; '.join(errors))
        result['state'] = 'structure_valid'
        for matrix, (_, data, checks) in zip(result['contracts'], contracts):
            rows = {row['obligation']: row for row in matrix['obligations']}
            for name in ('oracle-integrity', 'perimeter'):
                rows[name].update(status='PASS', evidence=[{'instrument': 'approved Git/index/worktree comparison',
                                                          'snapshot_sha256': result['snapshot_sha256']}])
            missing = set(rows) - set(INTERNAL) - set(checks)
            if missing:
                for name in sorted(missing):
                    rows[name].update(status='FAIL', evidence=[{'instrument': None,
                                                               'error': 'Required obligation has no approved check'}])
                result['error'] = 'Missing required obligations: ' + ', '.join(sorted(missing))
                return result
            if not _run(rows['oracle-execution'], data, root, declared_timeout(data), recheck):
                return result
        result['state'] = 'tests_approved'
        for matrix, (_, data, checks) in zip(result['contracts'], contracts):
            rows = {row['obligation']: row for row in matrix['obligations']}
            for name in sorted(checks):
                check = checks[name]
                metadata = dict(check, oracle_files=inventory_paths(data, required=True))
                if not _run(rows[name], metadata, root, check['timeout'], recheck):
                    return result
        recheck()
        result.update(ok=True, state='acceptance_approved')
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
    return result


def main(argv=None):
    prepare_runtime()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--policy', required=True)
    parser.add_argument('--approved-ref', required=True)
    parser.add_argument('--json-output')
    args = parser.parse_args(argv)
    result = verify_acceptance(args.repo_root, args.policy, args.approved_ref)
    text = json.dumps(result, indent=2)
    if args.json_output:
        Path(args.json_output).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
