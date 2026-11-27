"""Exercise acceptance-gated task closure with Git and both managed runners."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from tests.test_generated_task_evidence import ROOT, TaskProject


POLICY = 'acceptance.json'
TASK_CONTRACT = TaskProject.contract(1)
VIEW_CONTRACT = TaskProject.contract(2)
PRIMARY = 'tests/test_feature1.py'
PYTHON_CHECK = 'tests/test_feature1_policy.py'
NODE_TEST = 'tests/test_view.test.mjs'
NODE_CHECK = 'tests/test_view_policy.test.mjs'
PROBES = ('PYTHON', 'PYTHON_POLICY', 'NODE', 'NODE_POLICY')
OBLIGATIONS = ('signature', 'dependencies', 'budget', 'forbids', 'invariants')
MATRIX = {(path, key) for path in (TASK_CONTRACT, VIEW_CONTRACT)
          for key in ('oracle-execution', *OBLIGATIONS)}
def _python_probe(kind):
    return '''
def setUpModule():
    import os
    from pathlib import Path
    import subprocess
    head = subprocess.check_output(
        ["git", "--no-replace-objects", "rev-parse", "HEAD"], encoding="ascii").strip()
    with Path(os.environ["KDD_FINISH_%s_PROBE"]).open("a", encoding="utf-8") as stream:
        stream.write(head + "\\n")
''' % kind


PYTHON_ORACLE = TaskProject.oracle(1) + _python_probe('PYTHON')
PYTHON_POLICY = '''import unittest
from src.feature1 import f1

class ProductPolicy(unittest.TestCase):
    def test_value_policy(self):
        self.assertEqual(f1(8), 8)
''' + _python_probe('PYTHON_POLICY')


def _view_oracle(kind, symbol, argument, expected, message):
    return '''import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {appendFileSync} from 'node:fs';
import {test} from 'node:test';
import {%s} from '../src/view.ts';

test(%s, () => {
  const head = execFileSync('git', ['--no-replace-objects', 'rev-parse', 'HEAD'],
    {encoding: 'ascii'}).trim();
  appendFileSync(process.env.KDD_FINISH_%s_PROBE, head + '\\n');
  assert.equal(%s(%s), %s, %s);
});
''' % (symbol, json.dumps(message), kind, symbol, argument,
       json.dumps(expected), json.dumps(message))


VIEW_ORACLE = _view_oracle('NODE', 'label', '3', 'Vista 3', 'primary TypeScript label')
VIEW_POLICY = _view_oracle('NODE_POLICY', 'heading', '', 'Resultado', 'companion view policy')


def _metadata(text, values):
    marker = '\n---\n## Intent'
    if text.count(marker) != 1:
        raise AssertionError('The fixture contract layout changed')
    rows = '\n'.join(f'{name}: {value}' for name, value in values.items())
    return text.replace(marker, '\n' + rows + marker, 1)


def _python_contract(policy):
    text = TaskProject.contract_text(1, PYTHON_ORACLE)
    values = {
        'test_runner': 'python-unittest',
        'test_timeout': 30,
        'oracle_files': repr([PRIMARY, PYTHON_CHECK, 'tests/__init__.py', 'src/__init__.py']),
    }
    if policy is not None:
        values['acceptance_policy'] = policy
    return _metadata(text, values)


def _view_contract():
    text = TaskProject.contract_text(2, VIEW_ORACLE)
    replacements = {
        'target: src/feature2.py': 'target: src/view.ts',
        "signature: 'def f2(value):'": "signature: 'export function label(value: number): string'",
        "test_command: 'python -m unittest tests/test_feature2.py'": f"test_command: 'node --test {NODE_TEST}'",
        'tests: tests/test_feature2.py': f'tests: {NODE_TEST}',
        "touch_only: ['src/feature2.py']": "touch_only: ['src/view.ts', 'src/feature1.py']",
    }
    for before, after in replacements.items():
        if text.count(before) != 1:
            raise AssertionError(f'The TypeScript fixture template changed: {before}')
        text = text.replace(before, after, 1)
    return _metadata(text, {'language': 'typescript', 'test_runner': 'node-test',
                            'test_timeout': 30, 'oracle_files': repr([NODE_TEST, NODE_CHECK, 'package.json'])})


def _entry(path, runner, oracle, command):
    return {'path': path, 'checks': [
        {'obligation': name, 'tests': oracle, 'test_runner': runner,
         'test_command': command, 'timeout': 30}
        for name in OBLIGATIONS
    ]}


def _put_policy(project, include_task):
    entries = [
        _entry(TASK_CONTRACT, 'python-unittest', PYTHON_CHECK, f'python -m unittest {PYTHON_CHECK}'),
        _entry(VIEW_CONTRACT, 'node-test', NODE_CHECK, f'node --test {NODE_CHECK}'),
    ]
    policy = {'schema_version': 1, 'implementation': ['src/feature1.py'],
              'pm': ['knowledge/tasks/TASK-001.md'], 'contracts': entries if include_task else entries[1:]}
    project.write(POLICY, json.dumps(policy) + '\n')


class FinishAcceptance(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-close-acceptance-')
        self.addCleanup(area.cleanup)
        self.directory = Path(area.name)
        self.probes = {name: self.directory / f'{name.lower()}.log' for name in PROBES}

    def prepare(self, *, policy=POLICY, include_task=True, heading='Resultado'):
        project = TaskProject(self.directory / 'project')
        for name in ('verify_acceptance.py', 'validation_runtime.py', 'board_test_evidence.py'):
            shutil.copyfile(ROOT / 'scripts' / name, project.root / 'scripts' / name)
        project.write(PRIMARY, PYTHON_ORACLE)
        project.write(PYTHON_CHECK, PYTHON_POLICY)
        project.write(TASK_CONTRACT, _python_contract(policy))
        project.write('package.json', '{"type":"module"}\n')
        project.write('src/view.ts',
                      'export function label(value: number): string { return "Vista " + value; }\n'
                      f'export function heading(): string {{ return {json.dumps(heading)}; }}\n')
        project.write(NODE_TEST, VIEW_ORACLE)
        project.write(NODE_CHECK, VIEW_POLICY)
        project.write(VIEW_CONTRACT, _view_contract())
        _put_policy(project, include_task)
        quality = project.policy()
        quality['protected'].extend([
            'scripts/oracle_inventory.py', PYTHON_CHECK, VIEW_CONTRACT, NODE_TEST,
            NODE_CHECK, 'package.json', POLICY,
        ])
        project.write('quality/product.json', json.dumps(quality) + '\n')
        project.ref = project.commit('Temporary reviewed contracts, oracles and acceptance policy')
        project.env.update({f'KDD_FINISH_{name}_PROBE': str(path) for name, path in self.probes.items()})
        project.create(1)
        project.act('start', 1, '--assignee', 'fixture worker')
        project.implement(1)
        return project

    def receipt(self, project, closure):
        path = project.root / closure['task']['evidence']
        self.assertTrue(path.is_file())
        return json.loads(path.read_text(encoding='utf-8'))

    def runs(self, kind):
        path = self.probes[kind]
        return path.read_text(encoding='utf-8').splitlines() if path.exists() else []

    def rejected(self, project, diagnostic, *arguments):
        before = project.snapshot()
        run = project.act('finish', 1, *arguments, check=False)
        self.assertNotEqual(run.returncode, 0, 'finish published a closure without acceptance')
        self.assertIn('TASK_ACCEPTANCE', run.stdout + run.stderr)
        self.assertIn(diagnostic, run.stdout + run.stderr)
        self.assertEqual(project.snapshot(), before)
        self.assertEqual(project.act('show', 1)['status'], 'in_progress')
        self.assertEqual(list((project.root / 'docs/task-evidence').glob('*.json')), [])

    def check_bad_receipts(self, project, closed, report, board_command):
        task_path = 'knowledge/tasks/TASK-001.md'
        evidence_path = closed['task']['evidence']
        node = (project.root / task_path).read_text(encoding='utf-8')
        original_digest = closed['task']['evidence_sha256']
        snapshot = [sys.executable, 'scripts/validate_tasks.py', '--head-ref', 'main']
        for variant in ('missing', 'wrong-tested-commit'):
            with self.subTest(receipt=variant):
                invalid = dict(report)
                if variant == 'missing':
                    invalid.pop('acceptance')
                else:
                    invalid['acceptance'] = dict(report['acceptance'], tested_commit=project.ref)
                content = json.dumps(invalid, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
                digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
                project.write(evidence_path, content)
                project.write(task_path, node.replace(original_digest, digest, 1))
                project.commit('Synthetic inconsistent acceptance evidence for read-only validation')
                journal = project.command(snapshot, check=False)
                self.assertNotEqual(journal.returncode, 0)
                self.assertIn('TASK_ACCEPTANCE', journal.stdout + journal.stderr)
                board = project.command(board_command, check=False)
                self.assertNotEqual(board.returncode, 0)
                self.assertIn('TASK_EVIDENCE_INVALID', board.stderr)

    def test_legacy_task_keeps_one_primary_run_and_its_file_receipt(self):
        project = self.prepare(policy=None)
        tested = project.git('rev-parse', 'HEAD')
        closed = project.act('finish', 1)
        report = self.receipt(project, closed)
        self.assertEqual(closed['task']['status'], 'done')
        self.assertEqual(report['tested_commit'], tested)
        self.assertEqual(report['schema_version'], 2)
        self.assertNotIn('acceptance', report)
        self.assertEqual(report['oracle_results'][PRIMARY], {'executed': 2, 'skipped': 0, 'ok': True})
        self.assertEqual(self.runs('PYTHON'), [tested])
        self.assertTrue(all(not self.runs(kind) for kind in PROBES[1:]))

    def test_opted_in_default_finish_requires_the_explicit_acceptance_command(self):
        project = self.prepare()
        self.rejected(project, '--verify-acceptance')
        self.assertTrue(all(not self.runs(kind) for kind in PROBES))

    def test_mixed_matrix_closes_with_two_real_passes_and_a_board_summary(self):
        project = self.prepare()
        tested = project.git('rev-parse', 'HEAD')
        result = project.act('finish', 1, '--verify-acceptance', check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        closed = json.loads(result.stdout)
        report = self.receipt(project, closed)
        self.assertEqual(closed['task']['status'], 'done')
        self.assertEqual(report['schema_version'], 2)
        self.assertIn('acceptance', report, 'an opted-in closure requires acceptance evidence')
        accepted = report['acceptance']
        frozen = project.git('show', project.ref + ':' + POLICY) + '\n'
        digest = hashlib.sha256(frozen.encode('utf-8')).hexdigest()
        self.assertEqual(accepted['policy'], POLICY)
        self.assertEqual(accepted['policy_sha256'], digest)
        self.assertEqual(accepted['approved_ref'], project.ref)
        self.assertEqual(accepted['tested_commit'], report['tested_commit'])
        self.assertEqual(report['tested_commit'], tested)
        checks = {(row['contract'], row['obligation']): row['passes'] for row in accepted['checks']}
        self.assertEqual(set(checks), MATRIX)
        self.assertEqual(len(accepted['checks']), len(MATRIX))
        for (contract, obligation), passes in checks.items():
            with self.subTest(contract=contract, obligation=obligation):
                self.assertEqual([attempt['iteration'] for attempt in passes], [1, 2])
                want = 2 if (contract, obligation) == (TASK_CONTRACT, 'oracle-execution') else 1
                self.assertEqual([attempt['executed'] for attempt in passes], [want, want])
                for attempt in passes:
                    self.assertRegex(attempt['case_ids_sha256'], r'^[0-9a-f]{64}$')
                    self.assertRegex(attempt['output_sha256'], r'^[0-9a-f]{64}$')
                self.assertEqual(passes[0]['case_ids_sha256'], passes[1]['case_ids_sha256'])
        self.assertEqual(self.runs('PYTHON'), [tested] * 2)
        self.assertEqual(self.runs('NODE'), [tested] * 2)
        for kind in ('PYTHON_POLICY', 'NODE_POLICY'):
            runs = self.runs(kind)
            self.assertGreaterEqual(len(runs), 2)
            self.assertEqual(set(runs), {tested})
        digests = {attempts[0]['case_ids_sha256'] for attempts in checks.values()}
        self.assertEqual(len(digests), 4)
        self.assertEqual(checks[(TASK_CONTRACT, 'oracle-execution')][1]['output_sha256'],
                         report['output_sha256'])
        self.assertEqual(report['oracle_results'][PRIMARY], {'executed': 2, 'skipped': 0, 'ok': True})
        project.command([sys.executable, 'scripts/validate_tasks.py', '--base-ref', project.ref, '--head-ref', 'main'])
        audit = project.quality()
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
        command = [sys.executable, 'scripts/board_test_evidence.py', '--repo-root', str(project.root), 'TASK-001']
        board = json.loads(project.command(command).stdout)
        self.assertEqual(board['status'], 'available')
        self.assertEqual(board['tested_commit'], tested)
        self.assertEqual(board['acceptance'], {'policy': POLICY, 'policy_sha256': digest,
                                               'passes': 2, 'checks': len(MATRIX)})
        self.check_bad_receipts(project, closed, report, command)

    def test_failing_companion_view_keeps_task_in_progress(self):
        project = self.prepare(heading='Pendiente')
        tested = project.git('rev-parse', 'HEAD')
        self.rejected(project, VIEW_CONTRACT, '--verify-acceptance')
        self.assertEqual(self.runs('PYTHON'), [tested] * 2)
        self.assertEqual(self.runs('NODE'), [tested] * 2)
        self.assertTrue(self.runs('NODE_POLICY'), 'the failed policy check must actually execute')

    def test_missing_policy_at_approved_commit_blocks_before_oracles(self):
        project = self.prepare(policy='missing-acceptance.json')
        self.rejected(project, 'missing-acceptance.json', '--verify-acceptance')
        self.assertTrue(all(not self.runs(kind) for kind in PROBES))

    def test_policy_without_the_task_contract_blocks_before_oracles(self):
        project = self.prepare(include_task=False)
        self.rejected(project, TASK_CONTRACT, '--verify-acceptance')
        self.assertTrue(all(not self.runs(kind) for kind in PROBES))

    def test_policy_changed_on_main_is_rejected(self):
        project = self.prepare()
        policy = json.loads((project.root / POLICY).read_text(encoding='utf-8'))
        policy['contracts'].reverse()
        project.write(POLICY, json.dumps(policy) + '\n')
        project.commit('Local policy changed after its review')
        self.rejected(project, POLICY, '--verify-acceptance')
        self.assertTrue(all(not self.runs(kind) for kind in PROBES))


if __name__ == '__main__':
    unittest.main()
