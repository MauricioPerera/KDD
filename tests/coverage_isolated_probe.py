"""Integration probe for ci_coverage.py in a disposable coverage-enabled venv.

Run with the venv's Python. Creates a real source tree and separate
coverage directory, and validates branch hits in two isolated processes.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

COLLECTOR = Path(__file__).resolve().parents[1] / 'scripts/ci_coverage.py'


class CoverageProbe(unittest.TestCase):
    def command(self, *args, env=None, cwd=None):
        proc = subprocess.run([sys.executable, '-I', *map(str, args)], env=env,
                              cwd=cwd, capture_output=True, text=True,
                              encoding='utf-8', timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc

    def test_both_isolated_processes_contribute_to_the_same_pass(self):
        self.assertNotEqual(sys.prefix, sys.base_prefix, 'use a disposable venv')
        with tempfile.TemporaryDirectory(prefix='kdd-coverage-probe-') as folder:
            area = Path(folder).resolve()
            repo = area / 'repository'
            repo.mkdir()
            for source in ('scripts', 'src', 'site', 'tools/kdd-adoption'):
                (repo / source).mkdir(parents=True)
            module = repo / 'src/sample.py'
            module.write_text('def choose(value):\n    if value:\n        return 1\n    return 2\n',
                              encoding='utf-8')
            nested = repo / 'src/nested'
            nested.mkdir()
            (nested / 'unexecuted.py').write_text('def unused():\n    return 42\n', encoding='utf-8')
            child = area / 'child.py'
            child.write_text("import runpy, sys\n"
                             "assert runpy.run_path(sys.argv[1])['choose'](False) == 2\n",
                             encoding='utf-8')
            controller = area / 'controller.py'
            controller.write_text(
                "import runpy, subprocess, sys\n"
                "assert runpy.run_path(sys.argv[1])['choose'](True) == 1\n"
                "subprocess.run([sys.executable, '-I', sys.argv[2], sys.argv[1]], check=True)\n",
                encoding='utf-8')
            report_dir = area / 'report'
            self.command(COLLECTOR, 'prepare', '--repo-root', repo, '--output', report_dir)
            clean = {key: value for key, value in os.environ.items() if not key.startswith('COVERAGE_')}
            measured = dict(clean, COVERAGE_PROCESS_START=str(report_dir / 'coverage.ini'))
            self.command(controller, module, child, env=measured, cwd=repo)
            pieces = sorted(report_dir.glob('.coverage.*'))
            self.assertGreaterEqual(len(pieces), 2)
            self.command(controller, module, child, env=clean, cwd=repo)
            self.assertEqual(sorted(report_dir.glob('.coverage.*')), pieces)
            args = [COLLECTOR, 'report', '--repo-root', repo, '--output', report_dir,
                    '--head-sha', 'a' * 40, '--run-id', '11', '--attempt', '2',
                    '--platform', 'probe']
            corrupt = report_dir / '.coverage.corrupt'
            corrupt.write_text('not a coverage database', encoding='utf-8')
            rejected = subprocess.run([sys.executable, '-I', *map(str, args)], env=clean,
                                      cwd=repo, capture_output=True, text=True,
                                      encoding='utf-8', timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((report_dir / 'coverage.json').exists())
            corrupt.unlink()
            self.command(*args, env=clean, cwd=repo)
            data = json.loads((report_dir / 'coverage.json').read_text(encoding='utf-8'))
            self.assertEqual(data['kdd']['head_sha'], 'a' * 40)
            self.assertEqual(data['kdd']['suite_pass'], 1)
            summary = data['files']['src/sample.py']['summary']
            self.assertEqual((summary['covered_branches'], summary['num_branches']), (2, 2))
            unexecuted = data['files']['src/nested/unexecuted.py']['summary']
            self.assertEqual(unexecuted['num_statements'], 2)
            self.assertEqual(unexecuted['covered_lines'], 0)


if __name__ == '__main__':
    unittest.main()
