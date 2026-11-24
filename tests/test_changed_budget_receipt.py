"""Integration oracles for differential budget evidence."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.quality_review_fixture import fixture_environment, prepare_identity, run_git


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'scripts' / 'validate_changed_budgets.py'
LIMIT = """budget:
  cyclomatic_max: 2
  nesting_max: 2
  lines_max: 12
  params_max: 2"""
BASE_SOURCE = 'def result(flag):\n    return int(flag)\n'


class BudgetRepository(unittest.TestCase):
    def setUp(self):
        owner = tempfile.TemporaryDirectory(prefix='kdd-budget-evidence-')
        self.addCleanup(owner.cleanup)
        self.area = Path(owner.name).resolve()
        self.repo = self.area / 'project'
        self.repo.mkdir()
        run_git(self.repo, 'init', '-q', '-b', 'main')
        prepare_identity(self.repo)

    def git(self, *args):
        return run_git(self.repo, *args).decode('utf-8').strip()

    def write(self, relative, source):
        name = self.repo / relative
        name.parent.mkdir(parents=True, exist_ok=True)
        name.write_bytes(source.encode('utf-8'))

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def contract(self, task, target, touch=None, budget=LIMIT):
        oracle = f'def test_{task}():\n    assert 1 + 1 == 2\n'
        tests = f'test_{task}.py'
        self.write(tests, oracle)
        digest = hashlib.sha256(oracle.encode()).hexdigest()
        self.write(f'knowledge/contracts/{task}.md', f"""---
type: 'Task Contract'
title: Test receipt
description: Fixture for the differential budget audit.
tags: ['quality']
task: {task}
intent: Measure functions by approved target.
target: {target}
signature: 'def result(flag):'
test_command: python fixture
{budget}
tests: {tests}
tests_sha256: '{digest}'
touch_only: {json.dumps(touch or [target])}
deps_allowed: ['stdlib']
---
""")


class BudgetReceiptTests(BudgetRepository):
    def setUp(self):
        super().setUp()
        self.write('app.py', BASE_SOURCE)
        self.write('public/panel.ts', 'export const panel = 1;\n')
        self.write('README.md', '# Fixture\n')
        self.contract('app', 'app.py')
        self.contract('panel', 'public/panel.ts', ['public/panel.ts', 'scripts/handoff.py'])
        self.base = self.commit('base budget policies')

    def cli(self, head, *, json_mode=True):
        args = [sys.executable, str(TOOL), 'knowledge/contracts', '--repo-root', '.',
                '--base-ref', self.base, '--head-ref', head]
        if json_mode:
            args.append('--json')
        return subprocess.run(args, cwd=self.repo, env=fixture_environment(),
                              capture_output=True, text=True, encoding='utf-8', timeout=30)

    def receipt(self, completed, head, code=0):
        self.assertEqual(completed.returncode, code, completed.stdout + completed.stderr)
        self.assertTrue(completed.stdout.startswith('{'), completed.stdout + completed.stderr)
        data = json.loads(completed.stdout)
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual((data['base_ref'], data['head_ref']), (self.base, head))
        self.assertEqual(data['regression_status'], 'FAIL' if code else 'PASS')
        return data

    def test_board_like_diff_lists_both_exclusions_without_claiming_measurements(self):
        self.write('public/panel.ts', 'export const panel = 2;\n')
        self.write('scripts/handoff.py', 'def read():\n    return True\n')
        head = self.commit('update TS view with Python auxiliary')
        report = self.receipt(self.cli(head), head)
        self.assertEqual(report['files'], [
            dict(path='public/panel.ts', status='not_python', contracts=[], measurements=[]),
            dict(path='scripts/handoff.py', status='no_python_contract', contracts=[], measurements=[]),
        ])
        self.assertEqual(report['findings'], [])

    def test_measurements_name_the_exact_functions_and_contracts(self):
        self.write('app.py', BASE_SOURCE.replace('int(flag)', 'bool(flag)'))
        head = self.commit('update one measured function')
        report = self.receipt(self.cli(head), head)
        contract = 'knowledge/contracts/app.md'
        self.assertEqual(report['files'], [{
            'path': 'app.py', 'status': 'measured', 'contracts': [contract],
            'measurements': [{
                'contract': contract, 'function': 'result',
                'metrics': {'cyclomatic_max': 1, 'nesting_max': 0, 'lines_max': 2, 'params_max': 1},
                'limits': {'cyclomatic_max': 2, 'nesting_max': 2, 'lines_max': 12, 'params_max': 2},
                'within_budget': True,
            }],
        }])
        self.assertEqual(report['findings'], [])

    def test_fail_keeps_measurements_and_original_excess(self):
        self.write('app.py', BASE_SOURCE + '\ndef too_many(flag):\n'
                   '    if flag > 1:\n        return 1\n'
                   '    if flag < 0:\n        return -1\n    return 0\n')
        head = self.commit('add a function outside the approved budget')
        legacy = self.cli(head, json_mode=False)
        self.assertEqual(legacy.returncode, 1, legacy.stdout + legacy.stderr)
        self.assertIn('BUDGET_CYCLOMATIC', legacy.stdout)
        data = self.receipt(self.cli(head), head, code=1)
        measured = data['files'][0]['measurements']
        self.assertEqual([item['function'] for item in measured], ['too_many'])
        self.assertEqual(measured[0]['metrics']['cyclomatic_max'], 3)
        self.assertEqual(data['findings'], [line for line in legacy.stdout.splitlines()
                                            if line.startswith('ERROR ')])

    def test_existing_debt_can_pass_regression_while_failing_absolute_budget(self):
        source = ('def result(flag):\n'
                  '    if flag > 1:\n        return 1\n'
                  '    if flag < 0:\n        return -1\n    return 0\n')
        self.write('app.py', source)
        self.base = self.commit('establish historical complexity debt')
        self.write('app.py', source.replace('return 1', 'return 2'))
        head = self.commit('change behavior while carrying the same debt')
        data = self.receipt(self.cli(head), head)
        measured = data['files'][0]['measurements'][0]
        self.assertEqual(measured['metrics']['cyclomatic_max'], 3)
        self.assertEqual(measured['limits']['cyclomatic_max'], 2)
        self.assertIs(measured['within_budget'], False)
        self.assertEqual(data['findings'], [])


    def test_comment_change_reports_no_changed_functions_and_keeps_policy(self):
        self.write('app.py', '# Comment above the existing function.\n' + BASE_SOURCE)
        head = self.commit('change only a comment')
        data = self.receipt(self.cli(head), head)
        self.assertEqual(data['files'], [
            dict(path='app.py', status='no_changed_functions',
                 contracts=['knowledge/contracts/app.md'], measurements=[]),
        ])

    def test_rename_and_deletion_report_all_paths(self):
        self.git('mv', 'app.py', 'alternate.py')
        (self.repo / 'README.md').unlink()
        self.write('public/panel.ts', 'export const panel = 3;\n')
        head = self.commit('rename and remove files')
        report = self.receipt(self.cli(head), head)
        paths = [(item['path'], item['status']) for item in report['files']]
        self.assertEqual(paths, [('README.md', 'deleted'), ('alternate.py', 'no_python_contract'),
                                 ('app.py', 'deleted'), ('public/panel.ts', 'not_python')])
        self.assertTrue(all(not item['contracts'] and not item['measurements']
                            for item in report['files']))

    def test_receipt_reports_original_limits_for_two_policies(self):
        self.contract('secondary', 'app.py', budget='budget:\n  cyclomatic_max: 3')
        self.base = self.commit('freeze distinct policies for the same file')
        self.contract('app', 'app.py', budget='budget:\n  cyclomatic_max: 20')
        (self.repo / 'knowledge/contracts/secondary.md').unlink()
        self.write('app.py', BASE_SOURCE + '\ndef new_branch(flag):\n'
                   '    if flag > 1:\n        return 1\n'
                   '    if flag < 0:\n        return -1\n    return 0\n'
                   '\ndef a_simple(flag):\n    return str(flag)\n')
        head = self.commit('change policy and add functions out of alphabetical order')
        data = self.receipt(self.cli(head), head, code=1)
        measured = data['files'][0]
        primary = 'knowledge/contracts/app.md'
        secondary = 'knowledge/contracts/secondary.md'
        self.assertEqual(measured['contracts'], [primary, secondary])
        values = [(row['contract'], row['function'], row['limits'], row['within_budget'])
                  for row in measured['measurements']]
        self.assertEqual(values, [
            (primary, 'a_simple',
             {'cyclomatic_max': 2, 'nesting_max': 2, 'lines_max': 12, 'params_max': 2}, True),
            (primary, 'new_branch',
             {'cyclomatic_max': 2, 'nesting_max': 2, 'lines_max': 12, 'params_max': 2}, False),
            (secondary, 'a_simple', {'cyclomatic_max': 3}, True),
            (secondary, 'new_branch', {'cyclomatic_max': 3}, True),
        ])


    def test_exactly_the_same_objects_return_an_empty_inventory(self):
        report = self.receipt(self.cli(self.base), self.base)
        self.assertEqual(report['files'], [])
        self.assertEqual(report['findings'], [])

    def test_same_commits_produce_identical_receipts_after_local_edits(self):
        self.write('app.py', BASE_SOURCE.replace('int(flag)', 'bool(flag)'))
        head = self.commit('measure a committed function')
        original = self.cli(head)
        self.receipt(original, head)
        self.write('app.py', 'def result(flag):\n    return 0\n')
        self.write('untracked.py', 'def extra():\n    return 17\n')
        repeated = self.cli(head)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(original.stdout, repeated.stdout)


    def test_invalid_later_target_emits_no_partial_receipt(self):
        self.write('zbroken.py', BASE_SOURCE)
        self.contract('zbroken', 'zbroken.py')
        self.base = self.commit('establish two regular contracted targets')
        self.write('app.py', BASE_SOURCE.replace('int(flag)', 'bool(flag)'))
        self.write('zbroken.py', 'def broken(:\n')
        head = self.commit('change valid target and introduce parse failure')
        done = self.cli(head)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stdout, '')
        self.assertIn('BUDGET_PARSE', done.stderr)
        self.assertIn('zbroken.py', done.stderr)


    def test_invalid_scope_does_not_emit_a_complete_receipt(self):
        done = self.cli('f' * len(self.base))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertEqual(done.stdout, '')
        self.assertIn('BUDGET_REF', done.stderr)
