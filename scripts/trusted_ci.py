"""Start verification from an exact external Git bundle, with fresh evidence."""
import sys

if __name__ == '__main__' and not sys.flags.isolated:
    raise SystemExit('FAIL: trusted_ci requires python -I')
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

RUNTIME_FILES = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
                 'validate_contracts.py', 'process_tree.py', 'execution_profile.py')


def _git(root, *args):
    return subprocess.check_output(['git', '--no-pager', *args], cwd=root,
                                   stderr=subprocess.PIPE, timeout=30)


def prepare_bundle(repo_root, trusted_ref, bundle_dir) -> dict:
    root, destination = Path(repo_root).resolve(), Path(bundle_dir).resolve()
    if not re.fullmatch(r'[0-9a-fA-F]{40}', trusted_ref):
        raise ValueError('trusted runtime requires an explicit full commit SHA')
    trusted_ref = trusted_ref.lower()
    if destination.is_relative_to(root):
        raise ValueError('trusted bundle must be outside the candidate checkout')
    if os.path.lexists(bundle_dir):
        raise ValueError('trusted bundle destination already exists')
    if _git(root, 'cat-file', '-t', trusted_ref).strip() != b'commit':
        raise ValueError('trusted runtime is not a commit')
    blobs = {}
    for name in RUNTIME_FILES:
        path = 'scripts/' + name
        entry = _git(root, 'ls-tree', trusted_ref, '--', path)
        if not entry.startswith((b'100644 blob ', b'100755 blob ')):
            raise ValueError('trusted runtime is missing a regular file: ' + path)
        blobs[name] = _git(root, 'show', trusted_ref + ':' + path)
    manifest = dict(version=1, trusted_ref=trusted_ref,
                    files={name: hashlib.sha256(data).hexdigest() for name, data in blobs.items()})
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, content in blobs.items():
            (destination / name).write_bytes(content)
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    except BaseException:
        # Only remove entries this call created inside its exclusive directory.
        for name in (*RUNTIME_FILES, 'manifest.json'):
            (destination / name).unlink(missing_ok=True)
        destination.rmdir()
        raise
    return manifest


def _runtime(root):
    directory = Path(__file__).resolve().parent
    if directory.is_relative_to(root):
        raise ValueError('verification must run from an external trusted bundle')
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('version') != 1 or set(manifest.get('files', {})) != set(RUNTIME_FILES)
            or not re.fullmatch(r'[0-9a-f]{40}', manifest.get('trusted_ref', ''))):
        raise ValueError('invalid trusted runtime manifest')
    for name in RUNTIME_FILES:
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != manifest['files'][name]:
            raise ValueError('trusted runtime bytes changed: ' + name)
    # This path contains only the six already verified runtime files, no checkout.
    sys.path.insert(0, str(directory))
    return directory, manifest


def _safe_print(text):
    encoding = sys.stdout.encoding or 'utf-8'
    print(text.encode(encoding, errors='backslashreplace').decode(encoding), end='')


def _suite(args, directory):
    import run_test_suite as suite
    from process_tree import run
    with tempfile.TemporaryDirectory(prefix='kdd-trusted-suite-') as temporary:
        report_path = Path(temporary) / 'suite.json'
        proc = run([sys.executable, '-I', '-X', 'utf8', str(directory / 'run_test_suite.py'),
                    '--start-directory', args.start_directory, '--pattern', args.pattern,
                    '--workers', str(args.workers), '--report-json', str(report_path)],
                   cwd=args.repo_root, timeout=1800, capture_output=True, text=True,
                   encoding='utf-8', errors='backslashreplace')
        _safe_print(proc.stdout or '')
        _safe_print(proc.stderr or '')
        try:
            data = json.loads(report_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
    ids = data.get('expected_ids') if isinstance(data, dict) else None
    if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
        data = suite._empty([])
        suite._problem(data, 'trusted suite evidence absent or corrupt')
    else:
        data = suite._reconcile(ids, data)
    if not data['expected_ids']:
        suite._problem(data, 'trusted suite inventory is empty')
    if proc.returncode != 0:
        suite._problem(data, 'trusted suite process exit code ' + str(proc.returncode))
    return data


def _commands(args, directory):
    import validate_test_commands as gate
    contracts = Path(args.contracts_dir)
    if not contracts.is_absolute():
        contracts = Path(args.repo_root) / contracts
    planned = gate.collect_contracts(str(contracts))
    exclusive = gate.parse_exclusive_commands(args.exclusive_commands_json)
    results = gate.run_all(str(contracts), args.repo_root, timeout=args.timeout,
                           deduplicate=args.deduplicate, workers=args.workers,
                           trusted_bundle=directory, exclusive_commands=exclusive)
    expected = [(item['path'], item['test_command']) for item in planned]
    actual = [(item['path'], item['test_command']) for item in results]
    ok = bool(results) and expected == actual and all(
        item['ok'] is True and item['exit_code'] == 0 and item['error'] is None for item in results)
    gate._print_results(results)
    return dict(version=1, ok=ok, results=results, contracts=len(planned),
                exclusive_commands=list(exclusive))


def _report_destination(args):
    if args.report_json:
        if os.path.lexists(args.report_json):
            raise ValueError('evidence destination already exists')
        path = Path(args.report_json).resolve()
    else:
        path = Path(args.report_dir).resolve() / ('evidence-' + uuid.uuid4().hex + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively, including rejection of a pre-existing symlink.
    with path.open('x', encoding='utf-8'):
        pass
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--repo-root', required=True)
    prepare.add_argument('--trusted-ref', required=True)
    prepare.add_argument('--bundle-dir', required=True)
    for mode in ('suite', 'commands'):
        command = commands.add_parser(mode)
        command.add_argument('--repo-root', required=True)
        command.add_argument('--workers', type=int, default=1)
        report = command.add_mutually_exclusive_group(required=True)
        report.add_argument('--report-json')
        report.add_argument('--report-dir')
        if mode == 'suite':
            command.add_argument('--start-directory', default='tests')
            command.add_argument('--pattern', default='test_*.py')
        else:
            command.add_argument('--contracts-dir', default='knowledge/contracts')
            command.add_argument('--timeout', type=float, default=600)
            command.add_argument('--deduplicate', action='store_true')
            command.add_argument('--exclusive-commands-json', default='[]')
    args = parser.parse_args(argv)
    destination = None
    try:
        if args.command == 'prepare':
            print(json.dumps(prepare_bundle(args.repo_root, args.trusted_ref, args.bundle_dir), sort_keys=True))
            return 0
        args.repo_root = str(Path(args.repo_root).resolve())
        directory, manifest = _runtime(Path(args.repo_root))
        if not 1 <= args.workers <= 8:
            raise ValueError('workers must be an integer between 1 and 8')
        destination = _report_destination(args)
        data = _suite(args, directory) if args.command == 'suite' else _commands(args, directory)
        data['trusted_runtime_ref'] = manifest['trusted_ref']
        destination.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        print('KDD_EVIDENCE ' + json.dumps(dict(path=str(destination),
              sha256=hashlib.sha256(destination.read_bytes()).hexdigest())))
        return 0 if data['ok'] is True else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if destination is not None:
            destination.write_text(json.dumps(dict(version=1, ok=False, error=str(exc))) + '\n', encoding='utf-8')
        _safe_print('FAIL: ' + str(exc) + '\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
