"""Real Git and subprocess regressions for quality runner maintenance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts' / 'verify_quality.py'


class ExistingBudgets(unittest.TestCase):
    def budget(self, name):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_budgets.py'),
                                 str(ROOT / 'knowledge/contracts'), '--repo-root', str(ROOT),
                                 '--contract', name], capture_output=True, text=True,
                                encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_original_quality_budget(self):
        self.budget('verify-quality')

    def test_canonical_reference_budget(self):
        self.budget('quality-ref-canonical')

    def test_process_lifecycle_budget(self):
        self.budget('quality-process-lifecycle')

    def test_generated_evidence_budget(self):
        self.budget('quality-task-evidence')


class QualityIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd-quality-complexity-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        self.git('init', '-q')
        self.git('config', 'user.name', 'Quality Integration')
        self.git('config', 'user.email', 'quality@example.invalid')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/process_tree.py', self.root / 'scripts/process_tree.py')
        (self.root / 'oracle.py').write_text('assert True\n', encoding='utf-8')
        (self.root / 'product.py').write_text('value = 1\n', encoding='utf-8')
        self.policy = {'protected': ['oracle.py'], 'implementation': ['product.py'],
                       'pm': ['trace.txt'], 'required_kinds': ['functional', 'adversarial'],
                       'checks': [self.check('functional'), self.check('adversarial')]}

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args], env=self.env,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def check(self, name):
        code = "from pathlib import Path; p=Path('trace.txt'); p.write_text((p.read_text() if p.exists() else '')+%r)" % (name + '\n')
        return {'name': name, 'kind': name, 'argv': [sys.executable, '-c', code], 'timeout': 10}

    def freeze(self):
        (self.root / 'quality.json').write_text(json.dumps(self.policy), encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-qm', 'approved baseline')
        return self.git('rev-parse', 'HEAD')

    def run_quality(self, ref):
        return subprocess.run([sys.executable, str(RUNNER), '--repo-root', str(self.root),
                               '--policy', 'quality.json', '--approved-ref', ref],
                              env=self.env, capture_output=True, text=True,
                              encoding='utf-8', timeout=60)

    def test_actual_checks_execute_twice_in_order(self):
        ref = self.freeze()
        (self.root / 'product.py').write_text('value = 2\n', encoding='utf-8')
        result = self.run_quality(ref)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'trace.txt').read_text(encoding='utf-8').splitlines(),
                         ['functional', 'adversarial', 'functional', 'adversarial'])
        self.assertEqual(result.stdout.count('PASS quality:'), 1)
        self.assertEqual(self.git('rev-parse', 'HEAD'), ref)

    def test_index_tampering_rejected_before_any_check(self):
        ref = self.freeze()
        path = self.root / 'oracle.py'
        original = path.read_bytes()
        path.write_text('assert False\n', encoding='utf-8')
        self.git('add', 'oracle.py')
        path.write_bytes(original)
        staged = self.git('diff', '--cached', '--', 'oracle.py')
        result = self.run_quality(ref)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Protected index changed', result.stderr)
        self.assertFalse((self.root / 'trace.txt').exists())
        self.assertEqual(self.git('diff', '--cached', '--', 'oracle.py'), staged)
        self.assertEqual(self.git('rev-parse', 'HEAD'), ref)

    def test_alias_rejected_without_running_checks(self):
        ref = self.freeze()
        result = self.run_quality('HEAD')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('canonical', result.stderr)
        self.assertFalse((self.root / 'trace.txt').exists())
        self.assertEqual(self.git('rev-parse', 'HEAD'), ref)

    def test_failed_check_still_rechecks_protected_file(self):
        self.policy['checks'][0]['argv'] = [sys.executable, '-c',
            "from pathlib import Path; Path('oracle.py').write_text('changed'); raise SystemExit(7)"]
        ref = self.freeze()
        result = self.run_quality(ref)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Protected file changed', result.stderr)
        self.assertNotIn('PASS quality:', result.stdout)
        self.assertFalse((self.root / 'trace.txt').exists())
        self.assertEqual(self.git('rev-parse', 'HEAD'), ref)

    def test_duplicate_check_name_fails_before_execution(self):
        self.policy['checks'][1]['name'] = 'functional'
        ref = self.freeze()
        result = self.run_quality(ref)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate check name', result.stderr)
        self.assertFalse((self.root / 'trace.txt').exists())


if __name__ == '__main__':
    unittest.main()
