"""Run and verify the two native Windows post-init partitions."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import zipfile


REPOSITORY = 'MauricioPerera/KDD'
PATTERN = 'test_*.py'
OUTER_TEST = 'tests.test_init_project.TestInitProject.test_gates_verdes_post_apply_en_copia'
PROFILE = 'tools/ci/postinit-windows-shards.json'
MAX_RECEIPT = 1024 * 1024
TIMEOUT = 600
WORKERS = 10 if os.name == 'nt' else 4
IDENTITY_FIELDS = ('run_id', 'run_attempt', 'head_sha', 'tree', 'runtime_ref')
REPORT_FIELDS = ('expected_ids', 'executed_ids', 'fixture_omitted_ids', 'ok')
RECEIPT_FIELDS = {*IDENTITY_FIELDS, *REPORT_FIELDS, 'schema_version', 'shard', 'inventory'}
CHILD_PRIVATE = ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN',
                 'GITHUB_ENV', 'GITHUB_OUTPUT', 'GITHUB_PATH', 'GITHUB_STATE', 'GITHUB_STEP_SUMMARY',
                 'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'KDD_POSTINIT_SHARD',
                 'KDD_POSTINIT_RAW_REPORT')


class Pending(ValueError):
    """The current attempt can still produce evidence."""


def _load(path):
    spec = importlib.util.spec_from_file_location('_kdd_postinit_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _child_env():
    return {key: value for key, value in os.environ.items() if key not in CHILD_PRIVATE}


def _object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError('duplicate JSON field')
    return value


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object)


def _write(path, value, limit=None):
    raw = (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')
    if limit is not None and len(raw) > limit:
        raise ValueError('report exceeds byte limit')
    with path.open('xb') as output:
        output.write(raw)


def _profile(root):
    data = _json((root / PROFILE).read_bytes())
    if not isinstance(data, dict) or set(data) != {'schema_version', 'groups'} or (
            type(data['schema_version']) is not int or data['schema_version'] != 1):
        raise ValueError('invalid partition profile')
    groups = data['groups']
    if not isinstance(groups, list) or len(groups) != 2 or any(not isinstance(group, list) for group in groups):
        raise ValueError('partition profile needs two groups')
    names = groups[0] + groups[1]
    if any(not isinstance(name, str) or not all(part.isidentifier() for part in name.split('.'))
           for name in names):
        raise ValueError('invalid partition module name')
    if len(set(names)) != len(names):
        raise ValueError('duplicate module in partition profile')
    return groups


def _partition(root, runner):
    groups = _profile(root)
    sys.path.insert(0, str(root))
    loader = runner.DiscoveryLoader()
    suite = loader.discover(str(root / 'tests'), pattern=PATTERN)
    inventory = runner._inventory(list(runner._cases(suite)), loader)
    ids = [row['id'] for row in inventory]
    if loader.errors or not ids or len(set(ids)) != len(ids):
        raise ValueError('\n'.join(loader.errors) or 'empty or duplicate discovery inventory')
    owner = {name: index for index, group in enumerate(groups) for name in group}
    partitions = [[], []]
    for job in runner._module_jobs(inventory, groups[0] + groups[1]):
        name = job['module']
        index = owner.get(name)
        if index is None:
            index = hashlib.sha256(name.encode('utf-8')).digest()[0] % 2
        partitions[index].append(job)
    if not all(partitions):
        raise ValueError('empty partition')
    return partitions


def _expected(partitions):
    return [sorted(identity for job in jobs for identity in job['ids']) for jobs in partitions]


def _suite(root, shard, report_path):
    if os.path.lexists(report_path):
        raise ValueError('report destination already exists')
    started = time.perf_counter()
    runner = _load(root / 'scripts/run_test_suite.py')
    partitions = _partition(root, runner)
    expected = _expected(partitions)
    jobs = partitions[shard]
    report = runner._empty(expected[shard], [item for job in jobs for item in job['inventory']])
    runner._parallel_modules(report, jobs, str(root / 'tests'), PATTERN, WORKERS)
    for error in runner.validate_report(expected[shard], report):
        runner._problem(report, error)
    report.update(workers=WORKERS, duration_seconds=time.perf_counter() - started,
                  postinit_partition=dict(shard=shard, inventory=expected))
    _write(report_path, report)
    runner._summarize(report)
    return 0 if report['ok'] else 1


def discover(root):
    """Run full discovery with clean module state and no API credentials."""
    root = Path(root).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='kdd-postinit-discovery-') as directory:
        path = Path(directory) / 'inventory.json'
        command = [sys.executable, '-I', '-X', 'utf8', __file__, 'inventory',
                   '--repo-root', str(root), '--report-json', str(path)]
        subprocess.run(command, cwd=root, env=_child_env(), check=True, timeout=45)
        if not path.is_file():
            raise ValueError('independent discovery produced no inventory')
        return _canonical_inventory(_json(path.read_bytes()))


def _ids(value, field):
    if not isinstance(value, list) or any(
            not isinstance(item, str) or not 1 <= len(item) <= 1024 for item in value):
        raise ValueError('invalid ' + field)
    if value != sorted(set(value)):
        raise ValueError('duplicate or unordered ' + field)
    return value


def _canonical_inventory(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('inventory must have two partitions')
    left, right = (_ids(group, 'inventory') for group in value)
    if not left or not right or set(left).intersection(right):
        raise ValueError('empty or overlapping inventory')
    return value


def _receipt(data, expected, identity):
    if not isinstance(data, dict) or set(data) != RECEIPT_FIELDS or (
            type(data['schema_version']) is not int or data['schema_version'] != 1
            or type(data['shard']) is not int or data['shard'] not in (0, 1)
            or data['ok'] is not True):
        raise ValueError('invalid shard receipt')
    for key in IDENTITY_FIELDS:
        if data[key] != identity[key]:
            raise ValueError('receipt mismatch: ' + key)
    assigned = expected[data['shard']]
    if data['inventory'] != expected or data['expected_ids'] != assigned:
        raise ValueError('receipt inventory differs from independent discovery')
    executed = _ids(data['executed_ids'], 'executed_ids')
    omitted = _ids(data['fixture_omitted_ids'], 'fixture_omitted_ids')
    if sorted(executed + omitted) != assigned:
        raise ValueError('executed_ids and fixture omissions do not account for the assignment')
    return data['shard']


def _jobs(payload):
    rows = payload.get('jobs') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('invalid job list')
    groups = [[row for row in rows if row.get('name') == f'Windows post-init ({index})']
              for index in (0, 1)]
    if any(len(group) > 1 for group in groups):
        raise ValueError('duplicate post-init job')
    if not all(groups):
        raise Pending('waiting for both post-init jobs')
    selected = [group[0] for group in groups]
    ids = [row.get('id') for row in selected]
    if any(type(key) is not int or key <= 0 for key in ids) or ids[0] == ids[1]:
        raise ValueError('invalid or duplicate job ID')
    return selected


def _timestamp(raw):
    if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', raw):
        raise ValueError('invalid step timestamp')
    return datetime.fromisoformat(raw.replace('Z', '+00:00'))


def _interval(row, identity):
    for key in ('run_id', 'run_attempt', 'head_sha'):
        expected = identity['jobs_head_sha'] if key == 'head_sha' else int(identity[key])
        if type(row.get(key)) is not type(expected) or row[key] != expected:
            raise ValueError('job mismatch: ' + key)
    if row.get('status') in ('queued', 'in_progress', 'waiting', 'pending', 'requested'):
        raise Pending('waiting for post-init job completion')
    if row.get('status') != 'completed' or row.get('conclusion') != 'success':
        raise ValueError('post-init job did not succeed')
    steps = row.get('steps')
    matches = [item for item in steps if isinstance(item, dict)
               and item.get('name') == 'Run post-init shard'] if isinstance(steps, list) else []
    if len(matches) != 1 or matches[0].get('status') != 'completed' or (
            matches[0].get('conclusion') != 'success'):
        raise ValueError('expected one successful post-init step')
    start, end = (_timestamp(matches[0].get(key)) for key in ('started_at', 'completed_at'))
    if end <= start:
        raise ValueError('empty or reversed post-init step interval')
    return start, end


def verify(receipts, jobs, expected, identity):
    expected = _canonical_inventory(expected)
    if len(receipts) != 2 or {_receipt(row, expected, identity) for row in receipts} != {0, 1}:
        raise ValueError('expected one receipt from each shard')
    intervals = [_interval(row, identity) for row in _jobs(jobs)]
    earliest = min(start for start, _ in intervals)
    latest = max(end for _, end in intervals)
    wall = int((latest - earliest).total_seconds()) + 1
    if wall > TIMEOUT:
        raise ValueError(f'common post-init window {wall}s exceeds 600s')
    return dict(wall_bound_seconds=wall, shard_counts=[len(group) for group in expected])


def read_receipt_archive(raw):
    if len(raw) > MAX_RECEIPT * 2:
        raise ValueError('oversized receipt archive')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].orig_filename != 'receipt.json':
                raise ValueError('expected one receipt.json in the archive')
            info = entries[0]
            mode = stat.S_IFMT(info.external_attr >> 16)
            if mode not in (0, stat.S_IFREG) or info.file_size > MAX_RECEIPT:
                raise ValueError('invalid receipt archive entry')
            with archive.open(info) as stream:
                payload = stream.read(MAX_RECEIPT + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError('invalid receipt archive') from error
    if len(payload) > MAX_RECEIPT:
        raise ValueError('receipt exceeds byte limit')
    return _json(payload)


def _api_list(request, path, field):
    data = _json(request(path))
    rows = data.get(field) if isinstance(data, dict) else None
    if not isinstance(rows, list) or data.get('total_count') != len(rows) or (
            any(not isinstance(row, dict) for row in rows)):
        raise ValueError('incomplete GitHub ' + field + ' list')
    return data


def _download(request, run_path, identity, shard):
    name = f"kdd-postinit-shard-{identity['run_id']}-{identity['run_attempt']}-{shard}"
    rows = _api_list(request, f'{run_path}/artifacts?name={name}&per_page=100', 'artifacts')['artifacts']
    if not rows:
        raise Pending('waiting for post-init artifact ' + name)
    if len(rows) != 1:
        raise ValueError('ambiguous post-init artifact ' + name)
    row = rows[0]
    artifact = row.get('id')
    if row.get('name') != name or row.get('expired') is not False or (
            type(artifact) is not int or artifact <= 0 or row.get('size_in_bytes', 0) > MAX_RECEIPT * 2):
        raise ValueError('invalid post-init artifact ' + name)
    raw = request(f'repos/{REPOSITORY}/actions/artifacts/{artifact}/zip')
    if row.get('digest') != 'sha256:' + hashlib.sha256(raw).hexdigest():
        raise ValueError('post-init artifact digest mismatch')
    return read_receipt_archive(raw)


def _git(root, *arguments):
    return subprocess.check_output(['git', '--no-replace-objects', *arguments], cwd=root,
                                   env=_child_env(), timeout=30)


def _initialized_inventory(root, identity):
    if _git(root, 'rev-parse', 'HEAD^{tree}').decode().strip() != identity['tree'] or (
            _git(root, 'rev-parse', 'HEAD').decode().strip() != identity['head_sha']):
        raise ValueError('independent inventory checkout identity mismatch')
    with tempfile.TemporaryDirectory(prefix='kdd-postinit-inventory-') as directory:
        snapshot = Path(directory)
        raw = _git(root, 'archive', '--format=zip', identity['head_sha'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            archive.extractall(snapshot)
        command = [sys.executable, '-X', 'utf8', str(snapshot / 'scripts/init_project.py'),
                   '--repo-dir', str(snapshot), '--apply', '--repository', 'ExampleCo/Shop']
        subprocess.run(command, cwd=snapshot, env=_child_env(), check=True, timeout=45,
                       stdout=subprocess.DEVNULL)
        (snapshot / 'tests/test_init_project.py').unlink()
        return discover(snapshot)


def collect(root, identity, request):
    root = Path(root).resolve(strict=True)
    path = f"repos/{REPOSITORY}/actions/runs/{identity['run_id']}"
    jobs = _api_list(request, f"{path}/attempts/{identity['run_attempt']}/jobs?per_page=100", 'jobs')
    for job in _jobs(jobs):
        _interval(job, identity)
    receipts = [_download(request, path, identity, shard) for shard in (0, 1)]
    expected = _initialized_inventory(root, identity)
    return verify(receipts, jobs, expected, identity)


def _identity(root):
    data = {key: os.environ[name] for key, name in (
        ('run_id', 'GITHUB_RUN_ID'), ('run_attempt', 'GITHUB_RUN_ATTEMPT'),
        ('head_sha', 'GITHUB_SHA'), ('runtime_ref', 'KDD_TRUSTED_RUNTIME_REF'))}
    if any(not re.fullmatch(r'[1-9][0-9]{0,19}', data[key]) for key in ('run_id', 'run_attempt')) or (
            any(not re.fullmatch(r'[0-9a-f]{40}', data[key]) for key in ('head_sha', 'runtime_ref'))):
        raise ValueError('invalid GitHub run or runtime identity')
    if _git(root, 'rev-parse', 'HEAD').decode().strip() != data['head_sha']:
        raise ValueError('checkout does not match GitHub SHA')
    data['tree'] = _git(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    data['jobs_head_sha'] = data['head_sha']
    if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
        event = _json(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
        data['jobs_head_sha'] = event['pull_request']['head']['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', data['jobs_head_sha']):
            raise ValueError('invalid GitHub PR head identity')
    return data


def _run_shard(root, shard, destination):
    if os.path.lexists(destination):
        raise ValueError('receipt destination already exists')
    identity = _identity(root)
    runner = _load(Path(os.environ['KDD_TRUSTED_BUNDLE']) / 'process_tree.py')
    with tempfile.TemporaryDirectory(prefix='kdd-postinit-shard-report-') as directory:
        path = Path(directory) / 'suite.json'
        environment = dict(_child_env(), KDD_POSTINIT_SHARD=str(shard),
                           KDD_POSTINIT_RAW_REPORT=str(path))
        environment.pop('KDD_SKIP_INIT_POST_APPLY_SUITE', None)
        try:
            result = runner.run([sys.executable, '-X', 'utf8', '-m', 'unittest', OUTER_TEST],
                                cwd=root, timeout=TIMEOUT, env=environment)
        except subprocess.TimeoutExpired:
            print('post-init shard timed out after 600 seconds', file=sys.stderr)
            return 124
        if result.returncode:
            return result.returncode
        if not path.is_file():
            raise ValueError('successful init fixture produced no suite report')
        report = _json(path.read_bytes())
    metadata = report['postinit_partition']
    expected = _canonical_inventory(metadata['inventory'])
    if metadata['shard'] != shard:
        raise ValueError('unexpected report shard')
    errors = _load(root / 'scripts/run_test_suite.py').validate_report(expected[shard], report)
    if errors:
        raise ValueError('invalid suite report: ' + '; '.join(errors))
    receipt = {key: identity[key] for key in IDENTITY_FIELDS}
    receipt.update({key: report[key] for key in REPORT_FIELDS}, schema_version=1, shard=shard,
                   inventory=expected)
    _receipt(receipt, expected, identity)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write(destination, receipt, MAX_RECEIPT)
    return 0


def _request(path):
    return subprocess.check_output(['gh', 'api', path], timeout=25)


def _collect_cli(root):
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or not os.environ.get('GH_TOKEN'):
        raise ValueError('collection requires the repository CI read token')
    identity = _identity(root)
    deadline = time.monotonic() + 180
    while True:
        try:
            verdict = collect(root, identity, _request)
            print('KDD_POSTINIT_WINDOW ' + json.dumps(dict(verdict, **identity), sort_keys=True))
            return 0
        except Pending:
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('inventory', 'suite', 'run', 'collect'):
        command = commands.add_parser(name)
        command.add_argument('--repo-root', required=True, type=Path)
        if name in ('suite', 'run'):
            command.add_argument('--shard', type=int, choices=(0, 1), required=True)
        if name in ('inventory', 'suite', 'run'):
            command.add_argument('--receipt' if name == 'run' else '--report-json',
                                 required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.repo_root.resolve(strict=True)
        if args.command == 'inventory':
            runner = _load(root / 'scripts/run_test_suite.py')
            _write(args.report_json, _expected(_partition(root, runner)))
            return 0
        if args.command == 'suite':
            return _suite(root, args.shard, args.report_json)
        if args.command == 'run':
            return _run_shard(root, args.shard, args.receipt)
        return _collect_cli(root)
    except (OSError, ValueError, LookupError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print('POSTINIT_PARTITIONS: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
