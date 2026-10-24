"""Real preflight and dispatch invocations against small isolated projects."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExecutionProfile(unittest.TestCase):
    def setUp(self):
        case = tempfile.TemporaryDirectory(prefix='kdd execution profile ')
        self.addCleanup(case.cleanup)
        self.root = Path(case.name)
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (self.root / 'knowledge/contracts').mkdir(parents=True)
        (self.root / 'tests').mkdir()
        self.env = dict(os.environ, PYTHONUTF8='1')
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')

    def module(self, name):
        path = ROOT / 'scripts' / (name + '.py')
        self.assertTrue(path.is_file(), 'Missing contracted module: ' + name)
        spec = importlib.util.spec_from_file_location('kdd_profile_' + name, path)
        module = importlib.util.module_from_spec(spec)
        previous = list(sys.path)
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = previous
        return module

    def contract(self, name='fixture', delay=.1, exit_code=0):
        oracle = self.root / 'tests/fixture.py'
        oracle.write_text('import time\nfrom pathlib import Path\n'
                          'time.sleep(' + str(delay) + ')\n'
                          'p=Path("counter"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                          'raise SystemExit(' + str(exit_code) + ')\n', encoding='utf-8')
        cmd = '"' + sys.executable + '" tests/fixture.py'
        (self.root / 'knowledge/contracts' / (name + '.md')).write_text(
            "---\ntype: 'Task Contract'\ntitle: 'Fixture'\ndescription: 'Real command'\n"
            "tags: ['testing']\ntask: " + name + "\nintent: 'Check fixture'\n"
            "signature: 'def fixture():'\nbudget:\n  cyclomatic_max: 4\n"
            "touch_only: ['feature.py']\ndeps_allowed: ['stdlib']\nforbids: ['network']\n"
            "tests: tests/fixture.py\ntests_sha256: '" +
            hashlib.sha256(oracle.read_text(encoding='utf-8').encode('utf-8')).hexdigest() + "'\ntest_command: '" + cmd +
            "'\ntarget: feature.py\n---\n## Intent\nCheck.\n## Interface\nCommand.\n"
            "## Invariants\nNo mutation.\n## Examples\n- pass\n- fail\n"
            "## Do / Don't\nKeep assertions.\n## Tests\nReal command.\n"
            "## Constraints\nPARAR y reportar si no hay command.\n", encoding='utf-8')

    def preflight_cli(self, *options):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/preflight.py'),
                               '--repo-root', str(self.root), '--contract', 'fixture', *options],
                              cwd=self.root, env=self.env, capture_output=True, text=True,
                              encoding='utf-8', timeout=15)

    def test_shared_defaults_keep_consumer_serial_and_finite_limits(self):
        profile = self.module('execution_profile').resolve_profile()
        self.assertEqual(profile, {'command_timeout': 600, 'gate_timeout': 1800,
                                   'workers': 1, 'deduplicate': True})

    def test_invalid_profile_options_are_rejected(self):
        resolve = self.module('execution_profile').resolve_profile
        invalid = [{'workers': x} for x in (True, 0, 9, 1.5, '4')]
        invalid += [{'command_timeout': x} for x in (True, 0, -1, math.nan, math.inf)]
        invalid += [{'gate_timeout': 600}, {'deduplicate': 'true'}, {'unknown': 1}]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises((ValueError, TypeError)):
                resolve(**options)

    def test_dispatch_default_argv_has_shared_profile_without_shell(self):
        dispatch = self.module('mcp_gate_dispatch')
        argv = dispatch.build_argv('validate_test_commands', {})
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[2:], ['knowledge/contracts', '.', '--timeout', '600',
                                   '--workers', '1', '--deduplicate'])

    def test_preflight_cli_propagates_real_short_command_and_limits(self):
        self.contract(delay=.2)
        proc = self.preflight_cli('--command-timeout', '2', '--gate-timeout', '10', '--workers', '1')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('3/3', proc.stdout)
        self.assertEqual((self.root / 'counter').read_text(), '1')

    def test_preflight_cli_timeout_stays_failure(self):
        self.contract(delay=2)
        proc = self.preflight_cli('--command-timeout', '.5', '--gate-timeout', '10')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('TIMEOUT', proc.stdout)
        self.assertFalse((self.root / 'counter').exists())

    def test_dispatch_real_contracts_are_deduplicated_and_reported_individually(self):
        self.contract('a')
        self.contract('b')
        dispatch = self.module('mcp_gate_dispatch')
        result = dispatch.run_gate('validate_test_commands',
                                   {'command_timeout': 2, 'gate_timeout': 10,
                                    'workers': 1, 'deduplicate': True}, repo_root=str(self.root))
        self.assertEqual(result['exit_code'], 0, result['stdout'] + result['stderr'])
        self.assertEqual((self.root / 'counter').read_text(), '1')
        self.assertIn('contracts=2 commands=1', result['stdout'])
        self.assertEqual(result['stdout'].count('PASS [product]'), 2)

    def test_explicit_serial_no_dedup_still_executes_both_commands(self):
        self.contract('a')
        self.contract('b')
        dispatch = self.module('mcp_gate_dispatch')
        result = dispatch.run_gate('validate_test_commands',
                                   {'command_timeout': 2, 'gate_timeout': 10,
                                    'workers': 1, 'deduplicate': False}, repo_root=str(self.root))
        self.assertEqual(result['exit_code'], 0, result['stdout'] + result['stderr'])
        self.assertEqual((self.root / 'counter').read_text(), '2')

    def test_dispatch_real_failure_is_not_reclassified(self):
        self.contract(exit_code=7)
        dispatch = self.module('mcp_gate_dispatch')
        result = dispatch.run_gate('validate_test_commands',
                                   {'command_timeout': 2, 'gate_timeout': 10,
                                    'workers': 1, 'deduplicate': True}, repo_root=str(self.root))
        self.assertNotEqual(result['exit_code'], 0)
        self.assertIn('FAIL [product]', result['stdout'])
        self.assertEqual((self.root / 'counter').read_text(), '1')

    def test_dispatch_rejects_bad_options_and_escaping_paths_before_effects(self):
        self.contract()
        dispatch = self.module('mcp_gate_dispatch')
        for options in ({'workers': '$(echo bad)'}, {'workers': True}, {'command_timeout': math.inf},
                        {'contracts_dir': '../outside'}, {'unknown': 'value'}):
            with self.subTest(options=options):
                (self.root / 'counter').unlink(missing_ok=True)
                result = dispatch.run_gate('validate_test_commands', options,
                                           repo_root=str(self.root))
                self.assertNotEqual(result['exit_code'], 0)
                self.assertFalse((self.root / 'counter').exists())

    def test_preflight_api_full_mode_passes_profile_to_real_dispatch(self):
        self.contract()
        preflight = self.module('preflight')
        dispatch = self.module('mcp_gate_dispatch')
        # All calls execute the real dispatcher. Other gates fail cheaply in the
        # minimal project; only the contract command has a visible side effect.
        result = preflight.run_preflight(repo_root=str(self.root), runner=dispatch.run_gate,
                                          command_timeout=2, gate_timeout=10,
                                          workers=1, deduplicate=True)
        self.assertEqual(len(result['results']), 20)
        commands = result['results']['validate_test_commands']
        self.assertEqual(commands['exit_code'], 0, commands['stdout'] + commands['stderr'])
        self.assertFalse(result['overall_ok'])
        self.assertEqual((self.root / 'counter').read_text(), '1')


if __name__ == '__main__':
    unittest.main()
