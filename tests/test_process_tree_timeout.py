"""Actual descendants, pipes and side effects; no mocked subprocess lifecycle."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProcessTreeTimeout(unittest.TestCase):
    FIXTURE_TIMEOUT = 5.0
    TASK_ORACLE_TIMEOUT = 15.0

    def setUp(self):
        case = tempfile.TemporaryDirectory(prefix='kdd process \u00f1 ')
        self.addCleanup(case.cleanup)
        self.root = Path(case.name)

    def module(self, name):
        path = ROOT / 'scripts' / (name + '.py')
        self.assertTrue(path.is_file(), 'Missing contracted module: ' + name)
        spec = importlib.util.spec_from_file_location('kdd_timeout_' + name, path)
        module = importlib.util.module_from_spec(spec)
        previous = list(sys.path)
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = previous
        return module

    def tree(self, detached=False):
        # Absolute schedule bounds even an uncontained negative-control fixture.
        # Real descendants stay alive until the parent observes both of them.
        wait = ('late_at=json.loads(Path("schedule.json").read_text())["late_at"]\n'
                'while not Path("release").exists() and time.monotonic()<late_at: time.sleep(.01)\n'
                'if not Path("release").exists(): sys.exit(2)\n'
                'while time.monotonic()<late_at: time.sleep(.01)\n')
        grand = self.root / 'grandchild.py'
        grand.write_text('import json,os,sys,time\nfrom pathlib import Path\n'
                         'Path("grand.ready").write_text(str(os.getpid()))\n'
                         + wait +
                         'Path("grand.late").write_text("must not happen")\n', encoding='utf-8')
        child = self.root / 'child.py'
        child.write_text('import json,os,subprocess,sys,time\nfrom pathlib import Path\n'
                         'Path("child.ready").write_text(str(os.getpid()))\n'
                         'subprocess.Popen([sys.executable,' + repr(str(grand)) + '])\n'
                         + wait +
                         'Path("child.late").write_text("must not happen")\n', encoding='utf-8')
        redirection = ',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL' if detached else ''
        body = ('import subprocess,sys,time\nfrom pathlib import Path\n'
                'subprocess.Popen([sys.executable,' + repr(str(child)) + ']' + redirection + ')\n'
                'while not all(Path(p).exists() for p in ("child.ready","grand.ready")): time.sleep(.01)\n'
                'Path("tree.ready").write_text("observed")\n'
                'Path("release").touch()\n'
                'time.sleep(25)\n')
        parent = self.root / 'parent.py'
        parent.write_text(body, encoding='utf-8')
        return parent, body

    def assert_cancelled(self, operation, delay=None, timeout=None):
        if timeout is None:
            timeout = self.FIXTURE_TIMEOUT
        if delay is None:
            delay = timeout + 2.0
        start = time.monotonic()
        (self.root / 'schedule.json').write_text(json.dumps({'late_at': start + delay}), encoding='utf-8')
        result = operation()
        elapsed = time.monotonic() - start
        names = ('child.ready', 'grand.ready', 'tree.ready')
        ready = [(self.root / name).exists() for name in names]
        # On the old implementation descendants self-terminate; keep fixtures alive
        # until then even when an assertion will fail, avoiding orphaned writes.
        until = start + delay + 1.0
        while time.monotonic() < until:
            time.sleep(.05)
        present = [name for name, exists in zip(names, ready) if exists]
        missing = [name for name, exists in zip(names, ready) if not exists]
        self.assertTrue(all(ready), 'The test must observe real child and grandchild startup; '
                        'present={!r}; missing={!r}; elapsed={:.3f}; timeout={}; result={!r}'.format(
                            present, missing, elapsed, timeout, result))
        self.assertFalse((self.root / 'child.late').exists(), 'child survived the timeout')
        self.assertFalse((self.root / 'grand.late').exists(), 'grandchild survived the timeout')
        self.assertLess(elapsed, timeout + 6.0, 'deadline plus five-second cleanup grace exceeded')
        return result

    def test_completed_process_keeps_unicode_output_cwd_env_and_exit_code(self):
        runner = self.module('process_tree')
        proc = runner.run([sys.executable, '-c',
                           'import os,sys;print(os.environ["KDD_FIXTURE_VALUE"]);'
                           'print(os.getcwd());print("error ñ",file=sys.stderr);sys.exit(7)'],
                          cwd=self.root, timeout=10, capture_output=True, text=True,
                          encoding='utf-8', env=dict(os.environ, PYTHONUTF8='1', KDD_FIXTURE_VALUE='señal'))
        self.assertEqual(proc.returncode, 7)
        self.assertIn('señal', proc.stdout)
        self.assertIn(str(self.root), proc.stdout)
        self.assertIn('error ñ', proc.stderr)

    def test_invalid_timeouts_never_start_target(self):
        runner = self.module('process_tree')
        code = 'from pathlib import Path;Path("unexpected").touch()'
        for value in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                runner.run([sys.executable, '-c', code], cwd=self.root, timeout=value)
        self.assertFalse((self.root / 'unexpected').exists())

    def test_direct_timeout_cancels_child_and_grandchild_with_detached_output(self):
        runner = self.module('process_tree')
        parent, _ = self.tree(detached=True)
        def operation():
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run([sys.executable, str(parent)], cwd=self.root, timeout=self.FIXTURE_TIMEOUT,
                           capture_output=True, text=True)
        self.assert_cancelled(operation)

    def test_direct_timeout_bounds_inherited_pipe_drain(self):
        runner = self.module('process_tree')
        parent, _ = self.tree()
        def operation():
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run([sys.executable, str(parent)], cwd=self.root, timeout=self.FIXTURE_TIMEOUT,
                           capture_output=True, text=True)
        self.assert_cancelled(operation, delay=self.FIXTURE_TIMEOUT + 7.0)

    def test_contract_executor_timeout_cleans_descendants(self):
        gate = self.module('validate_test_commands')
        parent, _ = self.tree(detached=True)
        cmd = '"' + sys.executable + '" "' + str(parent) + '"'
        result = self.assert_cancelled(lambda: gate.run_test_command(
            cmd, str(self.root), timeout=self.FIXTURE_TIMEOUT, capture=True))
        self.assertEqual(result['error'], 'timeout')
        self.assertFalse(result['ok'])

    def test_preflight_timeout_cleans_descendants(self):
        preflight = self.module('preflight')
        parent, _ = self.tree(detached=True)
        tests = self.root / 'tests'
        tests.mkdir()
        oracle = tests / 'fixture.py'
        oracle.write_text('assert 1 == 1\n', encoding='utf-8')
        import hashlib
        contracts = self.root / 'knowledge/contracts'
        contracts.mkdir(parents=True)
        cmd = '"' + sys.executable + '" "' + str(parent) + '"'
        (contracts / 'fixture.md').write_text(
            "---\ntests: tests/fixture.py\ntests_sha256: '" +
            hashlib.sha256(oracle.read_text(encoding='utf-8').encode('utf-8')).hexdigest() + "'\ntest_command: '" + cmd + "'\n---\n",
            encoding='utf-8')
        result = self.assert_cancelled(lambda: preflight.run_preflight(
            repo_root=str(self.root), contract='fixture', command_timeout=self.FIXTURE_TIMEOUT, gate_timeout=10))
        self.assertFalse(result['overall_ok'])
        self.assertIsNone(result['results']['test_command']['exit_code'])

    def test_mcp_timeout_cleans_descendants(self):
        dispatch = self.module('mcp_gate_dispatch')
        parent, _ = self.tree(detached=True)
        scripts = self.root / 'scripts'
        scripts.mkdir()
        # A real gate-shaped target lets us exercise the dispatch deadline without
        # running the repository's recursive collection of contract commands.
        (scripts / 'validate_changelog.py').write_bytes(parent.read_bytes())
        result = self.assert_cancelled(lambda: dispatch.run_gate(
            'validate_changelog', {}, repo_root=str(self.root), timeout=self.FIXTURE_TIMEOUT))
        self.assertIsNone(result['exit_code'])
        self.assertIn('timeout', result['stderr'])

    def test_task_oracle_timeout_cleans_descendants(self):
        evidence = self.module('task_evidence')
        _, body = self.tree(detached=True)
        tests = self.root / 'tests'
        tests.mkdir()
        (tests / '__init__.py').write_text('', encoding='utf-8')
        (tests / 'test_oracle.py').write_text('import unittest\nclass T(unittest.TestCase):\n'
                                            ' def test_tree(self):\n' +
                                            ''.join('  ' + line + '\n' for line in body.splitlines()),
                                            encoding='utf-8')
        metadata = {'test_command': 'python -m unittest tests/test_oracle.py',
                    'tests': 'tests/test_oracle.py'}
        def operation():
            with self.assertRaises(Exception) as raised:
                evidence.execute(metadata, str(self.root), timeout=self.TASK_ORACLE_TIMEOUT)
            self.assertIn('TASK_TESTS', str(raised.exception))
            return raised.exception
        result = self.assert_cancelled(operation, timeout=self.TASK_ORACLE_TIMEOUT)
        self.assertIsInstance(result.__cause__, subprocess.TimeoutExpired,
                              'Task oracle must fail because of TimeoutExpired: ' + str(result))

    def test_timeout_does_not_kill_an_unrelated_neighbor(self):
        runner = self.module('process_tree')
        neighbor = subprocess.Popen([sys.executable, '-c',
                                      'import time;time.sleep(3);print("neighbor completed")'],
                                     cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run([sys.executable, '-c', 'import time;time.sleep(20)'],
                           cwd=self.root, timeout=.5, capture_output=True)
            stdout, stderr = neighbor.communicate(timeout=8)
            self.assertEqual(neighbor.returncode, 0, stderr)
            self.assertIn(b'neighbor completed', stdout)
        finally:
            if neighbor.poll() is None:
                neighbor.kill()
                neighbor.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
