"""Record actual Windows worker intervals around the unchanged post-init runner."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from postinit_resource import check_report, load_module, require, save


def observe(runner, start):
    active = threading.local()
    timeline = {}
    execute = runner._run_worker
    namespace = runner.run_process.__globals__
    job_type = namespace['_WindowsJob']

    class MeasuredJob(job_type):
        def close(self):
            try:
                if self.handle and hasattr(active, 'row'):
                    accounting = self.accounting()
                    self._check(self.k.QueryInformationJobObject(
                        self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
                    active.row.update(processes=accounting.total, active_at_close=accounting.active,
                                      cpu_seconds=sum(accounting.times[:2]) / 1e7)
            finally:
                super().close()

    def worker(job, *args):
        row = dict(thread=threading.get_ident(), start=time.perf_counter() - start)
        active.row = row
        try:
            return execute(job, *args)
        finally:
            row['end'] = time.perf_counter() - start
            timeline[job['module']] = row
            del active.row

    namespace['_WindowsJob'] = MeasuredJob
    runner._run_worker = worker
    return timeline


def run(source, destination, sha):
    require(subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                   text=True).strip() == sha, 'unexpected source SHA')
    sys.path.insert(0, str(source))
    fixture = load_module(source / 'tests/test_init_project.py')
    with tempfile.TemporaryDirectory(prefix='kdd-critical-path-') as directory:
        project = Path(directory) / 'project'
        fixture._copy_repo(project, full=True)
        result = fixture._run_cli(project, '--apply')
        require(result.returncode == 0, result.stderr)
        (project / 'tests/test_init_project.py').unlink()
        sys.path.insert(0, str(project / 'scripts'))
        runner = load_module(project / 'scripts/run_test_suite.py')
        cwd = Path.cwd()
        try:
            os.chdir(project)
            started = time.perf_counter()
            timeline = observe(runner, started)
            report = runner.run_suite('tests', workers=10,
                                      module_order=project / 'tools/ci/postinit-module-order.json')
        finally:
            os.chdir(cwd)
        if not report['ok']:
            print(json.dumps({name: report[name][:10] for name in ('errors', 'failures')}), flush=True)
        require(len(timeline) == 199, 'module timeline incomplete')
        save(destination / 'timeline.json', dict(sha=sha, workers=10, timeline=timeline))
        require(all(row.get('active_at_close') == 0 for row in timeline.values()),
                'missing Job Object accounting or active process after cleanup')
        temporary = Path(directory) / 'report.json'
        save(temporary, report)
        phase = check_report(temporary, 10)
        require(phase['executed_sha256'] ==
                '0c4351d10c9edca66675efd4d1fb694caa0f5b97034b146e92d19e2381399d90',
                'case IDs changed')
        save(destination / 'summary.json', phase)
        for name, row in sorted(timeline.items(), key=lambda item: item[1]['end'], reverse=True)[:8]:
            print(name, json.dumps(row), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    run(args.source.resolve(strict=True), args.out.resolve(), args.sha)
