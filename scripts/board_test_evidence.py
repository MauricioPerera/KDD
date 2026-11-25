"""Project a task's canonical evidence into Board without exporting runner logs."""

import argparse
import json
import os
from pathlib import Path
import sys

import task_git as journal
from task_model import TaskError, parse_task, task_path
from validate_tasks import _evidence, _receipt_object


_MAX_RECEIPT = 4 * 1024 * 1024


class MissingTask(TaskError):
    pass


def _receipt_projection(report):
    version = report['schema_version']
    files = [{'path': name, **counts}
             for name, counts in sorted(report.get('oracle_results', {}).items())] if version == 2 else []
    return {
        'version': version,
        'runner': report['runner'],
        'total': report['passed_tests'],
        'granularity': 'file' if version == 2 else 'run',
        'files': files,
    }


def _read_receipt(root, commit, task):
    expected = 'docs/task-evidence/{}-{}.json'.format(task['task_id'], task['verified_ref'])
    path = task['evidence']
    if path != expected:
        raise TaskError('Unexpected task receipt path')
    journal._committed_paths(root, commit, [path])
    size = journal.git(root, 'cat-file', '-s', commit + ':' + path)
    if int(size) > _MAX_RECEIPT:
        raise TaskError('Task receipt exceeds the size limit')
    metadata = journal.contract_metadata(root, task, task['verified_ref'], committed_only=True)
    if _evidence(root, commit, task, metadata):
        raise TaskError('Invalid task receipt')
    return json.loads(journal.blob(root, commit, path), object_pairs_hook=_receipt_object)


def project_evidence(root, task_id):
    with journal.object_cache():
        commit = journal.commit_sha(root, 'refs/heads/main')
        node = task_path(task_id)
        entries = journal._regular_paths(journal.git(root, 'ls-tree', '-z', commit, '--', node))
        if node not in entries:
            raise MissingTask('Task not found')
        task, _ = parse_task(journal.blob(root, commit, node), node)
        identity = {'task_id': task_id, 'observed_commit': commit}
        if task['status'] != 'done':
            return {'status': 'pending', **identity}
        report = _read_receipt(root, commit, task)
        return {
            'status': 'available',
            **identity,
            'approved_ref': task['approved_ref'],
            'tested_commit': task['verified_ref'],
            'artifact': {'path': task['evidence'], 'sha256': task['evidence_sha256']},
            'receipt': _receipt_projection(report),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('task_id')
    args = parser.parse_args(argv)
    for name in list(os.environ):
        if name.startswith('GIT_'):
            os.environ.pop(name)
    os.environ.update(
        GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0',
        GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1',
        GIT_CONFIG_GLOBAL=os.devnull,
    )
    try:
        result = project_evidence(Path(args.repo_root).resolve(), args.task_id)
    except MissingTask:
        print('TASK_MISSING: task not found', file=sys.stderr)
        return 1
    except (TaskError, OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        print('TASK_EVIDENCE_INVALID: invalid task evidence', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
