"""Integration with the independently evolved trusted CI runtime."""
import shutil
import unittest
from pathlib import Path
from tests import test_ci_trusted_execution as trusted_fixtures

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ('oracle_execution.py', 'oracle_inventory.py', 'unittest_oracle_runner.py', 'node_oracle_reporter.mjs')

class MethodologyIntegration(unittest.TestCase):
    def test_external_runtime_executes_instrumented_contract(self):
        fixture = trusted_fixtures.TrustedExecution('test_guard_allows_an_ordinary_implementation_module')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for name in HELPERS:
            shutil.copy2(ROOT / 'scripts' / name, fixture.repo / 'scripts' / name)
        contract = fixture.repo / 'knowledge/contracts/feature.md'
        text = contract.read_text(encoding='utf-8').replace("test_command: 'python scripts/run_test_suite.py --start-directory tests'", "test_command: 'python -m unittest tests/test_feature.py'\ntest_runner: python-unittest\noracle_files: ['tests/test_feature.py']")
        contract.write_text(text, encoding='utf-8')
        fixture.base = fixture.commit('Reviewed managed runtime and oracle')
        bundle = fixture.bundle()
        result = fixture.execute(bundle, mode='commands')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((fixture.repo / 'runs').read_text(), '1')
        for name in HELPERS:
            self.assertTrue((bundle / name).is_file(), name)
