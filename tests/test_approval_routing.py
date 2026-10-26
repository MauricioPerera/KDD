"""Real PR refs, trusted guard processes and generated product-quality CI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.test_approval_registry import GitApprovalFixture, ROOT
from tests.test_bootstrap_product_quality_ci import PRODUCT, ORACLE, CONFIG_STEP, QUALITY_STEP
import guard_pr_baseline as guard

SELECT_STEP = 'Select approved references'
WORKFLOW = '.github/workflows/validate.yml'
TEMPLATE = (ROOT / 'src/hello.py').is_file()
TEMPLATE_ONLY = 'template-only bootstrap integration: project already initialized'


class TestApprovalRouting(GitApprovalFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.origin = cls.root.parent / 'origin.git'
        cls.command('git', 'init', '--bare', '-q', str(cls.origin))
        cls.command('git', 'remote', 'add', 'origin', str(cls.origin))
        cls.command('git', 'checkout', '-qb', 'integration-two', cls.refs['main'])
        cls.command('git', 'merge', '--no-ff', '-qm', 'merge proposal two', cls.refs['two'])
        cls.refs['merge-two'] = cls.command('git', 'rev-parse', 'HEAD')
        cls.command('git', 'checkout', '-q', 'main')
        for number, name in ((17, 'merge'), (18, 'merge-two'), (19, 'poison')):
            cls.command('git', 'push', '-q', 'origin', cls.refs[name] + ':refs/pull/' + str(number) + '/merge')

    def invoke_guard(self, number, records, **extra):
        env = dict(os.environ, PYTHONUTF8='1', **extra)
        return subprocess.run([sys.executable, str(ROOT / 'scripts/guard_pr_baseline.py'),
            '--pr-number', str(number), '--base-ref', self.refs['main'],
            '--approval-registry', json.dumps(records)], cwd=self.root, env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=60)

    def guard_findings(self, candidate, approved):
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            return guard.check(self.refs['main'], candidate, approved)
        finally:
            os.chdir(previous)

    def step_body(self, root, name):
        text = (root / WORKFLOW).read_text(encoding='utf-8')
        marker = '      - name: ' + name + '\n'
        self.assertTrue(marker in text, 'Expected generated CI step: ' + name)
        block = text.split(marker, 1)[1].split('\n      - ', 1)[0]
        self.assertIn('        run: |\n', block)
        return textwrap.dedent(block.split('        run: |\n', 1)[1])

    def execute_step(self, root, name, env):
        result = subprocess.run([sys.executable, '-c', self.step_body(root, name)],
            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)
        return result

    def base_env(self, root, records, env_file):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
            KDD_APPROVAL_REGISTRY=json.dumps(records),
            KDD_EXPLICIT_APPROVED_BASELINE_REF='', KDD_EXPLICIT_QUALITY_APPROVED_REF='',
            KDD_REQUIRED_EVIDENCE='', GITHUB_ENV=str(env_file))
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GITHUB_STEP_SUMMARY'):
            env.pop(name, None)
        return env

    def selected_env(self, path):
        self.assertTrue(path.is_file(), 'The selection must publish its reviewed references')
        return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines() if '=' in line)

    def test_guard_accepts_two_real_pr_merges_without_changing_main(self):
        before = self.command('git', 'rev-parse', 'HEAD')
        for number in (17, 18):
            result = self.invoke_guard(number, self.records())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS: trusted PR baseline and gate files', result.stdout)
        self.assertEqual(self.command('git', 'rev-parse', 'HEAD'), before)
        self.assertFalse((self.root / 'candidate-executed').exists())

    def test_guard_does_not_fallback_to_the_legacy_global_reference(self):
        records = self.records()
        records['trees'].pop(self.trees['one'])
        result = self.invoke_guard(17, records, KDD_APPROVED_BASELINE_REF=self.refs['one'])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('APPROVAL_UNKNOWN_TREE', result.stdout + result.stderr)

    def test_wrong_registry_baseline_fails_the_actual_guard_comparison(self):
        records = self.records()
        records['trees'][self.trees['one']]['baseline_ref'] = self.refs['main']
        result = self.invoke_guard(17, records)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('oracle differs from approved baseline', result.stdout)

    def test_candidate_owned_registry_does_not_grant_an_approval(self):
        result = self.invoke_guard(19, self.records())
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('APPROVAL_UNKNOWN_TREE', result.stdout + result.stderr)
        self.assertFalse((self.root / 'candidate-executed').exists())

    def test_selector_and_import_shadows_remain_protected_even_if_oracles_are_approved(self):
        for name in ('poison', 'shadow'):
            with self.subTest(name=name):
                findings = self.guard_findings(self.refs[name], self.refs[name])
                self.assertTrue(any('trusted gate file changed' in item or
                                    'trusted import name changed' in item for item in findings), findings)
        self.assertFalse((self.root / 'candidate-executed').exists())

    def test_actual_workflow_selection_overrides_stale_global_values(self):
        with tempfile.TemporaryDirectory(prefix='kdd-env-selection-') as directory:
            env_file = Path(directory) / 'github.env'
            records = self.records()
            records['trees'][self.trees['main']]['quality_ref'] = self.refs['main']
            env = self.base_env(self.root, records, env_file)
            env.update(KDD_APPROVED_BASELINE_REF=self.refs['two'],
                       KDD_QUALITY_APPROVED_REF=self.refs['two'])
            tools = self.root / 'scripts'
            tools.mkdir(exist_ok=True)
            shutil.copyfile(ROOT / 'scripts/approval_registry.py', tools / 'approval_registry.py')
            # Execute the real workflow body with real Git; only tool code is
            # materialized in the minimal fixture, not any candidate payload.
            result = subprocess.run([sys.executable, '-c', self.step_body(ROOT, SELECT_STEP)],
                cwd=self.root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            selected = self.selected_env(env_file)
            self.assertEqual(selected['KDD_APPROVED_BASELINE_REF'], self.refs['main'])
            self.assertEqual(selected['KDD_QUALITY_APPROVED_REF'], self.refs['main'])
            text = (ROOT / WORKFLOW).read_text(encoding='utf-8')
            self.assertLess(text.index('- name: ' + SELECT_STEP),
                            text.index('- name: Check approved contract and oracle baseline'))
            self.assertNotIn('continue-on-error:', text)

    def fresh_product(self, area):
        project = area / 'product'
        project.mkdir()
        names = self.command('git', '-C', str(ROOT), 'ls-files', '--cached',
                             '--others', '--exclude-standard', '-z').split('\0')
        for name in filter(None, names):
            source = ROOT / name
            if source.is_file():
                target = project / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        self.command(sys.executable, str(ROOT / 'scripts/bootstrap_project.py'),
                     '--repo-dir', str(project), '--apply', '--name', 'Independent product',
                     '--repository', 'ExampleCo/Independent', cwd=project)
        (project / 'src/product.py').write_text(PRODUCT, encoding='utf-8')
        (project / 'tests/product_oracle.py').write_text(ORACLE, encoding='utf-8')
        policy = {'protected': [WORKFLOW, 'scripts/verify_quality.py', 'scripts/approval_registry.py',
                               'scripts/optional_evidence.py', 'tests/product_oracle.py'],
                  'implementation': ['src/product.py'], 'pm': ['README.md'],
                  'required_kinds': ['functional', 'adversarial', 'ui'],
                  'checks': [{'name': kind, 'kind': kind if kind != 'cli' else 'ui',
                              'argv': ['python', 'tests/product_oracle.py', kind], 'timeout': 30}
                             for kind in ('functional', 'adversarial', 'cli')]}
        (project / 'quality').mkdir(exist_ok=True)
        (project / 'quality/product.json').write_text(json.dumps(policy), encoding='utf-8')
        self.command('git', 'init', '-q', '--initial-branch=main', cwd=project)
        for key, value in [('user.name', 'Simulated fixture reviewer'),
                           ('user.email', 'reviewer@example.invalid'),
                           ('commit.gpgsign', 'false'), ('core.autocrlf', 'false'),
                           ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            self.command('git', 'config', key, value, cwd=project)
        self.command('git', 'add', '.', cwd=project)
        self.command('git', 'commit', '-qm', 'Simulated reviewed project; no real approval', cwd=project)
        approved = self.command('git', 'rev-parse', 'HEAD', cwd=project)
        with (project / 'README.md').open('a', encoding='utf-8') as stream:
            stream.write('\nCandidate documentation change.\n')
        self.command('git', 'add', 'README.md', cwd=project)
        self.command('git', 'commit', '-qm', 'Candidate after baseline', cwd=project)
        tree = self.command('git', 'rev-parse', 'HEAD^{tree}', cwd=project)
        return project, approved, tree

    @unittest.skipUnless(TEMPLATE, TEMPLATE_ONLY)
    def test_initialized_project_uses_selected_refs_and_runs_real_quality_twice(self):
        with tempfile.TemporaryDirectory(prefix='kdd-routed-product-') as directory:
            area = Path(directory)
            project, approved, tree = self.fresh_product(area)
            records = {'schema_version': 1, 'trees': {tree: {'baseline_ref': approved, 'quality_ref': approved}}}
            env_file = area / 'github.env'
            env = self.base_env(project, records, env_file)
            env.update(KDD_REQUIRED_EVIDENCE='quality', KDD_QUALITY_POLICY='quality/product.json')
            selected = self.execute_step(project, SELECT_STEP, env)
            self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
            env.update(self.selected_env(env_file))
            for name in (CONFIG_STEP, QUALITY_STEP):
                result = self.execute_step(project, name, env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('SKIP', result.stdout + result.stderr)
            self.assertIn('PASS quality: integrity, perimeter and all checks verified twice', result.stdout)
            self.assertEqual(self.command('git', 'status', '--porcelain', cwd=project), '')

    @unittest.skipUnless(TEMPLATE, TEMPLATE_ONLY)
    def test_initialized_project_rejects_missing_quality_before_product_checks(self):
        with tempfile.TemporaryDirectory(prefix='kdd-routed-missing-') as directory:
            area = Path(directory)
            project, approved, tree = self.fresh_product(area)
            records = {'schema_version': 1, 'trees': {tree: {'baseline_ref': approved}}}
            env = self.base_env(project, records, area / 'github.env')
            env.update(KDD_REQUIRED_EVIDENCE='quality', KDD_QUALITY_POLICY='quality/product.json',
                       KDD_QUALITY_APPROVED_REF=approved)
            result = self.execute_step(project, SELECT_STEP, env)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('APPROVAL_QUALITY', result.stdout + result.stderr)
            text = (project / WORKFLOW).read_text(encoding='utf-8')
            self.assertLess(text.index('- name: ' + SELECT_STEP), text.index('- name: ' + CONFIG_STEP))
            self.assertNotIn('continue-on-error:', text)

    @unittest.skipUnless(TEMPLATE, TEMPLATE_ONLY)
    def test_initialized_copy_marks_only_template_bootstrap_cases_inapplicable(self):
        with tempfile.TemporaryDirectory(prefix='kdd-routed-applicability-') as directory:
            project, _, _ = self.fresh_product(Path(directory))
            self.assertFalse((project / 'src/hello.py').exists())
            names = ['tests.test_approval_routing.TestApprovalRouting.' + name for name in (
                'test_initialized_project_uses_selected_refs_and_runs_real_quality_twice',
                'test_initialized_project_rejects_missing_quality_before_product_checks',
                'test_initialized_copy_marks_only_template_bootstrap_cases_inapplicable')]
            code = (
                'import io,json,unittest\n'
                'loader=unittest.TestLoader()\n'
                'suite=loader.loadTestsFromNames(' + repr(names) + ')\n'
                'result=unittest.TextTestRunner(stream=io.StringIO()).run(suite)\n'
                'print(json.dumps(dict(tests=result.testsRun,skipped=[(c.id(),why) for c,why in result.skipped],'
                'errors=[(c.id(),why) for c,why in result.errors],'
                'failures=[(c.id(),why) for c,why in result.failures],loader_errors=loader.errors)))\n')
            result = subprocess.run([sys.executable, '-c', code], cwd=project,
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['tests'], 3)
            self.assertEqual(data['errors'], [])
            self.assertEqual(data['failures'], [])
            self.assertEqual(data['loader_errors'], [])
            self.assertEqual(sorted(data['skipped']), sorted([name, TEMPLATE_ONLY] for name in names))


if __name__ == '__main__':
    unittest.main()
