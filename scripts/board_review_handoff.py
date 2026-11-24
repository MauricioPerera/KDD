"""Project a task's local baseline reviews without granting approval."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

import baseline_review
from task_git import read_tasks, safe_path
from task_model import TaskError, task_path, valid_sha


MAX_BYTES = 256 * 1024
MAX_PREVIOUS = 8


def _identity(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or info.st_size > MAX_BYTES):
        raise ValueError('invalid handoff file')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read(root, relative):
    path = safe_path(root, relative)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    identity = _identity(before)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if _identity(opened) != identity:
            raise ValueError('handoff file changed before reading')
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (len(raw) != before.st_size or _identity(after) != identity
                or opened.st_ctime_ns != after.st_ctime_ns):
            raise ValueError('handoff file changed during reading')
    # On Windows lstat and fstat may expose different ctime values for one file.
    named = safe_path(root, relative).lstat()
    if _identity(named) != identity or before.st_ctime_ns != named.st_ctime_ns:
        raise ValueError('handoff path changed during reading')
    return raw.decode('utf-8')


def _entry(data):
    baseline_review._keys(data, 'base_commit candidate_commit')
    if not all(valid_sha(value) for value in data.values()):
        raise ValueError('expected exact Git object IDs')
    return data['base_commit'], data['candidate_commit']


def _selection(raw):
    selection = json.loads(raw, object_pairs_hook=baseline_review._json_pairs,
                           parse_constant=baseline_review._nonfinite)
    baseline_review._keys(selection, 'current previous')
    previous = selection['previous']
    if not isinstance(previous, list) or len(previous) > MAX_PREVIOUS:
        raise ValueError('invalid review history')
    entries = [_entry(selection['current']), *map(_entry, previous)]
    if len({candidate for _, candidate in entries}) != len(entries):
        raise ValueError('duplicate candidate')
    return entries


def _candidate(root, directory, entry, *, required):
    base, candidate = entry
    raw = _read(root, directory + candidate + '.json')
    if raw is None:
        if required:
            raise ValueError('historical review missing')
        facts = baseline_review.inspect_change(root, base, candidate)
        status = 'missing'
    else:
        facts = baseline_review.verify_review(root, base, candidate, raw)
        status = 'ready' if facts['review_ready'] else 'blocked'
    return {'base_commit': base, 'candidate_commit': candidate,
            'candidate_tree': facts['candidate_tree'], 'review_status': status,
            'review_sha256': facts.get('review_sha256'),
            'finding_codes': sorted({finding['code'] for finding in facts.get('findings', [])})}


def project(root, task_id):
    task_path(task_id)
    task = read_tasks(root).get(task_id)
    if task is None:
        raise TaskError('TASK_MISSING: ' + task_id)
    result = dict(task_id=task_id, approved_ref=task['approved_ref'] or None,
                  evidence=task['evidence'] or None, current=None, previous=[])
    directory = '.agents/logs/board-reviews/' + task_id + '/'
    try:
        raw = _read(root, directory + 'selection.json')
        if raw is not None:
            current, *previous = _selection(raw)
            result['current'] = _candidate(root, directory, current, required=False)
            result['previous'] = [_candidate(root, directory, item, required=True) for item in previous]
    except (OSError, ValueError, RecursionError):
        # The Board only needs a public invalid-review outcome, not file diagnostics.
        return None
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True, type=Path)
    parser.add_argument('task_id')
    args = parser.parse_args(argv)
    try:
        result = project(args.repo_root.resolve(strict=True), args.task_id)
    except TaskError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'
    os.environ['GIT_NO_LAZY_FETCH'] = '1'
    os.environ['GIT_ALLOW_PROTOCOL'] = ''
    raise SystemExit(main())
