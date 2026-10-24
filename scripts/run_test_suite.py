"""Complete unittest discovery with bounded processes and reconciled case IDs."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


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


def _empty(ids):
    return dict(version=1, ok=False, tests_run=0, expected_ids=sorted(ids),
                executed_ids=[], modules=[], **{name: [] for name in OUTCOMES})


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
        if values != sorted(values) or Counter(values) != Counter(expected_ids):
            problems.append('incomplete or foreign ' + name)
    count = report.get('tests_run')
    executed = report.get('executed_ids')
    if (type(count) is not int or count < 0 or not isinstance(executed, list)
            or count != len(executed)):
        problems.append('incorrect executed count')
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
              and all(isinstance(report.get(k), list) for k in (*OUTCOMES, 'executed_ids', 'expected_ids', 'modules'))
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


def _execute(suite, ids):
    started = time.perf_counter()
    result = unittest.TextTestRunner(resultclass=RecordingResult).run(suite)
    report = _empty(ids)
    report.update(ok=result.wasSuccessful(), tests_run=result.testsRun,
                  executed_ids=sorted(result.executed_ids), pid=os.getpid(),
                  duration_seconds=time.perf_counter() - started,
                  stdout_encoding=sys.stdout.encoding, stderr_encoding=sys.stderr.encoding)
    report['skipped'] = [_outcome(t, reason=reason) for t, reason in result.skipped]
    for name in ('failures', 'errors', 'expected_failures'):
        source = result.expectedFailures if name == 'expected_failures' else getattr(result, name)
        report[name] = [_outcome(t, traceback=trace) for t, trace in source]
    report['unexpected_successes'] = [_outcome(t) for t in result.unexpectedSuccesses]
    return report


def _write(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')


def _worker(plan_path, report_path):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    sys.path.insert(0, str(Path.cwd()))
    sys.path.insert(0, plan['start_dir'])
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(plan['ids'])
    actual = [case.id() for case in _cases(suite)]
    if loader.errors or Counter(actual) != Counter(plan['ids']):
        report = _empty(plan['ids'])
        _problem(report, '\n'.join(loader.errors) or 'worker inventory mismatch')
    else:
        report = _execute(suite, plan['ids'])
        for error in validate_report(plan['ids'], report):
            _problem(report, error)
    _write(report_path, report)
    return 0 if report['ok'] else 1


def _run_worker(job, directory, index, start_dir):
    ids = job['ids']
    plan = Path(directory) / ('plan-' + str(index) + '.json')
    destination = Path(directory) / ('result-' + str(index) + '.json')
    _write(plan, {'ids': ids, 'start_dir': start_dir})
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                           '--worker-plan', str(plan), '--worker-report', str(destination)],
                          cwd=Path.cwd(), capture_output=True)
    try:
        report = json.loads(destination.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        report = _empty(ids)
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
    loader = unittest.TestLoader()
    try:
        suite = loader.discover(start_dir, pattern=pattern)
        cases = list(_cases(suite))
    except (ImportError, OSError, ValueError) as error:
        report = _empty([])
        _problem(report, error)
        report.update(workers=workers, duration_seconds=time.perf_counter() - started)
        return report
    ids = [case.id() for case in cases]
    report = _empty(ids)
    if not ids or len(set(ids)) != len(ids) or loader.errors:
        _problem(report, '\n'.join(loader.errors) or 'empty or duplicate discovery inventory')
    elif workers == 1:
        report = _execute(suite, ids)
    else:
        jobs = {}
        for case in cases:
            module = type(case).__module__
            jobs.setdefault(module, {'module': module, 'ids': []})['ids'].append(case.id())
        with tempfile.TemporaryDirectory(prefix='kdd-suite-') as directory:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_run_worker, job, directory, index, start_dir)
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
            report['modules'].append(child['module_result'])
            for name in OUTCOMES:
                report[name].extend(child[name])
        report['executed_ids'].sort()
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
        proc = subprocess.run([
            sys.executable, str(Path(__file__).resolve()),
            '--start-directory', args.start_directory, '--pattern', args.pattern,
            '--workers', str(args.workers), '--controller-report', str(destination)],
            cwd=Path.cwd(), capture_output=True)
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
    digest = lambda ids: hashlib.sha256(('\n'.join(ids) + '\n').encode('utf-8')).hexdigest()
    summary = dict(version=1, ok=report['ok'], tests_run=report['tests_run'],
                   expected_count=len(report['expected_ids']), workers=report['workers'],
                   expected_ids_sha256=digest(report['expected_ids']),
                   executed_ids_sha256=digest(report['executed_ids']),
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
