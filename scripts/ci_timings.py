"""Export a diagnostic projection of the existing CI timing reports."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import tempfile


ERROR = 'CI timing diagnostics could not be exported.'
CONTROLLER = 'controller diagnostics'


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, ERROR + '\n')


def _positive_number(value):
    if not re.fullmatch(r'[0-9]+', value) or int(value) < 1:
        raise ValueError('invalid run identifier')
    return int(value)


def _identity(args):
    for oid in (args.head_sha, args.trusted_runtime_ref):
        if not re.fullmatch(r'[0-9a-f]{40}', oid):
            raise ValueError('invalid identity SHA')
    return {
        'run_id': _positive_number(args.run_id),
        'run_attempt': _positive_number(args.run_attempt),
        'head_sha': args.head_sha,
        'platform': args.platform,
        'trusted_runtime_ref': args.trusted_runtime_ref,
    }


def _metadata(path):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError('redirected path')
    return info


def _directory(path, *, allow_missing=False):
    for part in (*reversed(path.parents), path):
        try:
            info = _metadata(part)
        except FileNotFoundError:
            if allow_missing:
                return False
            raise
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('expected a directory')
    return True


def _input_files(directory, limit):
    directory = Path(os.path.abspath(directory))
    if not _directory(directory, allow_missing=True):
        return []
    reports = [path for path in directory.iterdir()
               if path.name.startswith('evidence-') and path.name.endswith('.json')]
    if len(reports) > limit:
        raise ValueError('ambiguous report inventory')
    return reports


def _unique_object(pairs):
    document = {}
    for name, value in pairs:
        if name in document:
            raise ValueError('duplicate JSON key')
        document[name] = value
    return document


def _invalid_number(_value):
    raise ValueError('invalid JSON number')


def _duration(value):
    if type(value) not in (int, float) or value < 0:
        raise ValueError('invalid duration')
    if type(value) is float and not math.isfinite(value):
        raise ValueError('invalid duration')
    return value


def _status(value):
    if type(value) is not bool:
        raise ValueError('invalid status')
    return value


def _exit_code(value):
    if value is not None and type(value) is not int:
        raise ValueError('invalid exit code')
    return value


def _contract_path(value, root):
    if not isinstance(value, str) or not value or not value.isprintable():
        raise ValueError('invalid contract path')
    # CI reports use native absolute paths or relative paths with either separator.
    local = Path(value.replace('\\', '/'))
    if PureWindowsPath(value).drive and not local.is_absolute():
        raise ValueError('invalid drive')
    relative = Path(os.path.abspath(root / local)).relative_to(root)
    if not relative.parts:
        raise ValueError('expected a contract path')
    for path in reversed((root / relative).parents):
        if path != root and path.is_relative_to(root):
            try:
                _metadata(path)
            except FileNotFoundError:
                break
    try:
        _metadata(root / relative)
    except FileNotFoundError:
        pass
    return relative.as_posix()


def _command_row(row, root):
    scope = row['scope']
    if scope not in ('product', 'infrastructure'):
        raise ValueError('invalid command scope')
    duration = _duration(row['duration_seconds'])
    representative = row['shared_from']
    if representative is not None:
        if duration != 0:
            raise ValueError('nonzero shared duration')
        representative = _contract_path(representative, root)
    return {
        'contract': _contract_path(row['path'], root),
        'scope': scope,
        'duration_seconds': duration,
        'exit_code': _exit_code(row['exit_code']),
        'recorded_ok': _status(row['ok']),
        'shared_from': representative,
    }


def _suite_row(row):
    module, tests_run = row['module'], row['tests_run']
    if not isinstance(module, str):
        raise ValueError('invalid module')
    if module != CONTROLLER and not all(part.isidentifier() for part in module.split('.')):
        raise ValueError('invalid module')
    if type(tests_run) is not int or tests_run < 0 or (module == CONTROLLER and tests_run):
        raise ValueError('invalid test count')
    return {
        'module': module,
        'duration_seconds': _duration(row['duration_seconds']),
        'tests_run': tests_run,
        'exit_code': _exit_code(row['exit_code']),
    }


def _rows(document, key):
    rows = document[key]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('invalid metric rows')
    return rows


def _source(path, kind, root, runtime):
    if not stat.S_ISREG(_metadata(path).st_mode):
        raise ValueError('report must be a regular file')
    raw = path.read_bytes()
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=_invalid_number)
    version = data['version']
    if type(version) is not int or version != 1 or data['trusted_runtime_ref'] != runtime:
        raise ValueError('unexpected report version or runtime')
    if kind == 'commands':
        rows = [_command_row(row, root) for row in _rows(data, 'results')]
        duration, label = None, 'contract'
    else:
        rows = [_suite_row(row) for row in _rows(data, 'modules')]
        duration, label = _duration(data['duration_seconds']), 'module'
    rows.sort(key=lambda row: (-row['duration_seconds'], row[label]))
    return {
        'kind': kind,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'recorded_ok': _status(data['ok']),
        'duration_seconds': duration,
        'rows': rows,
    }


def _projection(args):
    identity = _identity(args)
    root = Path(os.path.abspath(args.repo_root))
    _directory(root)
    commands = _input_files(args.commands_dir, 1)
    suites = _input_files(args.suites_dir, 2)
    runtime = identity['trusted_runtime_ref']
    sources = [_source(path, 'commands', root, runtime) for path in commands]
    suite_sources = [_source(path, 'suite', root, runtime) for path in suites]
    if len({source['source_sha256'] for source in suite_sources}) != len(suites):
        raise ValueError('duplicate suite report')
    sources.extend(sorted(suite_sources, key=lambda source: source['source_sha256']))
    missing = [] if commands else ['commands-report']
    missing.extend('suite-report-' + str(index) for index in range(len(suites) + 1, 3))
    return {
        'schema_version': 1,
        'kind': 'kdd-ci-timings',
        'identity': identity,
        'complete': not missing,
        'missing': missing,
        'sources': sources,
    }


def _publish(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish the completed bytes in one operation with exclusive destination.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                    dir=path.parent, prefix='.kdd-timings-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(document, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.close()
            os.link(temporary, path)
        finally:
            stream.close()
            temporary.unlink()


def main(argv=None):
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    for name in ('repo-root', 'commands-dir', 'suites-dir', 'output', 'run-id', 'run-attempt',
                 'head-sha', 'trusted-runtime-ref'):
        export.add_argument('--' + name, required=True)
    export.add_argument('--platform', required=True, choices=('ubuntu-latest', 'windows-latest'))
    args = parser.parse_args(argv)
    try:
        _publish(Path(args.output), _projection(args))
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        print(ERROR, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
