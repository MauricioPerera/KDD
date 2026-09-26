"""A sealed baseline must govern checks against an actual Git change."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_change_contract as gate  # noqa: E402


class ChangeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self._git('init', '-q')
        self._git('config', 'user.name', 'KDD Test')
        self._git('config', 'user.email', 'kdd@example.test')
        self.contract = 'knowledge/contracts/demo.md'
        self._write(self.contract, self._contract())
        self._write('src/app.py', 'def value():\n    return 1\n')
        self._write('tests/test_app.py', '# frozen oracle\n')
        self.base = self._commit('approved baseline')

    def _git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')

    def _commit(self, message):
        self._git('add', '-A')
        self._git('commit', '-qm', message)
        return self._git('rev-parse', 'HEAD')

    def _contract(self, allowed='[]', perimeter="['src/app.py']",
                  budget=12):
        return ("---\n"
                "task: demo\n"
                "target: src/app.py\n"
                "tests: tests/test_app.py\n"
                "touch_only: {}\n"
                "deps_allowed: {}\n"
                "budget:\n  cyclomatic_max: {}\n"
                "---\n").format(perimeter, allowed, budget)

    def _rules(self, head):
        findings = gate.audit_change(self.root, self.contract,
                                     self.base, head)
        return {finding['rule'] for finding in findings}

    def test_target_change_with_stdlib_import_passes(self):
        self._write('src/app.py', 'import json\n\ndef value():\n    return 2\n')
        self.assertEqual(self._rules(self._commit('implementation')), set())

    def test_real_diff_outside_touch_only_fails(self):
        self._write('README.md', 'unapproved edit\n')
        self.assertIn('OUT_OF_PERIMETER', self._rules(self._commit('escape')))

    def test_frozen_oracle_change_fails(self):
        self._write('tests/test_app.py', '# altered oracle\n')
        self.assertIn('TESTS_TOUCHED', self._rules(self._commit('alter oracle')))

    def test_new_undeclared_external_import_fails(self):
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('add import')))

    def test_new_local_import_passes(self):
        self._write('src/helper.py', 'VALUE = 2\n')
        self.base = self._commit('local helper baseline')
        self._write('src/app.py', 'from src import helper\n\ndef value():\n'
                                  '    return helper.VALUE\n')
        self.assertEqual(self._rules(self._commit('use helper')), set())

    def test_declared_external_import_passes(self):
        self._write(self.contract, self._contract(allowed="['requests']"))
        self.base = self._commit('approved dependency')
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.assertEqual(self._rules(self._commit('use dependency')), set())

    def test_existing_external_import_is_grandfathered(self):
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.base = self._commit('existing import')
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 2\n')
        self.assertEqual(self._rules(self._commit('change logic')), set())

    def test_budget_is_enforced_on_changed_python_target(self):
        self._write(self.contract, self._contract(budget=1))
        self.base = self._commit('strict budget')
        self._write('src/app.py',
                    'def value(x):\n    if x:\n        return 1\n    return 2\n')
        self.assertIn('BUDGET_CYCLOMATIC',
                      self._rules(self._commit('complex implementation')))

    def test_contract_change_cannot_expand_approved_perimeter(self):
        self._write(self.contract, self._contract(perimeter="['*']"))
        self._write('README.md', 'out of perimeter\n')
        rules = self._rules(self._commit('self approve'))
        self.assertIn('OUT_OF_PERIMETER', rules)

    def test_base_must_be_ancestor(self):
        self._write('src/app.py', 'def value():\n    return 2\n')
        head = self._commit('implementation')
        findings = gate.audit_change(self.root, self.contract, head,
                                     self.base)
        self.assertIn('GIT_RANGE', {item['rule'] for item in findings})

    def test_missing_target_is_not_silently_skipped(self):
        (self.root / 'src' / 'app.py').unlink()
        self.assertIn('TARGET_MISSING', self._rules(self._commit('remove target')))

    def test_non_python_target_has_explicit_coverage_limit(self):
        self._write(self.contract, self._contract().replace('src/app.py',
                                                           'src/app.ts'))
        self._write('src/app.ts', 'export const value = 1;\n')
        self.base = self._commit('TypeScript baseline')
        self._write('src/app.ts', 'export const value = 2;\n')
        findings = gate.audit_change(self.root, self.contract, self.base,
                                     self._commit('TypeScript implementation'))
        self.assertEqual([f['rule'] for f in findings], ['CHECK_UNSUPPORTED'])


if __name__ == '__main__':
    unittest.main()
