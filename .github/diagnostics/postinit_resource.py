"""Measure two Windows worker profiles on one VM and an exact KDD checkout."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ORDER = (6, 10, 10, 6)
EXPECTED = (2130, 199, 104, 0)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Counters:
    """Read English PDH counters independently of Windows display language."""

    class Value(ctypes.Structure):
        _fields_ = [('status', wintypes.DWORD), ('number', ctypes.c_double)]

    def __init__(self, drive):
        self.pdh = ctypes.WinDLL('pdh')
        self.handle = wintypes.HANDLE()
        pointer = ctypes.POINTER(wintypes.HANDLE)
        declarations = {
            'PdhOpenQueryW': [wintypes.LPCWSTR, ctypes.c_size_t, pointer],
            'PdhAddEnglishCounterW': [wintypes.HANDLE, wintypes.LPCWSTR, ctypes.c_size_t, pointer],
            'PdhCollectQueryData': [wintypes.HANDLE],
            'PdhGetFormattedCounterValue': [
                wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(self.Value),
            ],
            'PdhCloseQuery': [wintypes.HANDLE],
        }
        for name, args in declarations.items():
            getattr(self.pdh, name).argtypes = args
            getattr(self.pdh, name).restype = wintypes.LONG
        disk = rf'\LogicalDisk({drive})'
        paths = {
            'cpu_percent': r'\Processor(_Total)\% Processor Time',
            'cpu_queue': r'\System\Processor Queue Length',
            'disk_reads_s': disk + r'\Disk Reads/sec',
            'disk_writes_s': disk + r'\Disk Writes/sec',
            'disk_read_bytes_s': disk + r'\Disk Read Bytes/sec',
            'disk_write_bytes_s': disk + r'\Disk Write Bytes/sec',
            'disk_queue': disk + r'\Avg. Disk Queue Length',
            'disk_transfer_seconds': disk + r'\Avg. Disk sec/Transfer',
        }
        self.keys = {}
        self.check(self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.handle)), 'open')
        try:
            for name, path in paths.items():
                key = wintypes.HANDLE()
                self.check(self.pdh.PdhAddEnglishCounterW(self.handle, path, 0, ctypes.byref(key)), path)
                self.keys[name] = key
            self.check(self.pdh.PdhCollectQueryData(self.handle), 'initial sample')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def check(status, label):
        require(status == 0, f'PDH {label}: {status & 0xffffffff:#x}')

    def sample(self):
        self.check(self.pdh.PdhCollectQueryData(self.handle), 'sample')
        row = {}
        for name, key in self.keys.items():
            item = self.Value()
            status = self.pdh.PdhGetFormattedCounterValue(key, 0x200, None, ctypes.byref(item))
            if status == 0 and item.status in (0, 1):
                row[name] = item.number
        return row

    def close(self):
        self.pdh.PdhCloseQuery(self.handle)


def probe(source, scratch, stop):
    commands = {
        'python_start': [sys.executable, '-I', '-c', 'pass'],
        'git_start': ['git', '--version'],
        'git_read': ['git', '-C', str(source), 'rev-parse', 'HEAD'],
    }
    rows = []
    payload = b'x' * 4096
    for _ in range(7):
        if stop.is_set():
            break
        row = {}
        for name, command in commands.items():
            started = time.perf_counter()
            subprocess.run(command, cwd=scratch, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, check=True, timeout=15)
            row[name] = time.perf_counter() - started
        started = time.perf_counter()
        for index in range(16):
            path = scratch / f'probe-{index}'
            path.write_bytes(payload)
            require(path.read_bytes() == payload, 'probe data mismatch')
            path.unlink()
        row['files16'] = time.perf_counter() - started
        rows.append(row)
    return rows


class Monitor:
    def __init__(self, source, scratch, *, idle):
        self.source = source
        self.scratch = scratch
        self.idle = idle
        self.stop = threading.Event()
        self.counters = Counters(scratch.drive)
        self.series = []
        self.probes = []
        self.errors = []
        self.threads = [
            threading.Thread(target=self.watch, args=(self.sample_counters,)),
            threading.Thread(target=self.watch, args=(self.sample_probes,)),
        ]

    def __enter__(self):
        self.started = time.perf_counter()
        for thread in self.threads:
            thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        for thread in self.threads:
            thread.join()
        self.counters.close()

    def watch(self, function):
        try:
            function()
        except Exception as error:
            self.errors.append(f'{function.__name__}: {error}')

    def sample_counters(self):
        while not self.stop.wait(2):
            self.series.append(dict(self.counters.sample(), t=time.perf_counter() - self.started))

    def sample_probes(self):
        if not self.idle and self.stop.wait(8):
            return
        while not self.stop.is_set():
            stamp = time.perf_counter() - self.started
            rows = probe(self.source, self.scratch, self.stop)
            self.probes.append({'t': stamp, 'samples': rows})
            if self.stop.wait(6 if self.idle else 23):
                return

    def result(self):
        require(not self.errors, str(self.errors))
        require(len(self.series) >= 3 and self.probes, 'not enough monitoring samples')
        for field in self.counters.keys:
            require(any(field in row for row in self.series), f'no samples for {field}')
        return {'counters': self.series, 'probes': self.probes}


def digest(values):
    return hashlib.sha256('\n'.join(sorted(values)).encode('utf-8')).hexdigest()


def check_report(path, workers):
    report = json.loads(path.read_text(encoding='utf-8'))
    actual = (report['tests_run'], len(report['modules']), len(report['skipped']),
              len(report['fixture_omitted_ids']))
    require(actual == EXPECTED, f'unexpected inventory or SKIP counts: {actual}')
    require(report['ok'] and not report['errors'] and not report['failures'], 'suite errors')
    require(report['workers'] == workers, 'worker profile mismatch')
    ids = report['executed_ids']
    require(len(set(ids)) == len(ids) == EXPECTED[0] and sorted(ids) == sorted(report['expected_ids']),
            'executed IDs differ from discovery')
    return {'suite_seconds': report['duration_seconds'], 'executed_sha256': digest(ids),
            'skip_sha256': digest(row['id'] for row in report['skipped']),
            'expected_failure_sha256': digest(row['id'] for row in report['expected_failures']),
            'module_order_sha256': report['scheduling']['profile_sha256'],
            'module_sequence_sha256': hashlib.sha256('\n'.join(report['scheduling']['modules']).encode()).hexdigest(),
            'modules': {m['module']: m['duration_seconds'] for m in report['modules']},
            'cases': actual[0], 'skipped': actual[2]}


def run_phase(fixture, process_tree, source, out, index, workers):
    with tempfile.TemporaryDirectory(prefix=f'kdd-diag-{index}-') as temp:
        scratch = Path(temp)
        project = scratch / 'project'
        probe_dir = scratch / 'probes'
        probe_dir.mkdir()
        started = time.perf_counter()
        fixture._copy_repo(project, full=True)
        result = fixture._run_cli(project, '--apply')
        require(result.returncode == 0, f'init --apply failed: {result.stderr}')
        (project / 'tests' / 'test_init_project.py').unlink()
        prep_seconds = time.perf_counter() - started
        report = scratch / 'report.json'
        if workers == 10:
            command = [sys.executable, str(project / 'scripts/init_post_apply_suite.py'),
                       '--repo-root', str(project), '--report-json', str(report)]
        else:
            command = [sys.executable, str(project / 'scripts/run_test_suite.py'),
                       '--start-directory', 'tests', '--pattern', 'test_*.py', '--workers', str(workers),
                       '--module-order', str(project / 'tools/ci/postinit-module-order.json'),
                       '--report-json', str(report)]
        with Monitor(source, probe_dir, idle=True) as idle:
            time.sleep(14)
        save(out / f'phase-{index}-idle.json', idle.result())
        print(f'PHASE_START index={index} workers={workers} prep={prep_seconds:.2f}', flush=True)
        log = scratch / 'suite.log'
        with log.open('wb') as stream, Monitor(source, probe_dir, idle=False) as active:
            started = time.perf_counter()
            result = process_tree.run(command, cwd=project, timeout=900, stdout=stream, stderr=subprocess.STDOUT)
            elapsed = time.perf_counter() - started
        save(out / f'phase-{index}-active.json', active.result())
        if result.returncode:
            print(log.read_text(encoding='utf-8', errors='replace')[-7000:], flush=True)
            raise RuntimeError(f'suite phase {index} exited {result.returncode}')
        phase = dict(check_report(report, workers), phase=index, workers=workers,
                     elapsed_seconds=elapsed, prep_seconds=prep_seconds)
        save(out / f'phase-{index}-result.json', phase)
        print(f'PHASE_RESULT index={index} workers={workers} suite={phase["suite_seconds"]:.3f} '
              f'cases={phase["cases"]} skipped={phase["skipped"]}', flush=True)
        return phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(actual == args.sha, f'wrong source SHA: {actual}')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'environment.json', {
        'sha': actual, 'image': os.environ.get('ImageOS'), 'image_version': os.environ.get('ImageVersion'),
        'logical_cpus': os.cpu_count(), 'processor': platform.processor(), 'python': sys.version,
        'git': shutil.which('git'), 'git_version': subprocess.check_output(['git', '--version'], text=True).strip(),
        'temp_drive': Path(tempfile.gettempdir()).drive,
    })
    if args.smoke:
        with tempfile.TemporaryDirectory(prefix='kdd-diag-smoke-') as path:
            with Monitor(source, Path(path), idle=True) as monitor:
                time.sleep(8)
            save(out / 'smoke.json', monitor.result())
        return
    sys.path.insert(0, str(source))
    fixture = load_module(source / 'tests/test_init_project.py')
    process_tree = load_module(source / 'scripts/process_tree.py')
    phases = []
    identity = ('executed_sha256', 'skip_sha256', 'expected_failure_sha256', 'module_order_sha256', 'module_sequence_sha256')
    for index, workers in enumerate(ORDER, 1):
        phase = run_phase(fixture, process_tree, source, out, index, workers)
        if phases:
            require(all(phase[key] == phases[0][key] for key in identity), 'phase outcomes or order differ')
        phases.append(phase)
    save(out / 'complete.json', {'sha': actual, 'phases': phases})


if __name__ == '__main__':
    main()
