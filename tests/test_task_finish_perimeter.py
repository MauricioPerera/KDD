"""Independent real-Git oracle for mandatory task implementation scope.

All approvals and products in this module are synthetic temporary fixtures.
No fixture approves or changes the KDD checkout itself.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from tests.test_fixture_preparation import configure_git
from tests.test_generated_task_evidence import TaskProject


class PerimeterProject(TaskProject):
    _fixture_lock = threading.Lock()

    @classmethod
    def _fixture(cls):
        with PerimeterProject._fixture_lock:
            cached = cls.__dict__.get('_fixture_template')
            if cached is not None:
                return cached
            area = tempfile.TemporaryDirectory(prefix='kdd-perimeter-base-')
            try:
                seed = object.__new__(cls)
                TaskProject.__init__(seed, Path(area.name) / 'product')
                seed.write('auxiliary.txt', 'existing unrelated product file\n')
                seed.ref = seed.commit('Synthetic reviewed baseline with auxiliary file')
                cached = (area, seed.root, seed.ref)
                cls._fixture_template = cached
                return cached
            except BaseException:
                area.cleanup()
                raise

    def __init__(self, root):
        path = Path(root)
        if path.exists() and any(path.iterdir()):
            super().__init__(root)
            self.write('auxiliary.txt', 'existing unrelated product file\n')
            self.ref = self.commit('Synthetic reviewed baseline with auxiliary file')
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        _area, source, reference = self._fixture()
        super().__init__(root, initialize=False)
        self.command(['git', 'clone', '-q', '--shared', str(source), str(self.root)],
                     cwd=self.root.parent)
        configure_git(self.root, {'user.name': 'Simulated fixture reviewer',
            'user.email': 'fixture@example.invalid', 'maintenance.autoDetach': 'false',
            'gc.autoDetach': 'false', 'core.autocrlf': 'false', 'commit.gpgsign': 'false'},
            ephemeral=True)
        self.ref = reference

    @staticmethod
    def oracle(number):
        return TaskProject.oracle(number) + '''
import os
from pathlib import Path
if os.environ.get('KDD_PERIMETER_PROBE'):
    Path(os.environ['KDD_PERIMETER_PROBE']).write_text('oracle executed', encoding='utf-8')
'''


class PerimeterCase(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-perimeter-oracle-')
        self.addCleanup(self.area.cleanup)
        self.p = PerimeterProject(Path(self.area.name) / 'product')
        self.marker = Path(self.area.name) / 'oracle-ran.txt'
        self.p.env['KDD_PERIMETER_PROBE'] = str(self.marker)
        self.p.create(1)
        started = self.p.act('start', 1, '--assignee', 'synthetic worker')
        self.branch_base = started['task']['branch_base']
        self.p.git('switch', '-q', 'task/TASK-001')
        self.p.write('src/feature1.py', self.p.implementation(1))

    def integrate(self):
        self.tip = self.p.commit('Synthetic implementation')
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', 'task/TASK-001', '-qm', 'Integrate synthetic task')
        return self.tip

    def assert_scope_rejected(self, *paths):
        before = self.p.snapshot()
        result = self.p.act('finish', 1, check=False)
        self.assertNotEqual(result.returncode, 0, 'finish accepted an out-of-scope implementation')
        output = result.stdout + result.stderr
        self.assertIn('TASK_PERIMETER', output)
        for path in paths:
            self.assertIn(path, output)
        self.assertFalse(self.marker.exists(), 'oracle executed before the scope rejection')
        self.assertEqual(self.p.snapshot(), before, 'scope rejection changed Git state')
        self.assertEqual(list((self.p.root / 'docs/task-evidence').glob('*.json')), [])

    def legacy_close(self, receipt=None, reported_tip=None):
        """Construct an old-format closure using a real passing oracle result."""
        sys.path.insert(0, str(self.p.root / 'scripts'))
        from task_model import render_task
        from validate_contracts import parse_frontmatter
        node = 'knowledge/tasks/TASK-001.md'
        data, body = parse_frontmatter((self.p.root / node).read_text(encoding='utf-8'))
        tested = self.p.git('rev-parse', 'HEAD')
        outcome = self.p.command([sys.executable, '-m', 'unittest', 'tests/test_feature1.py'])
        def digest(content):
            return hashlib.sha256(content.encode('utf-8') if isinstance(content, str) else content).hexdigest()
        def normalized(name):
            return (self.p.root / name).read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        report = {
            'schema_version': 1, 'task_id': 'TASK-001', 'tested_commit': tested,
            'branch_tip': reported_tip or self.tip, 'approved_ref': self.p.ref,
            'contract_sha256': digest(normalized(self.p.contract(1))),
            'target_sha256': digest(normalized('src/feature1.py')),
            'oracle_sha256': digest(normalized('tests/test_feature1.py')),
            'command': 'python -m unittest tests/test_feature1.py', 'runner': 'unittest',
            'exit_code': outcome.returncode, 'passed_tests': 2,
            'stdout': outcome.stdout, 'stderr': outcome.stderr,
            'output_sha256': digest(outcome.stdout + outcome.stderr),
        }
        if receipt is not None:
            report['perimeter'] = receipt
        content = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
        evidence = 'docs/task-evidence/TASK-001-' + tested + '.json'
        data.update(status='done', reason='Synthetic historical closure', verified_ref=tested,
                    evidence=evidence, evidence_sha256=digest(content))
        self.p.write(evidence, content)
        self.p.write(node, render_task(data, body))
        return self.p.commit('Synthetic historical closure with actual passing output')

    def audit(self, ranged=True):
        args = ['--base-ref', self.p.ref, '--head-ref', 'HEAD'] if ranged else ['--head-ref', 'HEAD']
        return self.p.command([sys.executable, 'scripts/validate_tasks.py', '--repo-root',
                               str(self.p.root), *args], check=False)


class FinishPerimeterTests(PerimeterCase):
    def test_allowed_implementation_finishes_with_actual_passing_tests(self):
        self.integrate()
        result = self.p.act('finish', 1)
        self.assertEqual(result['task']['status'], 'done')
        report = json.loads((self.p.root / result['task']['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(report['passed_tests'], 2)
        self.assertTrue(self.marker.exists())

    def test_new_receipt_binds_permissions_and_exact_git_revisions(self):
        self.integrate()
        tested = self.p.git('rev-parse', 'HEAD')
        result = self.p.act('finish', 1)
        report = json.loads((self.p.root / result['task']['evidence']).read_text(encoding='utf-8'))
        receipt = report.get('perimeter')
        self.assertIsInstance(receipt, dict, 'new closures need a perimeter receipt')
        for key, value in {'schema_version': 1, 'approved_ref': self.p.ref,
                           'branch_base': self.branch_base, 'branch_tip': self.tip,
                           'tested_commit': tested, 'paths': ['src/feature1.py']}.items():
            self.assertEqual(receipt.get(key), value, key)

    def test_added_file_outside_scope_rejects_before_oracle_without_writes(self):
        self.p.write('src/outside.py', 'unrelated = True\n')
        self.integrate()
        self.assert_scope_rejected('src/outside.py')

    def test_modified_existing_file_outside_scope_rejects_before_oracle(self):
        self.p.write('auxiliary.txt', 'changed outside the contract\n')
        self.integrate()
        self.assert_scope_rejected('auxiliary.txt')

    def test_deleted_file_outside_scope_rejects_before_oracle(self):
        (self.p.root / 'auxiliary.txt').unlink()
        self.integrate()
        self.assert_scope_rejected('auxiliary.txt')

    def test_rename_checks_both_endpoints(self):
        self.p.git('mv', 'auxiliary.txt', 'renamed.txt')
        self.integrate()
        self.assert_scope_rejected('auxiliary.txt', 'renamed.txt')

    def test_reverted_outside_change_is_not_hidden_by_the_final_diff(self):
        self.p.write('outside.txt', 'temporary committed scope violation\n')
        self.p.commit('Synthetic out-of-scope intermediate commit')
        (self.p.root / 'outside.txt').unlink()
        self.integrate()
        self.assert_scope_rejected('outside.txt')

    def test_reverted_oracle_change_remains_protected(self):
        path = self.p.root / 'tests/test_feature1.py'
        original = path.read_bytes()
        self.p.write('tests/test_feature1.py', 'raise RuntimeError("temporary oracle change")\n')
        self.p.commit('Synthetic temporary oracle replacement')
        path.write_bytes(original)
        self.integrate()
        self.assert_scope_rejected('tests/test_feature1.py')

    def test_git_type_change_outside_scope_is_rejected(self):
        self.p.git('config', 'core.symlinks', 'false')
        self.p.write('auxiliary.txt', 'src/feature1.py\n')
        self.p.git('add', 'src/feature1.py', 'auxiliary.txt')
        blob = self.p.git('hash-object', '-w', 'auxiliary.txt')
        self.p.git('update-index', '--cacheinfo', '120000,' + blob + ',auxiliary.txt')
        self.p.git('commit', '-qm', 'Synthetic tracked type change')
        self.tip = self.p.git('rev-parse', 'HEAD')
        self.assertTrue(self.p.git('ls-tree', 'HEAD', 'auxiliary.txt').startswith('120000'))
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', 'task/TASK-001', '-qm', 'Integrate tracked type change')
        self.assert_scope_rejected('auxiliary.txt')

    def test_merge_cannot_introduce_an_outside_file(self):
        self.tip = self.p.commit('Synthetic allowed implementation')
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', '--no-commit', 'task/TASK-001')
        self.p.write('merge-only.txt', 'introduced only by integration\n')
        self.p.commit('Synthetic integration with an extra file')
        self.assert_scope_rejected('merge-only.txt')

    def test_unrelated_main_advance_is_not_attributed_to_the_task(self):
        self.tip = self.p.commit('Synthetic allowed implementation')
        self.p.git('switch', '-q', 'main')
        self.p.write('other-task.txt', 'independent main work\n')
        self.p.commit('Synthetic independent main advance')
        self.p.git('merge', '--no-ff', 'task/TASK-001', '-qm', 'Integrate allowed task later')
        self.assertEqual(self.p.act('finish', 1)['task']['status'], 'done')
        self.assertTrue(self.marker.exists())

    def test_merge_resolution_inside_scope_can_finish(self):
        self.tip = self.p.commit('Synthetic allowed implementation')
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', '--no-commit', 'task/TASK-001')
        self.p.write('src/feature1.py', self.p.implementation(1) + '\n# in-scope integration edit\n')
        self.p.commit('Synthetic allowed integration resolution')
        self.assertEqual(self.p.act('finish', 1)['task']['status'], 'done')

    def test_candidate_cannot_widen_approved_permissions(self):
        path = self.p.root / self.p.contract(1)
        path.write_text(path.read_text(encoding='utf-8').replace(
            "touch_only: ['src/feature1.py']", "touch_only: ['*']"), encoding='utf-8')
        self.p.write('outside.txt', 'candidate-authorized only\n')
        self.integrate()
        before = self.p.snapshot()
        result = self.p.act('finish', 1, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TASK_APPROVAL', result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.p.snapshot(), before)

    def test_oracle_worktree_side_effect_cannot_publish_done(self):
        self.integrate()
        head = self.p.git('rev-parse', 'HEAD')
        self.p.env['KDD_PERIMETER_PROBE'] = str(self.p.root / 'after-oracle.txt')
        result = self.p.act('finish', 1, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.p.root / 'after-oracle.txt').exists())
        self.assertEqual(self.p.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.p.act('show', 1)['status'], 'in_progress')
        self.assertEqual(list((self.p.root / 'docs/task-evidence').glob('*.json')), [])

    def test_public_python_api_cannot_close_an_outside_implementation(self):
        self.p.write('outside-api.txt', 'outside change through the public API\n')
        self.integrate()
        before = self.p.snapshot()
        code = ("import sys; sys.path.insert(0, 'scripts'); import task_git; "
                "task_git.mutate('.', 'finish', 'TASK-001', {})")
        result = self.p.command([sys.executable, '-c', code], check=False)
        self.assertNotEqual(result.returncode, 0, 'public mutate API bypassed scope')
        self.assertIn('TASK_PERIMETER', result.stdout + result.stderr)
        self.assertIn('outside-api.txt', result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.p.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
