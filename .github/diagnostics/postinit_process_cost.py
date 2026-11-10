"""Measure existing Windows job objects while running the full official worker profile."""
import argparse
import ctypes
import time
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from postinit_resource import check_report, load_module, require, save

TARGETS = {'test_task_committed_artifacts', 'test_traceability_git', 'test_task_operation_controls'}


def stamp():
    return time.time()


def observe(runner):
    """Attach observation to the existing containment jobs of selected modules."""
    original = runner.run_process
    namespace = original.__globals__
    base = namespace['_WindowsJob']
    current = threading.local()
    records = {}

    class Observed(base):
        def assign(self, pid):
            super().assign(pid)
            self.root = (pid, stamp())

        def close(self):
            try:
                module = getattr(current, 'module', None)
                if module in TARGETS and self.handle and hasattr(self, 'root'):
                    accounting = self.accounting()
                    self._check(self.k.QueryInformationJobObject(
                        self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
                    require(module not in records and accounting.active == 0,
                            'profiling requires one completed job per module')
                    records[module] = {
                        'root_pid': self.root[0], 'assigned_epoch': self.root[1],
                        'processes': accounting.total, 'user_seconds': accounting.times[0] / 1e7,
                        'kernel_seconds': accounting.times[1] / 1e7,
                    }
            finally:
                super().close()

    def instrument(argv, **kwargs):
        plan = Path(argv[argv.index('--worker-plan') + 1])
        module = json.loads(plan.read_text(encoding='utf-8'))['origin']
        current.module = module
        try:
            return original(argv, **kwargs)
        finally:
            del current.module

    namespace['_WindowsJob'] = Observed
    runner.run_process = instrument
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(strict=True), args.out.resolve()
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(actual == args.sha, 'unexpected checkout revision')
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(source))
    fixture = load_module(source / 'tests/test_init_project.py')
    with tempfile.TemporaryDirectory(prefix='kdd-process-cost-') as scratch:
        project = Path(scratch) / 'project'
        fixture._copy_repo(project, full=True)
        applied = fixture._run_cli(project, '--apply')
        require(applied.returncode == 0, applied.stderr)
        (project / 'tests/test_init_project.py').unlink()
        sys.path.insert(0, str(project / 'scripts'))
        runner = load_module(project / 'scripts/run_test_suite.py')
        records = observe(runner)
        previous = Path.cwd()
        try:
            os.chdir(project)
            report = runner.run_suite('tests', workers=10, module_order=project / 'tools/ci/postinit-module-order.json')
        finally:
            os.chdir(previous)
        if not report['ok']:
            print(str(report['errors'][:5])[:4000], flush=True)
            print(str(report['failures'][:5])[:4000], flush=True)
        report_file = Path(scratch) / 'report.json'
        save(report_file, report)
        phase = check_report(report_file, 10)
        require(set(records) == TARGETS, f'missing worker records: {TARGETS - set(records)}')
        for module in records:
            records[module]['wall_seconds'] = phase['modules'][module]
        save(out / 'profile.json', {'sha': actual, 'suite': phase, 'jobs': records})


if __name__ == '__main__':
    main()
