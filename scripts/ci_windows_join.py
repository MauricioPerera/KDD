"""Project and join the immutable evidence from the native Windows CI jobs."""

import sys

if __name__ == '__main__' and not sys.flags.isolated:
    raise SystemExit('Windows validation evidence requires python -I.')

import argparse
from collections import defaultdict
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import runpy
import stat
import subprocess
import tempfile
import zipfile


MIB = 1024 * 1024
IDENTITY = {'repository': 'MauricioPerera/KDD', 'workflow': '.github/workflows/validate.yml',
            'platform': 'windows-latest'}
RUNTIME_FILES = {'trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
                 'validate_contracts.py', 'process_tree.py', 'execution_profile.py'}
MANAGED_FILES = {'oracle_execution.py', 'oracle_inventory.py', 'unittest_oracle_runner.py',
                 'node_oracle_reporter.mjs'}
CONTRACT_FIELDS = ('path', 'test_command', 'scope', 'shared_from', 'ok', 'exit_code')
PASS_METADATA = ('number', 'runtime', 'workers', 'ok', 'errors', 'failures',
                 'fixture_omitted_ids', 'coverage')
LEGACY_PASS_FIELDS = {*PASS_METADATA, 'expected_ids', 'executed_ids'}
COMPACT_PASS_FIELDS = {*PASS_METADATA, 'expected_ids_sha256', 'executed_ids_sha256'}
TIMING_FIELDS = {'schema_version', 'kind', 'identity', 'complete', 'missing', 'sources'}


class EvidenceError(ValueError):
    """A rejection with a message independent of evidence contents."""


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _hex(value, size):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(size) + '}', value) is not None


def _integer(value, minimum=1):
    return type(value) is int and value >= minimum


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('invalid JSON constant')


def _json(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_constant)


def _metadata(path):
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and
             not getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
             'expected a regular evidence file')
    return info


def _read(path, limit):
    _metadata(path)
    with path.open('rb') as handle:
        raw = handle.read(limit + 1)
    _require(len(raw) <= limit, 'evidence exceeds byte limit')
    return raw


def _archive(path, digest, member):
    compressed, limit = (8 * MIB, 16 * MIB) if member == 'coverage.json' else (2 * MIB, MIB)
    raw = _read(path, compressed)
    _require(_digest(raw) == digest, 'archive digest does not match its producer')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        _require(len(entries) == 1, 'unexpected archive member count')
        info = entries[0]
        _require(info.orig_filename == member and info.file_size <= limit
                 and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
                 and not info.external_attr & stat.FILE_ATTRIBUTE_REPARSE_POINT,
                 'invalid archive member')
        with archive.open(info) as handle:
            payload = handle.read(limit + 1)
    _require(len(payload) <= limit, 'archive member exceeds byte limit')
    return payload


def _git(root, *args, data=None):
    return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=root, input=data,
                                   stderr=subprocess.PIPE, timeout=30)


def _identity(root, value):
    fields = {*IDENTITY, 'run_id', 'run_attempt', 'head_sha', 'tree', 'runtime_ref'}
    _require(set(value) == fields and all(value[k] == v for k, v in IDENTITY.items()),
             'wrong receipt origin')
    _require(all(_integer(value[k]) for k in ('run_id', 'run_attempt'))
             and all(_hex(value[k], 40) for k in ('head_sha', 'tree', 'runtime_ref')),
             'invalid receipt identity')
    head, tree = _git(root, 'rev-parse', 'HEAD', 'HEAD^{tree}').decode('ascii').splitlines()
    _require((head, tree) == (value['head_sha'], value['tree']), 'checkout does not match receipt')


def _producers(value):
    _require(set(value) == {'contracts', 'suites', 'coverage'}, 'wrong producer set')
    ids = set()
    for item in value.values():
        _require(set(item) == {'id', 'digest', 'result'} and _integer(item['id'])
                 and _hex(item['digest'], 64) and item['result'] == 'success', 'invalid producer')
        ids.add(item['id'])
    _require(len(ids) == len(value), 'producer IDs must be distinct')


def _receipt(payload, role, identity):
    value = _json(payload)
    field = 'rows' if role == 'contracts' else 'passes'
    expected = {'schema_version', 'role', 'identity', 'ok', field}
    version = value['schema_version']
    _require(type(version) is int and (version == 1 or (version == 2 and role == 'suites'))
             and value['ok'] is True and value['role'] == role and value['identity'] == identity,
             'stale or mismatched receipt')
    if version == 2:
        _require(set(value) == expected | {'inventory', 'timing'}, 'unexpected receipt fields')
        _compact_suite_timing(value['timing'], identity)
    else:
        _require(set(value).difference({'timing'}) == expected, 'unexpected receipt fields')
    _require(type(value['identity']['run_id']) is int and type(value['identity']['run_attempt']) is int,
             'receipt run identifiers must be integers')
    return value


def _entries(root, revision, directory, allowed):
    entries = _git(root, 'ls-tree', '-z', revision + ':' + directory)
    found = {}
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        metadata, raw_name = entry.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if not allowed(name):
            continue
        mode, kind, oid = metadata.decode('ascii').split()
        _require(kind == 'blob' and mode in ('100644', '100755') and not set(name).intersection('\\:'),
                 'nonregular file in reviewed Git inputs')
        found[name] = oid
    return found


def _copy_git_blobs(root, entries, destination):
    """Use one Git process for the inventory's content as well as its paths."""
    names = defaultdict(list)
    for name, oid in entries.items():
        names[oid].append(name)
    data = ''.join(oid + '\n' for oid in names).encode('ascii')
    with io.BytesIO(_git(root, 'cat-file', '--batch', data=data)) as stream:
        for oid, paths in names.items():
            found, kind, length = stream.readline().decode('ascii').split()
            _require(found == oid and kind == 'blob', 'unexpected Git object')
            raw = stream.read(int(length))
            _require(len(raw) == int(length) and stream.read(1) == b'\n', 'truncated Git object')
            for name in paths:
                (destination / name).write_bytes(raw)
        _require(not stream.read(1), 'unexpected trailing Git objects')


def _runtime_copy(root, bundle, runtime, destination):
    bundle = bundle.resolve(strict=True)
    _require(not bundle.is_relative_to(root), 'runtime bundle must be external')
    manifest = _json(_read(bundle / 'manifest.json', MIB))
    files = manifest['files']
    _require(manifest['version'] == 1 and manifest['trusted_ref'] == runtime
             and set(files) in (RUNTIME_FILES, RUNTIME_FILES | MANAGED_FILES),
             'unexpected runtime manifest')
    _require(_git(root, 'cat-file', '-t', runtime).strip() == b'commit', 'runtime must be a commit')
    entries = _entries(root, runtime, 'scripts', files.__contains__)
    _require(set(entries) == set(files), 'missing runtime from reviewed commit')
    _copy_git_blobs(root, entries, destination)
    for name, checksum in files.items():
        raw = _read(bundle / name, MIB)
        _require(_digest(raw) == checksum and raw == (destination / name).read_bytes(),
                 'runtime bundle differs from the reviewed Git object')


def _contract_plan(args, identity):
    root = args.repo_root
    with tempfile.TemporaryDirectory(prefix='kdd-windows-plan-') as directory:
        scratch = Path(directory)
        runtime, snapshot = scratch / 'runtime', scratch / 'contracts'
        runtime.mkdir()
        snapshot.mkdir()
        _runtime_copy(root, args.runtime_bundle, identity['runtime_ref'], runtime)
        entries = _entries(root, identity['head_sha'], 'knowledge/contracts',
                           lambda name: name.endswith('.md') and not name.startswith('TEMPLATE-'))
        _copy_git_blobs(root, entries, snapshot)
        sys.path.insert(0, str(runtime))
        try:
            return _collect(snapshot)
        finally:
            sys.path.pop(0)


def _collect(directory):
    import validate_test_commands as gate

    rows = []
    representatives = {}
    for index, item in enumerate(gate.collect_contracts(str(directory))):
        path = 'knowledge/contracts/' + Path(item['path']).name
        command = item['test_command']
        key = gate._item_key(item, index, True) if hasattr(gate, '_item_key') else command
        representative = representatives.setdefault(key, path)
        rows.append(dict(path=path, test_command=command, scope=item['scope'],
                         shared_from=None if representative == path else representative,
                         ok=True, exit_code=0))
    return rows


def _coverage(payload, identity):
    data = _json(payload)
    meta, totals = data['kdd'], data['totals']
    expected = dict(head_sha=identity['head_sha'], platform=identity['platform'],
                    run_id=str(identity['run_id']), attempt=str(identity['run_attempt']), suite_pass=1)
    _require(all(meta[key] == value for key, value in expected.items())
             and type(meta['suite_pass']) is int, 'coverage belongs to another run, attempt or pass')
    fragments, lines, branches = meta['fragments'], totals['num_statements'], totals['num_branches']
    _require(all(map(_integer, (fragments, lines, branches))), 'invalid coverage summary')
    return dict(pass_no=1, sha256=_digest(payload), fragments=fragments,
                lines_total=lines, branches_total=branches)


def _inventory(value):
    _require(isinstance(value, list) and value and all(
        isinstance(case, str) and case and not set(case).intersection('\r\n\0') for case in value),
        'invalid suite inventory')
    _require(len(set(value)) == len(value), 'duplicate suite IDs')
    return _digest(('\n'.join(sorted(value)) + '\n').encode('utf-8'))


def _check_pass(value, number, runtime, inventory, coverage):
    _require(_integer(value['number']) and value['number'] == number and value['runtime'] == runtime
             and value['workers'] == 6 and type(value['workers']) is int
             and value['ok'] is True and value['fixture_omitted_ids'] == [],
             'invalid suite pass identity or outcome')
    _require(all(_integer(value[k], 0) and value[k] == 0 for k in ('errors', 'failures')),
             'suite reported failures')
    if 'expected_ids' in value:
        expected = _inventory(value['expected_ids'])
        executed = _inventory(value['executed_ids'])
    else:
        expected, executed = value['expected_ids_sha256'], value['executed_ids_sha256']
    _require(expected == executed == inventory, 'suite inventory differs from the required inventory')
    actual = value['coverage']
    _require(actual == coverage and (coverage is None or all(
        type(actual[key]) is type(coverage[key]) for key in coverage)),
        'coverage is missing, misplaced or inconsistent')


def _check_suite_passes(suites, runtime, discovery, coverage):
    rows = suites['passes']
    _require(_hex(discovery, 64) and isinstance(rows, list) and len(rows) == 2, 'missing suite passes')
    compact = suites['schema_version'] == 2
    if compact:
        inventory = suites['inventory']
        _require(_inventory(inventory) == discovery and inventory == sorted(inventory),
                 'suite inventory differs from independent discovery or is not sorted')
    fields = COMPACT_PASS_FIELDS if compact else LEGACY_PASS_FIELDS
    for number, row in enumerate(rows, 1):
        _require(isinstance(row, dict) and set(row) == fields, 'invalid suite pass fields')
        _check_pass(row, number, runtime, discovery, coverage if number == 1 else None)
    return [len(inventory)] * len(rows) if compact else [len(row['expected_ids']) for row in rows]


def _path(root, value):
    return Path(value).resolve(strict=True).relative_to(root).as_posix()


def _project_rows(rows, root):
    result = []
    for row in rows:
        _require(row['ok'] is True and type(row['exit_code']) is int
                 and row['exit_code'] == 0 and row.get('error') is None, 'contract reported failure')
        projected = {key: row[key] for key in CONTRACT_FIELDS}
        projected['path'] = _path(root, row['path'])
        if row['shared_from'] is not None:
            projected['shared_from'] = _path(root, row['shared_from'])
        result.append(projected)
    return result


def _reports(path, count):
    files = list(path.glob('evidence-*.json'))
    _require(len(files) == count, 'unexpected number of fresh reports')
    if count == 2:
        # The trusted launcher reserves unique files before each consecutive pass.
        order = [
            (_metadata(item).st_ctime_ns if os.name == 'nt' else _metadata(item).st_mtime_ns, item)
            for item in files
        ]
        _require(order[0][0] != order[1][0], 'ambiguous suite pass order')
        files = [item for _, item in sorted(order)]
    return [_json(_read(item, 16 * MIB)) for item in files]


def _suite_row(data, number, coverage):
    return dict(number=number, runtime=data['trusted_runtime_ref'], workers=data['workers'],
                expected_ids_sha256=_inventory(data['expected_ids']),
                executed_ids_sha256=_inventory(data['executed_ids']), ok=data['ok'],
                errors=len(data['errors']), failures=len(data['failures']),
                fixture_omitted_ids=data['fixture_omitted_ids'], coverage=coverage)


def _project_suites(reports, runtime, coverage):
    passes = [_suite_row(report, number, coverage if number == 1 else None)
              for number, report in enumerate(reports, 1)]
    expected = passes[0]['expected_ids_sha256']
    for number, row in enumerate(passes, 1):
        _check_pass(row, number, runtime, expected, coverage if number == 1 else None)
    return dict(schema_version=2, inventory=sorted(reports[0]['expected_ids']), passes=passes)


def _timing_identity(identity):
    return dict(run_id=identity['run_id'], run_attempt=identity['run_attempt'],
                head_sha=identity['head_sha'], trusted_runtime_ref=identity['runtime_ref'],
                platform=identity['platform'])


def _timing_projection(root, temp, identity):
    projector = runpy.run_path(str(root / 'scripts/ci_timings.py'))['_projection']
    return projector(argparse.Namespace(
        repo_root=str(root), commands_dir=str(temp / 'kdd-command-reports'),
        suites_dir=str(temp / 'kdd-suite-reports'), run_id=str(identity['run_id']),
        run_attempt=str(identity['run_attempt']), head_sha=identity['head_sha'],
        platform=identity['platform'], trusted_runtime_ref=identity['runtime_ref']))


def _duration(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _check_command_timings(rows, contract_rows):
    paths = {row['path']: row for row in contract_rows}
    _require(len(rows) == len(paths), 'incomplete command diagnostics')
    for row in rows:
        expected = paths.pop(row['contract'])
        _require(set(row) == {'contract', 'scope', 'duration_seconds', 'exit_code', 'recorded_ok', 'shared_from'}
                 and row['scope'] == expected['scope'] and row['shared_from'] == expected['shared_from']
                 and row['recorded_ok'] is True and type(row['exit_code']) is int and row['exit_code'] == 0
                 and _duration(row['duration_seconds']), 'invalid command diagnostic row')


def _check_suite_timings(rows):
    for row in rows:
        module = row['module']
        _require(set(row) == {'module', 'duration_seconds', 'tests_run', 'exit_code'}
                 and (module == 'controller diagnostics' or all(part.isidentifier() for part in module.split('.')))
                 and _duration(row['duration_seconds']) and _integer(row['tests_run'], 0)
                 and (row['exit_code'] is None or type(row['exit_code']) is int),
                 'invalid suite diagnostic row')


def _check_timing_source(source, contracts):
    _require(set(source) == {'kind', 'source_sha256', 'recorded_ok', 'duration_seconds', 'rows'}
             and _hex(source['source_sha256'], 64) and source['recorded_ok'] is True
             and isinstance(source['rows'], list), 'invalid diagnostic source')
    if source['kind'] == 'commands':
        _require(source['duration_seconds'] is None, 'unexpected command diagnostic duration')
        _check_command_timings(source['rows'], contracts)
    else:
        _require(_duration(source['duration_seconds']), 'invalid suite diagnostic duration')
        _check_suite_timings(source['rows'])


def _compact_suite_timing(timing, identity):
    _require(isinstance(timing, dict) and set(timing) == TIMING_FIELDS
             and type(timing['schema_version']) is int and timing['schema_version'] == 1
             and timing['kind'] == 'kdd-ci-timings' and timing['identity'] == _timing_identity(identity)
             and timing['complete'] is False and timing['missing'] == ['commands-report'],
             'unexpected diagnostics metadata in the compact suites receipt')
    sources = timing['sources']
    _require(isinstance(sources, list) and len(sources) == 2
             and all(isinstance(source, dict) and source.get('kind') == 'suite' for source in sources),
             'unexpected diagnostics sources in the compact suites receipt')
    for source in sources:
        _check_timing_source(source, ())
    _require(len({source['source_sha256'] for source in sources}) == 2, 'repeated diagnostic sources')


def _publish(path, value, limit=None):
    raw = json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8') + b'\n'
    _require(limit is None or len(raw) <= limit, 'projected evidence exceeds byte limit')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(raw)


def _join_timings(output, contracts, suites, identity):
    sources = []
    for receipt, expected in ((contracts, ['commands']), (suites, ['suite', 'suite'])):
        timing = receipt['timing']
        _require(timing['identity'] == _timing_identity(identity)
                 and timing['schema_version'] == 1 and timing['kind'] == 'kdd-ci-timings',
                 'mismatched diagnostic identity')
        actual = timing['sources']
        _require([source['kind'] for source in actual] == expected, 'wrong timing source role')
        for source in actual:
            _check_timing_source(source, contracts['rows'])
        sources.extend(actual)
    _require(len({source['source_sha256'] for source in sources}) == 3, 'repeated diagnostic sources')
    sorted_sources = [sources[0], *sorted(sources[1:], key=lambda source: source['source_sha256'])]
    _publish(output, dict(schema_version=1, kind='kdd-ci-timings', identity=_timing_identity(identity),
                          complete=True, missing=[], sources=sorted_sources))


def _verify(args):
    identity = _json(_read(args.identity, MIB))
    _identity(args.repo_root, identity)
    producers = _json(_read(args.producers, MIB))
    _producers(producers)
    coverage = _coverage(_archive(args.coverage, producers['coverage']['digest'], 'coverage.json'), identity)
    contracts = _receipt(_archive(args.contracts, producers['contracts']['digest'], 'receipt.json'),
                         'contracts', identity)
    suites = _receipt(_archive(args.suites, producers['suites']['digest'], 'receipt.json'), 'suites', identity)
    rows, expected = contracts['rows'], _contract_plan(args, identity)
    _require(expected and rows == expected and all(
        row['ok'] is True and type(row['exit_code']) is int for row in rows), 'contract plan differs from the receipt')
    passes = _check_suite_passes(suites, identity['runtime_ref'], args.suite_inventory_sha256, coverage)
    if args.timings_output is not None:
        _join_timings(args.timings_output, contracts, suites, identity)
    print(json.dumps(dict(ok=True, contracts=len(rows), passes=passes,
                          suite_inventory_sha256=args.suite_inventory_sha256,
                          coverage_sha256=coverage['sha256'])))


def _produce(args):
    env, root = os.environ, args.repo_root
    temp = Path(env['RUNNER_TEMP']).resolve(strict=True)
    _require(not temp.is_relative_to(root), 'receipt directory must be external')
    head = env['GITHUB_SHA']
    identity = dict(IDENTITY, repository=env['GITHUB_REPOSITORY'], run_id=int(env['GITHUB_RUN_ID']),
                    run_attempt=int(env['GITHUB_RUN_ATTEMPT']), head_sha=head,
                    tree=_git(root, 'rev-parse', 'HEAD^{tree}').decode('ascii').strip(),
                    runtime_ref=env['KDD_TRUSTED_RUNTIME_REF'])
    _identity(root, identity)
    data = dict(schema_version=1, role=args.role, identity=identity, ok=True)
    if args.role == 'contracts':
        report, = _reports(temp / 'kdd-command-reports', 1)
        _require(report['ok'] is True and report['trusted_runtime_ref'] == identity['runtime_ref'],
                 'untrusted contract report')
        data['rows'] = _project_rows(report['results'], root)
    else:
        source = temp / f"kdd-python-coverage-{identity['run_id']}-{identity['run_attempt']}" / 'coverage.json'
        coverage = _coverage(_read(source, 16 * MIB), identity)
        reports = _reports(temp / 'kdd-suite-reports', 2)
        data.update(_project_suites(reports, identity['runtime_ref'], coverage))
    data['timing'] = _timing_projection(root, temp, identity)
    if args.role == 'suites':
        _compact_suite_timing(data['timing'], identity)
    _publish(temp / 'kdd-windows-receipts' / 'receipt.json', data, MIB)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    verify, produce = commands.add_parser('verify'), commands.add_parser('produce')
    for command in (verify, produce):
        command.add_argument('--repo-root', type=Path, required=True)
    for flag in ('runtime-bundle', 'identity', 'producers', 'contracts', 'suites', 'coverage'):
        verify.add_argument('--' + flag, type=Path, required=True)
    verify.add_argument('--suite-inventory-sha256', required=True)
    verify.add_argument('--timings-output', type=Path)
    produce.add_argument('--role', choices=('contracts', 'suites'), required=True)
    args = parser.parse_args(argv)
    try:
        args.repo_root = args.repo_root.resolve(strict=True)
        {'verify': _verify, 'produce': _produce}[args.command](args)
    except EvidenceError as error:
        print(f'Windows validation evidence rejected: {error}.', file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, OverflowError,
            RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print(f'Windows validation evidence rejected ({type(error).__name__}).', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
