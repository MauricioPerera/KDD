"""Complete unittest discovery with bounded processes and reconciled case IDs."""
import sys

# Only built-in/frozen modules may precede the isolated re-exec. In particular,
# scripts/argparse.py must not run before the supervisor even exists.
if __name__ == '__main__' and not sys.flags.isolated:
    import os
    # Windows CRT execv does not quote argv paths containing spaces. Import the
    # stdlib launcher from a restricted path and let CreateProcess quote argv.
    _stdlib = os.path.dirname(os.__file__)
    sys.path[:] = [_stdlib, os.path.join(_stdlib, 'lib-dynload'),
                   os.path.join(_stdlib, os.pardir, 'DLLs')]
    import subprocess as _bootstrap_process
    raise SystemExit(_bootstrap_process.call(
        [sys.executable, '-I', '-X', 'utf8', __file__, *sys.argv[1:]]))

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.util
import json
import locale
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest

_process_spec = importlib.util.spec_from_file_location(
    '_kdd_suite_process_tree', Path(__file__).resolve().with_name('process_tree.py'))
_process_module = importlib.util.module_from_spec(_process_spec)
_process_spec.loader.exec_module(_process_module)
run_process = _process_module.run


OUTCOMES = ('skipped', 'failures', 'errors', 'expected_failures', 'unexpected_successes')


def _workers(value):
    if type(value) is not int or not 1 <= value <= 8:
        raise ValueError('workers must be an integer between 1 and 8')
    return value


def _cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _cases(item)
        else:
            yield item


def _empty(ids, inventory=None):
    return dict(version=1, ok=False, tests_run=0, expected_ids=sorted(ids),
                executed_ids=[], fixture_omitted_ids=[], fixture_outcomes=[],
                inventory=inventory or [], modules=[], **{name: [] for name in OUTCOMES})


class DiscoveryLoader(unittest.TestLoader):
    """Retain the origin of suites, including FunctionTestCase/load_tests."""
    def __init__(self):
        super().__init__()
        self.origins = {}

    def loadTestsFromModule(self, module, *args, **kwargs):
        suite = super().loadTestsFromModule(module, *args, **kwargs)
        for case in _cases(suite):
            if hasattr(module, 'load_tests') or id(case) not in self.origins:
                self.origins[id(case)] = module.__name__
        return suite


def _inventory(cases, loader):
    result = []
    for case in cases:
        cls = type(case)
        import_skip = cls.__module__ == 'unittest.loader' and cls.__name__ == 'ModuleSkipped'
        origin = (case._testMethodName if import_skip else
                  loader.origins.get(id(case), cls.__module__))
        result.append(dict(id=case.id(), origin=origin, module=cls.__module__,
                           class_name=cls.__module__ + '.' + cls.__qualname__, import_skip=import_skip))
    return result


def _fixture_scope(identity):
    match = re.fullmatch(r'(setUpClass|tearDownClass|setUpModule|tearDownModule|import) \((.+)\)', identity)
    if not match:
        return None, None
    hook, target = match.groups()
    return ('import' if hook == 'import' else 'class' if hook.endswith('Class') else 'module'), target


def _fixture_members(fixture, inventory):
    scope, target = _fixture_scope(fixture.get('id', ''))
    if scope != fixture.get('scope'):
        return None
    key = {'class': 'class_name', 'module': 'module', 'import': 'origin'}.get(scope)
    if key is None:
        return None
    return {item['id'] for item in inventory if item.get(key) == target
            and (scope != 'import' or item.get('import_skip') is True)}


def _validate_fixtures(expected_ids, report, executed):
    inventory = report.get('inventory')
    outcomes, omitted = report.get('fixture_outcomes'), report.get('fixture_omitted_ids')
    if (not isinstance(inventory, list) or not isinstance(outcomes, list) or
            not isinstance(omitted, list) or any(not isinstance(x, str) for x in omitted)):
        return ['invalid fixture accounting']
    if any(not isinstance(x, dict) or any(not isinstance(x.get(k), str)
           for k in ('id', 'origin', 'module', 'class_name')) for x in inventory):
        return ['invalid discovery metadata']
    problems = []
    if Counter(x['id'] for x in inventory) != Counter(expected_ids):
        problems.append('incomplete or foreign discovery metadata')
    covered = []
    for fixture in outcomes:
        if not isinstance(fixture, dict):
            problems.append('invalid fixture outcome')
            continue
        affected = fixture.get('affected_ids')
        members = _fixture_members(fixture, inventory)
        if (members is None or not members or not isinstance(affected, list) or
                any(not isinstance(x, str) for x in affected)):
            problems.append('invalid fixture scope')
            continue
        if not set(affected) <= members or set(affected) & set(executed):
            problems.append('foreign or executed fixture omission')
        if fixture.get('status') == 'skipped':
            if not isinstance(fixture.get('reason'), str):
                problems.append('missing fixture skip reason')
        elif fixture.get('status') == 'error':
            if report.get('ok') or not isinstance(fixture.get('traceback'), str):
                problems.append('invalid fixture error')
        else:
            problems.append('invalid fixture status')
        covered.extend(affected)
    if (omitted != sorted(set(omitted)) or Counter(covered) != Counter(omitted)
            or len(covered) != len(set(covered))):
        problems.append('unbacked or duplicate fixture omissions')
    return problems


def _problem(report, message, identity='runner'):
    report['ok'] = False
    report['errors'].append({'id': identity, 'traceback': str(message), 'infrastructure': True})


def validate_report(expected_ids, report) -> list:
    """Validate coverage independently of stdout and of a reported success flag."""
    if not isinstance(report, dict):
        return ['report is not an object']
    problems = []
    if type(report.get('version')) is not int or report['version'] != 1:
        problems.append('unsupported report version')
    if type(report.get('ok')) is not bool:
        problems.append('invalid success flag')
    for name in ('expected_ids', 'executed_ids'):
        values = report.get(name)
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            problems.append('invalid ' + name)
            continue
        if len(values) != len(set(values)):
            problems.append('duplicate ' + name)
        omitted = report.get('fixture_omitted_ids', []) if name == 'executed_ids' else []
        if not isinstance(omitted, list) or any(not isinstance(x, str) for x in omitted):
            omitted = []
        if (values != sorted(values) or Counter(values + omitted) != Counter(expected_ids)
                or set(values) & set(omitted)):
            problems.append('incomplete or foreign ' + name)
    count = report.get('tests_run')
    executed = report.get('executed_ids')
    if (type(count) is not int or count < 0 or not isinstance(executed, list)
            or count != len(executed)):
        problems.append('incorrect executed count')
    problems.extend(_validate_fixtures(expected_ids, report,
                                       executed if isinstance(executed, list) else []))
    for name in OUTCOMES:
        values = report.get(name)
        if not isinstance(values, list):
            problems.append('invalid ' + name)
            continue
        for value in values:
            infrastructure = (isinstance(value, dict) and name == 'errors'
                              and value.get('infrastructure') is True and report.get('ok') is False)
            if not isinstance(value, dict) or (value.get('id') not in expected_ids and not infrastructure):
                problems.append('foreign or invalid outcome in ' + name)
            elif name == 'skipped' and not isinstance(value.get('reason'), str):
                problems.append('missing skip reason')
    if report.get('ok') and any(report.get(name) for name in ('failures', 'errors', 'unexpected_successes')):
        problems.append('success contradicts outcomes')
    return problems


def _reconcile(ids, report, identity='runner'):
    problems = validate_report(ids, report)
    usable = (isinstance(report, dict) and type(report.get('tests_run')) is int
               and all(isinstance(report.get(k), list) for k in
                       (*OUTCOMES, 'executed_ids', 'expected_ids', 'modules',
                        'fixture_omitted_ids', 'fixture_outcomes', 'inventory'))
              and all(isinstance(x, str) for x in report['executed_ids'])
              and all(isinstance(x, dict) and isinstance(x.get('id'), str)
                      for k in OUTCOMES for x in report[k]))
    if not usable:
        report = _empty(ids)
    for problem in problems:
        _problem(report, problem, identity)
    return report


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_ids = []

    def startTest(self, test):
        self.executed_ids.append(test.id())
        super().startTest(test)


def _outcome(test, **details):
    # A skipped/failed subtest belongs to its executed parent case.
    parent = getattr(test, 'test_case', test)
    entry = {'id': parent.id(), **details}
    if parent is not test:
        entry['subtest'] = test.id()
    return entry


def _execute(suite, ids, inventory):
    started = time.perf_counter()
    result = unittest.TextTestRunner(resultclass=RecordingResult).run(suite)
    report = _empty(ids, inventory)
    report.update(ok=result.wasSuccessful(), tests_run=result.testsRun,
                  executed_ids=sorted(result.executed_ids), pid=os.getpid(),
                  duration_seconds=time.perf_counter() - started,
                  stdout_encoding=sys.stdout.encoding, stderr_encoding=sys.stderr.encoding)
    def outcome(test, status, **details):
        identity = test.id()
        entry = next((item for item in inventory if item['id'] == identity), None)
        if entry is not None and not entry['import_skip']:
            return _outcome(test, **details)
        fixture_id = 'import (' + entry['origin'] + ')' if entry is not None else identity
        scope, _ = _fixture_scope(fixture_id)
        fixture = dict(id=fixture_id, scope=scope, status=status, affected_ids=[], **details)
        members = _fixture_members(fixture, inventory) or set()
        fixture['affected_ids'] = sorted(members - set(report['executed_ids'])
                                          - set(report['fixture_omitted_ids']))
        report['fixture_outcomes'].append(fixture)
        report['fixture_omitted_ids'].extend(fixture['affected_ids'])
        # unittest counts its synthetic import-skip case; retain that callback
        # and distinguish it from product execution with the discovery metadata.
        if entry is not None:
            return _outcome(test, **details)
        if status == 'error':
            return _outcome(test, infrastructure=True, **details)
        return None

    report['skipped'] = [entry for t, reason in result.skipped
                         if (entry := outcome(t, 'skipped', reason=reason)) is not None]
    for name in ('failures', 'errors', 'expected_failures'):
        source = result.expectedFailures if name == 'expected_failures' else getattr(result, name)
        report[name] = [entry for t, trace in source
                        if (entry := outcome(t, 'error', traceback=trace)) is not None]
    report['unexpected_successes'] = [_outcome(t) for t in result.unexpectedSuccesses]
    report['fixture_omitted_ids'].sort()
    return report


def _write(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')


def _worker(plan_path, report_path):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    sys.path.insert(0, str(Path.cwd()))
    sys.path.insert(0, plan['start_dir'])
    loader = DiscoveryLoader()
    try:
        module = importlib.import_module(plan['origin'])
        suite = loader.loadTestsFromModule(module, pattern=plan['pattern'])
    except unittest.SkipTest as exc:
        if not all(item['import_skip'] for item in plan['inventory']):
            raise
        reason = str(exc)
        class ImportedSkip(unittest.TestCase):
            def id(self):
                return plan['ids'][0]

            def runTest(self):
                raise unittest.SkipTest(reason)
        suite = unittest.TestSuite([ImportedSkip()])
    actual = [case.id() for case in _cases(suite)]
    if loader.errors or Counter(actual) != Counter(plan['ids']):
        report = _empty(plan['ids'], plan['inventory'])
        _problem(report, '\n'.join(loader.errors) or 'worker inventory mismatch')
    else:
        report = _execute(suite, plan['ids'], plan['inventory'])
        for error in validate_report(plan['ids'], report):
            _problem(report, error)
    _write(report_path, report)
    return 0 if report['ok'] else 1


def _run_worker(job, directory, index, start_dir, pattern):
    ids = job['ids']
    plan = Path(directory) / ('plan-' + str(index) + '.json')
    destination = Path(directory) / ('result-' + str(index) + '.json')
    _write(plan, {'ids': ids, 'start_dir': start_dir, 'pattern': pattern,
                  'origin': job['module'], 'inventory': job['inventory']})
    started = time.perf_counter()
    try:
        proc = run_process([sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()),
                            '--worker-plan', str(plan), '--worker-report', str(destination)],
                           cwd=Path.cwd(), capture_output=True, timeout=1800)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report = _empty(ids, job['inventory'])
        _problem(report, 'worker could not complete: ' + str(exc), job['module'])
        report['module_result'] = dict(module=job['module'], exit_code=1, tests_run=0,
                                      pid=None, duration_seconds=time.perf_counter() - started,
                                      stdout='', stderr=str(exc))
        return report
    try:
        report = json.loads(destination.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        report = _empty(ids, job['inventory'])
        _problem(report, 'worker report absent or corrupt', job['module'])
    report = _reconcile(ids, report, job['module'])
    if proc.returncode and (report['ok'] or proc.returncode != 1):
        _problem(report, 'worker exit code ' + str(proc.returncode), job['module'])
    outputs = {}
    for name in ('stdout', 'stderr'):
        encoding = report.get(name + '_encoding') or locale.getpreferredencoding(False)
        try:
            outputs[name] = getattr(proc, name).decode(encoding, errors='backslashreplace')
        except LookupError:
            outputs[name] = getattr(proc, name).decode('utf-8', errors='backslashreplace')
    report['module_result'] = dict(module=job['module'], exit_code=proc.returncode,
                                   tests_run=report['tests_run'], pid=report.get('pid'),
                                   duration_seconds=time.perf_counter() - started, **outputs)
    return report


def run_suite(start_dir, pattern="test_*.py", workers=1) -> dict:
    """Discover every case, execute it once, and reconcile actual case callbacks."""
    _workers(workers)
    started = time.perf_counter()
    sys.path.insert(0, str(Path.cwd()))
    start_dir = str(Path(start_dir).resolve())
    loader = DiscoveryLoader()
    try:
        suite = loader.discover(start_dir, pattern=pattern)
        cases = list(_cases(suite))
    except (ImportError, OSError, ValueError) as error:
        report = _empty([])
        _problem(report, error)
        report.update(workers=workers, duration_seconds=time.perf_counter() - started)
        return report
    ids = [case.id() for case in cases]
    inventory = _inventory(cases, loader)
    report = _empty(ids, inventory)
    if not ids or len(set(ids)) != len(ids) or loader.errors:
        _problem(report, '\n'.join(loader.errors) or 'empty or duplicate discovery inventory')
    elif workers == 1:
        report = _execute(suite, ids, inventory)
    else:
        jobs = {}
        for item in inventory:
            job = jobs.setdefault(item['origin'], {'module': item['origin'], 'ids': [], 'inventory': []})
            job['ids'].append(item['id'])
            job['inventory'].append(item)
        with tempfile.TemporaryDirectory(prefix='kdd-suite-') as directory:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_run_worker, job, directory, index, start_dir, pattern)
                           for index, job in enumerate(jobs.values())]
                reports = []
                for future in futures:
                    try:
                        reports.append(future.result())
                    except Exception as error:
                        _problem(report, 'worker infrastructure error: ' + str(error))
        report['ok'] = bool(reports) and not report['errors'] and all(r['ok'] for r in reports)
        for child in reports:
            report['tests_run'] += child['tests_run']
            report['executed_ids'].extend(child['executed_ids'])
            report['fixture_omitted_ids'].extend(child['fixture_omitted_ids'])
            report['fixture_outcomes'].extend(child['fixture_outcomes'])
            report['modules'].append(child['module_result'])
            for name in OUTCOMES:
                report[name].extend(child[name])
        report['executed_ids'].sort()
        report['fixture_omitted_ids'].sort()
    for error in validate_report(ids, report):
        _problem(report, error)
    report.update(workers=workers, duration_seconds=time.perf_counter() - started)
    return report


def _display(text):
    encoding = sys.stdout.encoding or 'utf-8'
    print(text.encode(encoding, errors='backslashreplace').decode(encoding))


def _supervise(args):
    """Keep discovery and serial test exits from bypassing the CLI verdict."""
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='kdd-suite-controller-') as directory:
        destination = Path(directory) / 'controller.json'
        try:
            proc = run_process([
                sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()),
                '--start-directory', args.start_directory, '--pattern', args.pattern,
                '--workers', str(args.workers), '--controller-report', str(destination)],
                cwd=Path.cwd(), capture_output=True, timeout=1800)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report = _empty([])
            _problem(report, 'suite controller could not complete: ' + str(exc))
            report.update(workers=args.workers, duration_seconds=time.perf_counter() - started)
            return report
        try:
            report = json.loads(destination.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            report = None
    ids = report.get('expected_ids') if isinstance(report, dict) else None
    if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
        report = _empty([])
        _problem(report, 'suite controller report absent or corrupt')
    else:
        report = _reconcile(ids, report)
    if proc.returncode and (report['ok'] or proc.returncode != 1):
        _problem(report, 'suite controller exit code ' + str(proc.returncode))
    if not report['expected_ids']:
        _problem(report, 'empty suite inventory')
    outputs = {}
    for stream in ('stdout', 'stderr'):
        encoding = report.get(stream + '_encoding') or locale.getpreferredencoding(False)
        try:
            outputs[stream] = getattr(proc, stream).decode(encoding, errors='backslashreplace')
        except LookupError:
            outputs[stream] = getattr(proc, stream).decode('utf-8', errors='backslashreplace')
    if any(outputs.values()):
        report['modules'].append(dict(module='controller diagnostics', exit_code=proc.returncode,
                                       tests_run=0, pid=None,
                                       duration_seconds=time.perf_counter() - started, **outputs))
    report.update(workers=args.workers, duration_seconds=time.perf_counter() - started)
    return report


def _summarize(report):
    for module in report['modules']:
        _display('MODULE {} tests={} exit={}'.format(module['module'], module['tests_run'], module['exit_code']))
        for stream in ('stdout', 'stderr'):
            if module[stream].strip():
                _display(module[stream].rstrip())
    # One short line per executed ID avoids truncating huge JSON log lines.
    for identity in report['executed_ids']:
        _display('KDD_CASE ' + json.dumps({'id': identity}, ensure_ascii=True))
    for fixture in report['fixture_outcomes']:
        _display('KDD_FIXTURE ' + json.dumps(fixture, ensure_ascii=True))
    digest = lambda ids: hashlib.sha256(('\n'.join(ids) + '\n').encode('utf-8')).hexdigest()
    summary = dict(version=1, ok=report['ok'], tests_run=report['tests_run'],
                   expected_count=len(report['expected_ids']), workers=report['workers'],
                   expected_ids_sha256=digest(report['expected_ids']),
                   executed_ids_sha256=digest(report['executed_ids']),
                   fixture_omitted_count=len(report['fixture_omitted_ids']),
                   fixture_skips=sum(f['status'] == 'skipped' for f in report['fixture_outcomes']),
                   duration_seconds=report['duration_seconds'],
                   **{name: len(report[name]) for name in OUTCOMES})
    _display('KDD_SUITE_REPORT ' + json.dumps(summary, sort_keys=True))
    _display('Ran {} tests in {:.3f}s'.format(report['tests_run'], report['duration_seconds']))
    _display(('OK' if report['ok'] else 'FAILED') + ' (skipped={})'.format(len(report['skipped'])))
    for error in report['errors']:
        _display(str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-directory', default='tests')
    parser.add_argument('--pattern', default='test_*.py')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--report-json')
    parser.add_argument('--worker-plan', help=argparse.SUPPRESS)
    parser.add_argument('--worker-report', help=argparse.SUPPRESS)
    parser.add_argument('--controller-report', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        _workers(args.workers)
    except ValueError as error:
        parser.error(str(error))
    if args.worker_plan:
        if not args.worker_report:
            parser.error('worker report destination required')
        return _worker(args.worker_plan, args.worker_report)
    if args.controller_report:
        report = run_suite(args.start_directory, args.pattern, args.workers)
        _write(args.controller_report, report)
        return 0 if report['ok'] else 1
    report = _supervise(args)
    if args.report_json:
        _write(args.report_json, report)
    _summarize(report)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
