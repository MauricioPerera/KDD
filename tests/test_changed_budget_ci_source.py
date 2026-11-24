"""Exercise the protected budget step against real Git objects."""

import hashlib
import json
import re
import subprocess
import sys
import textwrap

from tests.quality_review_fixture import fixture_environment
from tests.test_changed_budget_receipt import BASE_SOURCE, BudgetRepository, ROOT


MODULES = ('scripts/validate_changed_budgets.py', 'scripts/validate_budgets.py',
           'scripts/validate_contracts.py')


class BudgetCISourceTests(BudgetRepository):
    def setUp(self):
        super().setUp()
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.step = text.split('      - name: Audit changed Python budgets\n', 1)[1]
        self.step = self.step.split('      - name:', 1)[0]
        self.body = textwrap.dedent(self.step.split('        run: |\n', 1)[1])
        self.hashes = {}
        self.temps = self.area / 'runner'
        self.temps.mkdir()
        self.step_file = self.temps / 'budget-step.py'
        self.step_file.write_text(self.body, encoding='utf-8')
        for relative in MODULES:
            raw = (ROOT / relative).read_bytes()
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            self.hashes[relative] = hashlib.sha256(raw).hexdigest()
        self.approved = self.commit('reviewed measurement modules')
        base_module = self.repo / MODULES[1]
        base_module.write_bytes(base_module.read_bytes() + b'\n# Distinct base object\n')
        self.write('app.py', BASE_SOURCE)
        self.contract('app', 'app.py')
        self.base = self.commit('approved product policy')
        self.write('app.py', BASE_SOURCE.replace('int(flag)', 'bool(flag)'))

    def run_step(self, head, ref=None, *, import_dir=None):
        env = fixture_environment()
        env.update(KDD_BUDGET_AUDITOR_REF=ref if ref is not None else self.approved,
                   KDD_BUDGET_BASE_REF=self.base, KDD_BUDGET_HEAD_REF=head,
                   KDD_CONTRACTS_DIR='knowledge/contracts', RUNNER_TEMP=str(self.temps))
        if import_dir is not None:
            env['PYTHONPATH'] = str(import_dir)
        return subprocess.run([sys.executable, str(self.step_file)], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_pin_is_literal_and_native_scope_stays_unchanged(self):
        self.assertIn('        shell: python\n', self.step)
        self.assertIn(
            "        if: ${{ !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD' }}\n",
            self.step,
        )
        self.assertIn(
            '          KDD_BUDGET_BASE_REF: ${{ github.event.pull_request.base.sha || github.event.before }}\n',
            self.step,
        )
        self.assertIn('          KDD_BUDGET_HEAD_REF: ${{ github.sha }}\n', self.step)
        self.assertTrue(re.search(r'(?m)^\s+KDD_BUDGET_AUDITOR_REF:\s+[a-f0-9]{40}(?:[a-f0-9]{24})?$',
                                  self.step), self.step)

    def test_audit_works_without_executable_copies_in_candidate(self):
        for relative in MODULES:
            (self.repo / relative).unlink()
        head = self.commit('candidate with independent Python change')
        result = self.run_step(head)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prefix = 'BUDGET_AUDITOR '
        binding = next((line[len(prefix):] for line in result.stdout.splitlines()
                        if line.startswith(prefix)), None)
        self.assertIsNotNone(binding, result.stdout)
        self.assertEqual(json.loads(binding), {'ref': self.approved, 'files': self.hashes})
        receipt = next((line for line in result.stdout.splitlines() if line.startswith('{')), None)
        self.assertIsNotNone(receipt, result.stdout)
        data = json.loads(receipt)
        self.assertEqual((data['base_ref'], data['head_ref']), (self.base, head))
        measured = next(item for item in data['files'] if item['path'] == 'app.py')
        self.assertEqual(measured['status'], 'measured')
        self.assertEqual(measured['measurements'][0]['function'], 'result')

    def test_missing_or_symbolic_auditor_ref_fails_without_a_receipt(self):
        head = self.commit('candidate')
        for value in ('', 'f' * len(self.approved), 'HEAD'):
            with self.subTest(ref=value):
                result = self.run_step(head, ref=value)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('BUDGET_AUDITOR', result.stdout + result.stderr)
                self.assertNotIn('"measurements"', result.stdout)

    def test_tree_in_place_of_regular_module_fails(self):
        path = self.repo / MODULES[1]
        path.unlink()
        self.write(MODULES[1] + '/marker.txt', 'Directory instead of a regular module\n')
        incomplete = self.commit('incomplete measurement bundle')
        result = self.run_step(incomplete, ref=incomplete)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BUDGET_AUDITOR', result.stdout + result.stderr)
        self.assertNotIn('"measurements"', result.stdout)

    def test_rejects_head_mismatch_before_measurement(self):
        self.commit('candidate')
        result = self.run_step(self.base)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BUDGET_REF', result.stdout + result.stderr)
        self.assertNotIn('"measurements"', result.stdout)


    def test_pythonpath_module_cannot_override_the_reviewed_bundle(self):
        self.write('alternate/validate_budgets.py', "raise RuntimeError('unreviewed import')\n")
        for relative in MODULES:
            (self.repo / relative).unlink()
        head = self.commit('candidate with auxiliary module')
        result = self.run_step(head, import_dir=self.repo / 'alternate')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('unreviewed import', result.stdout + result.stderr)
        self.assertIn('"measurements"', result.stdout)

    def test_reads_original_approved_objects_despite_git_replacement(self):
        path = MODULES[1]
        raw = (self.repo / path).read_bytes()
        (self.repo / path).write_bytes(raw + b'\n# Replacement content\n')
        replacement = self.commit('alternate regular measurement objects')
        (self.repo / path).write_bytes(raw)
        head = self.commit('restore checkout content')
        self.git('replace', self.approved, replacement)
        result = self.run_step(head)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prefix = 'BUDGET_AUDITOR '
        binding = next((line[len(prefix):] for line in result.stdout.splitlines()
                        if line.startswith(prefix)), None)
        self.assertIsNotNone(binding, result.stdout)
        self.assertEqual(json.loads(binding), {'ref': self.approved, 'files': self.hashes})

    def test_real_budget_failure_keeps_receipt_and_exit_code(self):
        self.write('app.py', BASE_SOURCE + '\ndef too_many(flag):\n'
                   '    if flag > 1:\n        return 1\n'
                   '    if flag < 0:\n        return -1\n    return 0\n')
        head = self.commit('candidate with excess complexity')
        result = self.run_step(head)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        receipt = next((line for line in result.stdout.splitlines() if line.startswith('{')), None)
        self.assertIsNotNone(receipt, result.stdout)
        data = json.loads(receipt)
        self.assertEqual(data['regression_status'], 'FAIL')
        self.assertFalse(data['files'][0]['measurements'][0]['within_budget'])
        self.assertTrue(any('BUDGET_CYCLOMATIC' in detail for detail in data['findings']))
