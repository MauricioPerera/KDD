"""Opt-in concurrent commands: real barriers, exact verdicts and legacy default."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_test_commands as runner


class CommandWorkers(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='kdd command workers ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.contracts = self.root / 'contracts'
        self.contracts.mkdir()

    def script(self, name, source):
        path = self.root / (name + '.py')
        path.write_text(source, encoding='utf-8')
        return '"{}" "{}"'.format(sys.executable, path)

    def contract(self, name, command, target='scripts/check.py'):
        (self.contracts / (name + '.md')).write_text(
            '---\ntarget: {}\ntest_command: \'{}\'\n---\n'.format(target, command),
            encoding='utf-8')

    def execute(self, workers=2, **kwargs):
        try:
            return runner.run_all(str(self.contracts), str(self.root),
                                  workers=workers, **kwargs)
        except TypeError as error:
            self.fail('Missing contracted workers API: ' + str(error))

    def test_real_barrier_bound_and_path_order(self):
        for number in range(4):
            command = self.script('work' + str(number), '''import json,os,time
from pathlib import Path
number=NUMBER; start=time.monotonic_ns()
Path(str(number)+'.ready').write_text(str(os.getpid()))
try:
 if number<2:
  deadline=time.monotonic()+5
  while not Path(str(1-number)+'.ready').exists() and time.monotonic()<deadline:
   time.sleep(.01)
  assert Path(str(1-number)+'.ready').exists(),'no concurrent peer'
 time.sleep(.15)
finally:
 Path(str(number)+'.event').write_text(json.dumps([start,time.monotonic_ns(),os.getpid()]))
'''.replace('NUMBER', str(number)))
            self.contract(str(number), command)
        results = self.execute(timeout=15)
        self.assertEqual([Path(r['path']).stem for r in results], ['0', '1', '2', '3'])
        self.assertTrue(all(r['ok'] for r in results), results)
        events = [json.loads(p.read_text()) for p in self.root.glob('*.event')]
        self.assertEqual(len(events), 4)
        transitions = sorted([(s, 1) for s, e, pid in events] + [(e, -1) for s, e, pid in events])
        active = peak = 0
        for stamp, delta in transitions:
            active += delta
            peak = max(peak, active)
        self.assertEqual(peak, 2)
        self.assertGreaterEqual(len({e[2] for e in events}), 2)

    def test_deduplicate_shares_actual_failure_and_keeps_scopes(self):
        command = self.script('bad', 'from pathlib import Path\nimport sys\n'
                              'p=Path("count"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                              'print("fixture stdout"); sys.exit(3)\n')
        self.contract('a', command)
        self.contract('b', command, 'src/product.py')
        results = self.execute(workers=4, deduplicate=True)
        self.assertEqual((self.root / 'count').read_text(), '1')
        self.assertEqual([r['exit_code'] for r in results], [3, 3])
        self.assertEqual([r['scope'] for r in results], ['infrastructure', 'product'])
        self.assertIsNone(results[0]['shared_from'])
        self.assertEqual(results[1]['shared_from'], results[0]['path'])
        self.assertEqual(results[1]['duration_seconds'], 0)
        self.assertEqual(results[0]['stdout'], results[1]['stdout'])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner._print_results(results), 1)
        self.assertIn('Summary: product PASS=0 FAIL=1', output.getvalue())

    def test_timeout_and_missing_executable_are_failures(self):
        sleep = self.script('sleep', 'import time\ntime.sleep(5)\n')
        self.contract('a', sleep)
        self.contract('b', sleep, 'src/product.py')
        self.contract('c', 'nonexistent-kdd-worker-executable')
        results = self.execute(deduplicate=True, timeout=.2)
        self.assertEqual([r['error'] for r in results], ['timeout', 'timeout', 'not_found'])
        self.assertTrue(all(not r['ok'] for r in results))

    def test_failure_does_not_cancel_remaining_commands(self):
        self.contract('a', self.script('bad', 'raise SystemExit(3)\n'))
        for name in ('b', 'c', 'd'):
            self.contract(name, self.script(name, 'from pathlib import Path\n'
                                           'Path(' + repr(name + '.done') + ').write_text("done")\n'))
        results = self.execute()
        self.assertEqual(len(results), 4)
        self.assertFalse(results[0]['ok'])
        self.assertTrue(all(r['ok'] for r in results[1:]))
        self.assertTrue(all((self.root / (name + '.done')).is_file() for name in ('b', 'c', 'd')))

    def test_second_invocation_reexecutes_and_retains_cwd(self):
        command = self.script('counter', 'from pathlib import Path\n'
                              'p=Path("count"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                              'print(Path.cwd())\n')
        self.contract('a', command)
        self.contract('b', command)
        for expected in (1, 2):
            results = self.execute(deduplicate=True)
            self.assertTrue(all(r['ok'] for r in results))
            self.assertIn(str(self.root), results[0]['stdout'])
            self.assertEqual((self.root / 'count').read_text(), str(expected))

    def test_default_is_still_serial_and_not_deduplicated(self):
        command = self.script('counter', 'from pathlib import Path\nimport json,time\n'
                              'start=time.monotonic_ns()\n'
                              'p=Path("count"); n=int(p.read_text())+1 if p.exists() else 1\n'
                              'p.write_text(str(n)); time.sleep(.1)\n'
                              'Path(str(n)+".event").write_text(json.dumps([start,time.monotonic_ns()]))\n')
        self.contract('a', command)
        self.contract('b', command)
        results = runner.run_all(str(self.contracts), str(self.root))
        self.assertTrue(all(r['ok'] for r in results))
        self.assertEqual((self.root / 'count').read_text(), '2')
        self.assertTrue(all(r['shared_from'] is None for r in results))
        first = json.loads((self.root / '1.event').read_text())
        second = json.loads((self.root / '2.event').read_text())
        self.assertLessEqual(first[1], second[0])

    def test_invalid_workers_rejected_before_effects(self):
        self.contract('a', self.script('bad', 'from pathlib import Path\nPath("unexpected").touch()\n'))
        for value in (0, -1, 9, True, '2', 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.execute(workers=value)
                self.assertFalse((self.root / 'unexpected').exists())

    def test_cli_worker_flag_and_summary_are_real(self):
        self.contract('a', self.script('ok', 'from pathlib import Path\n'
                                      'Path("executed").touch()\nprint("fixture FAIL text")\n'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_test_commands.py'),
                                 str(self.contracts), str(self.root), '--workers', '2',
                                 '--deduplicate'], capture_output=True, text=True,
                                encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('contracts=1 commands=1 shared=0', result.stdout)
        self.assertTrue((self.root / 'executed').is_file())
        (self.root / 'executed').unlink()
        for value in ('0', '9', 'abc'):
            proc = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_test_commands.py'),
                                   str(self.contracts), str(self.root), '--workers', value],
                                  capture_output=True, timeout=20)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((self.root / 'executed').exists())


if __name__ == '__main__':
    unittest.main()
