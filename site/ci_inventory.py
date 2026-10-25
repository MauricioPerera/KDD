"""Strict discovery and local consumption of reviewed CI inventory artifacts."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import unittest

REPOSITORY = 'MauricioPerera/KDD'
WORKFLOW = '.github/workflows/validate.yml'
PLATFORMS = ('ubuntu-latest', 'windows-latest')
RUN_URL = re.compile(r'https://github\.com/MauricioPerera/KDD/actions/runs/([0-9]+)\Z')


class InventoryError(ValueError):
    pass


def fail(message, kind='PAGES_CI_INVENTORY'):
    raise InventoryError(kind + ': ' + message)


def ids_digest(ids):
    return hashlib.sha256(('\n'.join(ids) + '\n').encode('utf-8')).hexdigest()


def valid_ids(ids, kind='PAGES_CI_INVENTORY'):
    if (not isinstance(ids, list) or not ids or
            any(not isinstance(i, str) or not i or '\n' in i or '\r' in i for i in ids)):
        fail('empty or invalid inventory', kind)
    if ids != sorted(set(ids)) or any('unittest.loader._FailedTest.' in i for i in ids):
        fail('duplicate, unordered or failed-discovery IDs', kind)
    return ids


def integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        fail('invalid ' + name)
    return value


def hexadecimal(value, length, name):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{' + str(length) + '}', value):
        fail('invalid ' + name)
    return value


def script_module(repo, name):
    spec = importlib.util.spec_from_file_location('_pages_' + name, repo / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def revision(repo):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                   text=True, encoding='utf-8', timeout=30).strip()
    hexadecimal(head, 40, 'checkout SHA')
    clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=repo, timeout=30)
    if clean.returncode:
        fail('tracked source differs from the checkout SHA')
    return head


def load_json(path):
    if path.is_symlink() or not path.is_file():
        fail('missing or unsafe inventory/report: ' + str(path))
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        fail('invalid JSON evidence: ' + str(exc))


def discover(repo):
    """Runs only in the fresh child; never executes a discovered case."""
    def walk(suite):
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                yield from walk(case)
            else:
                yield case.id()
    sys.path.insert(0, str(repo))
    loader = unittest.TestLoader()
    with contextlib.redirect_stdout(io.StringIO()):
        suite = loader.discover(str(repo / 'tests'), pattern='test_*.py')
        ids = list(walk(suite))
    if loader.errors:
        fail('\n'.join(loader.errors), 'PAGES_DISCOVERY')
    return valid_ids(sorted(ids), 'PAGES_DISCOVERY')


def fresh_discovery(repo):
    try:
        run = script_module(repo, 'process_tree').run
        proc = run([sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()),
                    'discover', '--repo-root', str(repo)], cwd=repo, timeout=120,
                   capture_output=True, text=True, encoding='utf-8')
        if proc.returncode:
            fail(proc.stderr.strip() or 'discovery process failed', 'PAGES_DISCOVERY')
        return valid_ids(json.loads(proc.stdout), 'PAGES_DISCOVERY')
    except InventoryError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        fail('discovery could not complete: ' + str(exc), 'PAGES_DISCOVERY')


def pass_summary(data, raw, ids, trusted_ref, validator):
    if not isinstance(data, dict) or data.get('ok') is not True:
        fail('suite report did not pass')
    if data.get('trusted_runtime_ref') != trusted_ref:
        fail('suite report uses a different trusted runtime')
    try:
        problems = validator(ids, data)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        fail('malformed suite report: ' + str(exc))
    if problems:
        fail('invalid suite accounting: ' + '; '.join(problems))
    result = dict(report_sha256=hashlib.sha256(raw).hexdigest(), tests_run=data['tests_run'],
                  skipped_count=len(data['skipped']), fixture_omitted_count=len(data['fixture_omitted_ids']),
                  duration_seconds=data.get('duration_seconds'))
    validate_pass(result, len(ids))
    return result


def validate_pass(record, count):
    if not isinstance(record, dict):
        fail('invalid pass record')
    hexadecimal(record.get('report_sha256'), 64, 'report hash')
    for key in ('tests_run', 'skipped_count', 'fixture_omitted_count'):
        integer(record.get(key), key, minimum=0)
    if (record['tests_run'] + record['fixture_omitted_count'] != count or
            record['skipped_count'] > record['tests_run']):
        fail('pass counts do not explain the inventory')
    duration = record.get('duration_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        fail('invalid pass duration')


def export_inventory(repo_root, reports_dir, output, *, run_id, run_attempt, head_sha,
                     platform, trusted_runtime_ref):
    repo, source, target = Path(repo_root).resolve(), Path(reports_dir).resolve(), Path(output).resolve()
    integer(run_id, 'run_id'); integer(run_attempt, 'run_attempt')
    hexadecimal(trusted_runtime_ref, 40, 'trusted runtime')
    if platform not in PLATFORMS or head_sha != revision(repo):
        fail('platform or checkout SHA does not match')
    if target.exists() or target.is_symlink() or target == repo or repo in target.parents:
        fail('output must be new and outside the checkout')
    files = sorted(source.glob('*.json'))
    if len(files) != 2:
        fail('exactly two fresh suite reports are required')
    validator = script_module(repo, 'run_test_suite').validate_report
    inventory, passes = None, []
    for path in files:
        data = load_json(path)
        ids = valid_ids(data.get('expected_ids') if isinstance(data, dict) else None)
        if inventory is not None and ids != inventory:
            fail('suite passes have different IDs')
        inventory = ids
        passes.append(pass_summary(data, path.read_bytes(), ids, trusted_runtime_ref, validator))
    if len({p['report_sha256'] for p in passes}) != 2:
        fail('suite report replay')
    manifest = dict(schema_version=1, repository=REPOSITORY, workflow_path=WORKFLOW,
                    run_id=run_id, run_attempt=run_attempt, head_sha=head_sha, platform=platform,
                    trusted_runtime_ref=trusted_runtime_ref, ids=inventory,
                    ids_sha256=ids_digest(inventory), passes=passes)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=True) + '\n')
    return manifest


def consume_inventory(repo, run_id, context):
    if not isinstance(context, dict) or set(context) != {'directory', 'run_attempt', 'trusted_runtime_ref'}:
        fail('incomplete CI inventory context')
    attempt = integer(context['run_attempt'], 'run_attempt')
    trusted = hexadecimal(context['trusted_runtime_ref'], 40, 'trusted runtime')
    root = Path(context['directory']).resolve()
    expected = {root / platform / 'inventory.json' for platform in PLATFORMS}
    if set(root.rglob('*.json')) != expected:
        fail('both platform manifests are required, without extra JSON evidence')
    head, inventory, hashes = revision(repo), None, []
    identity = dict(schema_version=1, repository=REPOSITORY, workflow_path=WORKFLOW,
                    run_id=run_id, run_attempt=attempt, head_sha=head, trusted_runtime_ref=trusted)
    for platform in PLATFORMS:
        data = load_json(root / platform / 'inventory.json')
        if not isinstance(data, dict):
            fail('manifest is not an object')
        integer(data.get('schema_version'), 'schema_version')
        integer(data.get('run_id'), 'run_id'); integer(data.get('run_attempt'), 'run_attempt')
        if any(data.get(key) != value for key, value in identity.items()) or data.get('platform') != platform:
            fail('manifest identity differs from the triggering run/attempt/SHA/runtime')
        ids = valid_ids(data.get('ids'))
        if data.get('ids_sha256') != ids_digest(ids) or (inventory is not None and ids != inventory):
            fail('platform inventories or digests disagree')
        inventory = ids
        passes = data.get('passes')
        if not isinstance(passes, list) or len(passes) != 2:
            fail('each platform must contain two passes')
        for record in passes:
            validate_pass(record, len(ids)); hashes.append(record['report_sha256'])
    if len(set(hashes)) != 4:
        fail('replayed pass evidence across platforms')
    return inventory


def inspect_inventory(repo_root, ci_run_url, ci_inventory=None):
    repo = Path(repo_root).resolve()
    match = RUN_URL.fullmatch(ci_run_url)
    if not match or int(match[1]) <= 0:
        fail('CI URL must identify an exact KDD run')
    expected = consume_inventory(repo, int(match[1]), ci_inventory) if ci_inventory is not None else None
    ids = fresh_discovery(repo)
    if expected is not None and expected != ids:
        fail('local discovery IDs differ from the real CI inventory')
    return dict(ids=ids, ids_sha256=ids_digest(ids), tests=len(ids),
                inventory_source='ci-verified' if expected is not None else 'discovery-preview')


def cli_context(args):
    values = (args.ci_inventory_dir, args.ci_run_attempt, args.ci_trusted_runtime_ref)
    if any(v is not None for v in values):
        if any(v is None for v in values):
            fail('all CI inventory context arguments are required together')
        return dict(directory=values[0], run_attempt=values[1], trusted_runtime_ref=values[2])
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--repo-root', required=True); inspect.add_argument('--ci-run-url', required=True)
    inspect.add_argument('--ci-inventory-dir'); inspect.add_argument('--ci-run-attempt', type=int)
    inspect.add_argument('--ci-trusted-runtime-ref')
    child = commands.add_parser('discover'); child.add_argument('--repo-root', required=True)
    export = commands.add_parser('export')
    for flag in ('repo-root', 'reports-dir', 'output', 'head-sha', 'platform', 'trusted-runtime-ref'):
        export.add_argument('--' + flag, required=True)
    export.add_argument('--run-id', type=int, required=True); export.add_argument('--run-attempt', type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'discover':
            result = discover(Path(args.repo_root).resolve())
        elif args.command == 'inspect':
            result = inspect_inventory(args.repo_root, args.ci_run_url, cli_context(args))
        else:
            result = export_inventory(args.repo_root, args.reports_dir, args.output, run_id=args.run_id,
                                      run_attempt=args.run_attempt, head_sha=args.head_sha, platform=args.platform,
                                      trusted_runtime_ref=args.trusted_runtime_ref)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        message = str(exc)
        print(message if message.startswith(('PAGES_DISCOVERY:', 'PAGES_CI_INVENTORY:'))
              else 'PAGES_CI_INVENTORY: ' + message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
