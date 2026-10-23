"""Validate committed Task snapshots and every mainline transition read-only."""
import argparse
import json
from pathlib import Path
import sys

import task_evidence as proof
import task_git as journal
from task_model import TaskError, task_path, valid_sha, validate_transition
from validate_contracts import parse_frontmatter


def _dependencies(tasks):
    errors = []
    visited = set()
    def visit(identifier, active):
        if identifier not in tasks:
            errors.append('TASK_DEPENDENCIES: missing ' + identifier)
            return
        if identifier in active:
            errors.append('TASK_DEPENDENCIES: dependency cycle at ' + identifier)
            return
        if identifier not in visited:
            for dependency in tasks[identifier]['depends_on']:
                visit(dependency, active | {identifier})
            visited.add(identifier)
    for identifier in tasks:
        visit(identifier, set())
    return errors


def _proof_output(report, metadata):
    _, runner = proof.invocation(metadata)
    valid = (report.get('runner') == runner and type(report.get('exit_code')) is int
             and report['exit_code'] == 0 and type(report.get('passed_tests')) is int)
    if not valid or not all(isinstance(report.get(k), str) for k in ('stdout', 'stderr')):
        return ['TASK_EVIDENCE: invalid runner result']
    expected = proof.passed_tests(runner, report['stdout'], report['stderr'])
    if expected < 1 or report['passed_tests'] != expected:
        return ['TASK_EVIDENCE: missing recognized passing tests']
    if report.get('output_sha256') != proof.digest(report['stdout'] + report['stderr']):
        return ['TASK_EVIDENCE: output digest mismatch']
    return []


def _proof_refs(root, task, report):
    tip = report.get('branch_tip')
    if not valid_sha(tip) or tip == task['branch_base']:
        return ['TASK_EVIDENCE: missing implementation tip']
    pairs = [(task['branch_base'], tip), (tip, task['verified_ref'])]
    if not all(journal.ancestor(root, a, b) for a, b in pairs):
        return ['TASK_EVIDENCE: implementation is not integrated']
    return []


def _proof_fields(root, task, report, metadata):
    expected = {'schema_version': 1, 'task_id': task['task_id'],
                'tested_commit': task['verified_ref'], 'approved_ref': task['approved_ref'],
                'command': metadata['test_command']}
    for field, path in [('contract_sha256', task['contract']),
                        ('target_sha256', metadata['target']), ('oracle_sha256', metadata['tests'])]:
        expected[field] = proof.digest(proof.normalized(journal.blob(root, task['verified_ref'], path)))
    return ['TASK_EVIDENCE: mismatch in ' + k for k, v in expected.items() if report.get(k) != v]


def _evidence(root, ref, task, metadata):
    content = journal.blob(root, ref, task['evidence'])
    if proof.digest(content) != task['evidence_sha256']:
        return ['TASK_EVIDENCE: artifact digest mismatch']
    report = json.loads(content)
    if not isinstance(report, dict):
        return ['TASK_EVIDENCE: expected an object']
    if not journal.ancestor(root, task['verified_ref'], journal.commit_sha(root, ref)):
        return ['TASK_EVIDENCE: tested commit is not an ancestor']
    return (_proof_fields(root, task, report, metadata) + _proof_refs(root, task, report)
            + _proof_output(report, metadata))


def validate_snapshot(repo_root, ref='main'):
    root = Path(repo_root).resolve()
    try:
        revision = journal.commit_sha(root, ref)
        tasks = journal.read_tasks(root, revision)
        errors = _dependencies(tasks)
        for task in tasks.values():
            if task['status'] == 'backlog':
                metadata, _ = parse_frontmatter(journal.blob(root, revision, task['contract']))
                if not isinstance(metadata, dict) or metadata.get('type') != 'Task Contract':
                    errors.append('TASK_CONTRACT: linked contract is not a Task Contract')
                continue
            tested = task['verified_ref'] if task['status'] == 'done' else revision
            metadata = journal.contract_metadata(root, task, tested)
            if task['status'] == 'done':
                errors.extend(_evidence(root, revision, task, metadata))
        return errors
    except (TaskError, ValueError, OSError, KeyError) as exc:
        return ['TASK_SNAPSHOT: ' + str(exc)]


def _transition_scope(old, new, identifier, parent):
    errors, allowed = [], {task_path(identifier)}
    if old is None:
        allowed.add('knowledge/index.md')
    if new and new['status'] == 'done':
        allowed.add(new['evidence'])
        if new['verified_ref'] != parent:
            errors.append('TASK_CLOSURE: tested commit must be the immediate parent')
    if old and not old['branch_base'] and new and new['status'] == 'in_progress':
        if new['branch_base'] != parent:
            errors.append('TASK_BRANCH: initial branch base must be the start parent')
    return errors, allowed


def _audit_import(root, parents, nodes, changed, cache):
    if len(parents) != 2:
        return ['TASK_IMPORT: only two-parent journal imports are supported']
    bases = journal.git(root, 'merge-base', '--all', *parents).splitlines()
    if len(bases) != 1:
        return ['TASK_IMPORT: journal import requires an unambiguous fork']
    fork, source = journal.read_nodes(root, bases[0]), journal.read_nodes(root, parents[1])
    before, after = nodes
    errors = []
    for identifier in changed:
        if before.get(identifier) != fork.get(identifier):
            errors.append('TASK_IMPORT: concurrent target change to ' + identifier)
        if identifier not in source or after.get(identifier) != source.get(identifier):
            errors.append('TASK_IMPORT: merge must preserve the source node ' + identifier)
    return errors + _audit_range(root, bases[0], parents[1], cache)


def _audit_commit(root, parent, revision, cache):
    before, after = journal.read_nodes(root, parent), journal.read_nodes(root, revision)
    changed = [key for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]
    parents = journal.git(root, 'rev-list', '--parents', '-n', '1', revision).split()[1:]
    if len(parents) > 1:
        errors = _audit_import(root, parents, (before, after), changed, cache)
        return errors + ['{}: {}'.format(revision, e) for e in validate_snapshot(root, revision)]
    completed = {key for key, pair in before.items() if pair[0]['status'] == 'done'}
    errors, allowed = [], set()
    for identifier in changed:
        old = before[identifier][0] if identifier in before else None
        new = after[identifier][0] if identifier in after else None
        errors.extend(validate_transition(old, new, completed))
        scope_errors, scope = _transition_scope(old, new, identifier, parent)
        errors.extend(scope_errors)
        allowed.update(scope)
    if changed:
        actual = set(filter(None, journal.git(root, 'diff', '--no-ext-diff', '--name-only', '-z', parent, revision).split('\0')))
        if not actual.issubset(allowed):
            errors.append('TASK_SCOPE: task transition commit contains unrelated changes')
    return ['{}: {}'.format(revision, e) for e in errors + validate_snapshot(root, revision)]


def _audit_range(root, base, head, cache):
    key = (base, head)
    if key in cache:
        return cache[key]
    chain = journal.git(root, 'rev-list', '--first-parent', '--reverse', head).splitlines()
    if base not in chain:
        return ['TASK_BASELINE: base must be on the first-parent history of head']
    errors = validate_snapshot(root, base)
    parent = base
    for revision in chain[chain.index(base) + 1:]:
        errors.extend(_audit_commit(root, parent, revision, cache))
        parent = revision
    cache[key] = errors
    return errors


def validate_range(repo_root, base_ref, head_ref):
    root = Path(repo_root).resolve()
    try:
        base, head = journal.commit_sha(root, base_ref), journal.commit_sha(root, head_ref)
        return _audit_range(root, base, head, {})
    except (TaskError, ValueError, OSError, KeyError, RecursionError) as exc:
        return ['TASK_HISTORY: ' + str(exc)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--base-ref')
    parser.add_argument('--head-ref', default='main')
    args = parser.parse_args(argv)
    findings = (validate_range(args.repo_root, args.base_ref, args.head_ref) if args.base_ref
                else validate_snapshot(args.repo_root, args.head_ref))
    for finding in findings:
        print('ERROR [{}]'.format(finding))
    print('Task validation: {} error(s)'.format(len(findings)))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
