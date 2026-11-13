"""Compare complexity at original Git commits through the budget CLI."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.quality_review_fixture import fixture_environment, prepare_identity, run_git

ROOT = Path(__file__).resolve().parents[1]
BASE = """def historical(a, b):
    if a:
        return 1
    if b:
        return 2
    return 0


class Left:
    def same(self, value):
        return value


class Right:
    def same(self, value):
        if value:
            return 1
        if value is False:
            return 0
        return 2
"""


class ChangedPythonBudgets(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='kdd-changed-budgets-')
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        run_git(self.repo, 'init', '-q', '-b', 'main')
        prepare_identity(self.repo)
        self.write('app.py', BASE)
        self.contract('app')
        self.base = self.commit('existing debt')

    def write(self, name, value):
        file = self.repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value, encoding='utf-8', newline='\n')

    def contract(self, name, limit=2, target="app.py"):
        oracle = 'import unittest\nclass Oracle(unittest.TestCase):\n def test_value(self): self.assertEqual(1, 1)\n'
        self.write('test_app.py', oracle)
        digest = hashlib.sha256(oracle.encode()).hexdigest()
        self.write(f'knowledge/contracts/{name}.md', f"""---
type: Task Contract
title: App
description: Contract fixture for changed Python budgets.
tags: ['quality']
task: {name}
intent: Verify app complexity.
target: {target}
signature: 'def historical(a, b):'
test_command: 'python -m unittest test_app'
budget:
  cyclomatic_max: {limit}
  nesting_max: 1
  lines_max: 5
  params_max: 2
tests: test_app.py
tests_sha256: '{digest}'
touch_only: ['{target}']
deps_allowed: ['stdlib']
---
""")

    def commit(self, message):
        run_git(self.repo, 'add', '-A')
        run_git(self.repo, 'commit', '-qm', message)
        return run_git(self.repo, 'rev-parse', 'HEAD').decode().strip()

    def audit(self, candidate, base=None):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/validate_changed_budgets.py'),
            'knowledge/contracts', '--repo-root', '.', '--base-ref', base or self.base,
            '--head-ref', candidate], cwd=self.repo, env=fixture_environment(),
            capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_unrelated_function_change_keeps_unchanged_debt_advisory(self):
        self.write('app.py', BASE.replace('return value', 'return str(value)'))
        result = self.audit(self.commit('modify Left only'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Left.same', result.stdout)
        self.assertNotIn('BUDGET_CYCLOMATIC', result.stdout)

    def test_unchanged_or_improved_metrics_are_allowed_for_existing_debt(self):
        self.write('app.py', BASE.replace('return 1', 'return 42', 1))
        same = self.commit('change the behavior of existing debt')
        result = self.audit(same)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('historical', result.stdout)
        self.write('app.py', BASE.replace('    if b:\n        return 2\n', ''))
        improved = self.audit(self.commit('improve complexity'), base=same)
        self.assertEqual(improved.returncode, 0, improved.stdout + improved.stderr)

    def test_added_method_is_not_confused_with_old_homonym(self):
        self.write('app.py', BASE + """
class Added:
    def same(self, value):
        if value:
            return 1
        if value is False:
            return 0
        return 2
""")
        result = self.audit(self.commit('new excessive method'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('Added.same', result.stdout + result.stderr)
        self.assertIn('BUDGET_CYCLOMATIC', result.stdout + result.stderr)

    def test_increased_debt_rejects_raised_or_deleted_contract(self):
        self.write('app.py', BASE.replace('    return 0\n', '    if a == b:\n        return 3\n    return 0\n', 1))
        self.contract('app', limit=200)
        raised = self.commit('raise limit and increase existing debt')
        result = self.audit(raised)
        self.assertEqual(result.returncode, 1)
        self.assertIn('BUDGET_CYCLOMATIC', result.stdout + result.stderr)
        self.assertIn('historical', result.stdout + result.stderr)
        (self.repo / 'knowledge/contracts/app.md').unlink()
        deleted = self.audit(self.commit('remove approved contract'))
        self.assertEqual(deleted.returncode, 1)
        self.assertIn('BUDGET_CYCLOMATIC', deleted.stdout + deleted.stderr)

    def test_new_contract_does_not_block_existing_debt_and_enforces_new_functions(self):
        self.write('secondary.py', BASE)
        secondary_base = self.commit('independent source with existing debt')
        self.contract('added', target='secondary.py')
        unchanged = self.audit(self.commit('add a contract for existing target'), base=secondary_base)
        self.assertEqual(unchanged.returncode, 0, unchanged.stdout + unchanged.stderr)
        self.write('secondary.py', BASE + BASE.split('class Left:', 1)[0].replace(
            'historical(', 'new_function('))
        result = self.audit(self.commit('add a newly contracted function'), base=secondary_base)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout + result.stderr,
                         r'(?m)^.*BUDGET_CYCLOMATIC.*added\.md.*new_function')

    def test_budget_compares_each_metric_even_when_branch_count_is_unchanged(self):
        cases = {
            'BUDGET_LINES': BASE.replace('    if a:', '    # added comment\n    if a:', 1),
            'BUDGET_PARAMS': BASE.replace('historical(a, b)', 'historical(a, b, c)'),
            'BUDGET_NESTING': BASE.replace('    if b:\n        return 2', '        if b:\n            return 2'),
        }
        for rule, text in cases.items():
            with self.subTest(rule=rule):
                self.write('app.py', text)
                result = self.audit(self.commit(rule))
                self.assertEqual(result.returncode, 1)
                self.assertIn(rule, result.stdout + result.stderr)
                self.assertIn('historical', result.stdout + result.stderr)

    def test_new_contract_with_invalid_seal_cannot_authorize_measurement(self):
        self.contract('added', limit=200)
        self.write('test_app.py', 'changed bytes\n')
        result = self.audit(self.commit('add contract with invalid oracle seal'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('BUDGET_CONTRACT', result.stdout + result.stderr)

    def test_uses_committed_source_and_ignores_git_replacements(self):
        self.write('app.py', BASE.replace('return value', 'return str(value)'))
        candidate = self.commit('safe committed candidate')
        self.write('app.py', 'broken syntax :')
        self.assertEqual(self.audit(candidate).returncode, 0)
        replacement = self.commit('bad replacement')
        run_git(self.repo, 'replace', candidate, replacement)
        self.assertEqual(self.audit(candidate).returncode, 0)
        blocked = self.audit(replacement)
        self.assertEqual(blocked.returncode, 1)
        self.assertIn('BUDGET_PARSE', blocked.stdout + blocked.stderr)

    def test_invalid_interval_never_returns_success(self):
        result = self.audit('HEAD')
        self.assertEqual(result.returncode, 1)
        self.assertIn('BUDGET_REF', result.stdout + result.stderr)

    def test_native_workflow_invokes_budget_diff(self):
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertIn('      - name: Audit changed Python budgets\n', text)
        step = text.split('      - name: Audit changed Python budgets\n', 1)[1]
        step = step.split('      - name:', 1)[0]
        self.assertIn("!inputs.reusable_execution", step)
        self.assertIn('github.event.before', step)
        self.assertIn('github.event.pull_request.base.sha', step)
        self.assertIn('github.sha', step)
        body = textwrap.dedent(step.split('        run: |\n', 1)[1])
        (self.repo / 'scripts').mkdir()
        for name in ('validate_changed_budgets.py', 'validate_budgets.py', 'validate_contracts.py'):
            source = ROOT / 'scripts' / name
            (self.repo / 'scripts' / name).write_bytes(source.read_bytes())
        self.write('app.py', BASE.replace('return value', 'return str(value)'))
        candidate = self.commit('candidate checked out in CI')
        env = fixture_environment()
        env.update(KDD_BUDGET_BASE_REF=self.base, KDD_BUDGET_HEAD_REF=candidate,
                   KDD_CONTRACTS_DIR='knowledge/contracts')
        def run():
            return subprocess.run([sys.executable, '-c', body], cwd=self.repo, env=env,
                                  capture_output=True, text=True, encoding='utf-8', timeout=30)
        accepted = run()
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn('Left.same', accepted.stdout)
        env['KDD_BUDGET_HEAD_REF'] = self.base
        rejected = run()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('BUDGET_REF', rejected.stdout + rejected.stderr)
