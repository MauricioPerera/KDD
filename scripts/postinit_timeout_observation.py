"""Summarize the worker files left by one interrupted post-init suite."""
import argparse
import json
import os
from pathlib import Path
import re
import stat


MAX_BYTES = 256 * 1024
MODULE_NAME = re.compile(r'(?:[A-Za-z_][A-Za-z0-9_]*\.)*test_[A-Za-z0-9_]+')
INDEX = re.compile(r'0|[1-9][0-9]*')


def _reparse(info):
    return getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT


def _directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or _reparse(info):
        raise ValueError('unusable observation directory')


def _file_identity(info):
    if (not stat.S_ISREG(info.st_mode) or _reparse(info)
            or info.st_nlink != 1 or info.st_size > MAX_BYTES):
        raise ValueError('unusable observation file')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('duplicate JSON key')
    return result


def _nonfinite(_value):
    raise ValueError('non-finite JSON constant')


def _read(path):
    before = path.lstat()
    identity = _file_identity(before)
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb', buffering=0) as stream:
        if _file_identity(os.fstat(stream.fileno())) != identity:
            raise ValueError('observation file changed before reading')
        raw = stream.read(MAX_BYTES)
        if len(raw) != before.st_size or _file_identity(os.fstat(stream.fileno())) != identity:
            raise ValueError('observation file changed while reading')
    if _file_identity(path.lstat()) != identity:
        raise ValueError('observation path changed while reading')
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    if not isinstance(data, dict):
        raise ValueError('observation file must contain an object')
    return data, before.st_mtime_ns


def _indexed(directory, prefix):
    files = {}
    for path in directory.glob(prefix + '-*.json'):
        name = path.stem.removeprefix(prefix + '-')
        if not INDEX.fullmatch(name):
            raise ValueError('invalid observation index')
        files[int(name)] = path
    return files


def _ids(values):
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise ValueError('invalid case identities')
    unique = set(values)
    if len(unique) != len(values):
        raise ValueError('duplicate case identity')
    return unique


def _inventory(items, origin):
    if not isinstance(items, list):
        raise ValueError('invalid worker inventory')
    entries = {}
    for item in items:
        if not isinstance(item, dict) or item.get('origin') != origin:
            raise ValueError('foreign worker inventory')
        identity = item.get('id')
        if not isinstance(identity, str) or not identity or identity in entries:
            raise ValueError('invalid worker inventory identity')
        entries[identity] = item
    return entries


def _plan(data):
    origin = data.get('origin')
    if not isinstance(origin, str) or not MODULE_NAME.fullmatch(origin):
        raise ValueError('invalid module name')
    inventory = _inventory(data.get('inventory'), origin)
    if not inventory or _ids(data.get('ids')) != inventory.keys():
        raise ValueError('plan inventory does not match its cases')
    return origin, inventory


def _compatible(data, origin, inventory):
    if type(data.get('version')) is not int or data['version'] != 1 or type(data.get('ok')) is not bool:
        raise ValueError('invalid worker result')
    if (_ids(data.get('expected_ids')) != inventory.keys()
            or _inventory(data.get('inventory'), origin) != inventory):
        raise ValueError('result inventory does not match the plan')
    executed = _ids(data.get('executed_ids'))
    omitted = _ids(data.get('fixture_omitted_ids'))
    if executed & omitted or (executed | omitted) - inventory.keys():
        raise ValueError('foreign or conflicting cases in worker result')


def _applicable_plans(directory, source):
    paths = _indexed(directory, 'plan')
    selected = {}
    for index, path in paths.items():
        data, modified = _read(path)
        start = data.get('start_dir')
        if not isinstance(start, str) or '\0' in start or not Path(start).is_absolute():
            raise ValueError('invalid plan source')
        if Path(start) == source:
            selected[index] = data, modified
    if selected and len(selected) != len(paths):
        raise ValueError('mixed project sources in one suite')
    return selected


def _modules(directory, plans):
    results = _indexed(directory, 'result')
    if results.keys() - plans.keys():
        raise ValueError('result has no plan')
    modules, names = [], set()
    for index, (data, started) in sorted(plans.items()):
        origin, inventory = _plan(data)
        if origin in names:
            raise ValueError('duplicate module plan')
        names.add(origin)
        elapsed = None
        if index in results:
            result, finished = _read(results[index])
            _compatible(result, origin, inventory)
            if finished < started:
                raise ValueError('result predates plan')
            elapsed = (finished - started) / 1e9
        modules.append(dict(index=index, name=origin, cases=len(inventory),
                            phase='incomplete' if elapsed is None else 'completed',
                            duration_seconds=elapsed))
    return modules


def observe(temp_root, project_root):
    temp = Path(os.path.abspath(temp_root))
    project = Path(os.path.abspath(project_root))
    if project.parent != temp:
        raise ValueError('project must be a direct child of the observation root')
    source = project / 'tests'
    for path in (*reversed(source.parents), source):
        _directory(path)
    selected = None
    for directory in temp.glob('kdd-suite-*'):
        _directory(directory)
        plans = _applicable_plans(directory, source)
        if plans:
            if selected is not None:
                raise ValueError('more than one suite for the selected project')
            selected = directory, plans
    if selected is None:
        return dict(state='not_found', modules=[])
    return dict(state='partial', modules=_modules(*selected))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temp-root', required=True)
    parser.add_argument('--project-root', required=True)
    args = parser.parse_args(argv)
    try:
        result = observe(args.temp_root, args.project_root)
    except (OSError, ValueError, RecursionError):
        result = dict(state='inconclusive', modules=[])
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
