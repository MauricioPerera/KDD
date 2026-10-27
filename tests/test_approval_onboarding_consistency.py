"""Onboarding entries and actual bootstrap/selector/product-quality execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = '.github/workflows/validate.yml'


def environment():
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME='Onboarding fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
        GIT_COMMITTER_NAME='Onboarding fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                'PYTHONPATH', 'GITHUB_STEP_SUMMARY', 'NODE_TEST_CONTEXT', 'KDD_BOARD_TOKEN'):
        env.pop(key, None)
    return env


def command(root, args, env=None):
    return subprocess.run(args, cwd=root, env=env or environment(),
        capture_output=True, text=True, encoding='utf-8', timeout=120)


def git(root, *args):
    result = command(root, ['git', '-C', str(root), *args])
    if result.returncode:
        raise AssertionError('Real Git fixture failed: ' + repr(args) + '\n' + result.stderr)
    return result.stdout.strip()


class ApprovalOnboardingDocs(unittest.TestCase):
    def entry(self, marker):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn(marker, text)
        return text.split(marker, 1)[1].split('\n\n', 1)[0]

    def registry_entry(self, marker):
        entry = self.entry(marker)
        self.assertIn('KDD_APPROVAL_REGISTRY', entry)
        self.assertIn('knowledge/approval-registry.md', entry)
        self.assertNotIn('`KDD_APPROVED_BASELINE_REF`', entry,
            'global selected output is not the native onboarding configuration')
        self.assertNotIn('`KDD_QUALITY_APPROVED_REF`', entry)

    def test_english_entry_configures_the_tree_registry(self):
        self.registry_entry('Both initialization commands configure')

    def test_spanish_entry_configures_the_tree_registry(self):
        self.registry_entry('Ambas entradas configuran')

    def test_portuguese_entry_configures_the_tree_registry(self):
        self.registry_entry('Ambas as entradas configuram')

    def test_canonical_validation_points_to_current_external_selection(self):
        text = (ROOT / 'knowledge/validacion.md').read_text(encoding='utf-8')
        self.assertIn('KDD_APPROVAL_REGISTRY', text)
        self.assertIn('approval-registry.md', text)
        self.assertIn('approved_baseline_ref', text)

    def test_trust_guarantees_explain_registry_and_reusable_inputs(self):
        text = (ROOT / 'knowledge/verification-guarantees.md').read_text(encoding='utf-8')
        self.assertIn('KDD_APPROVAL_REGISTRY', text)
        self.assertIn('approval-registry.md', text)
        self.assertIn('approved_baseline_ref', text)

    def test_generated_guide_retains_registry_for_all_profiles(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import bootstrap_project
        for profile in ('minimal', 'standard', 'strict'):
            with self.subTest(profile=profile):
                guide = bootstrap_project._start_here('Own product', profile)
                self.assertIn('KDD_APPROVAL_REGISTRY', guide)
                self.assertIn('knowledge/approval-registry.md', guide)
                self.assertIn('quality/product.json', guide)


class ApprovalOnboardingIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.area = tempfile.TemporaryDirectory(prefix='kdd-onboarding-real-')
        cls.addClassCleanup(cls.area.cleanup)
        cls.base = Path(cls.area.name) / 'base product-\u00f1'
        cls.base.mkdir()
        if (ROOT / '.git').exists():
            files = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z'],
                env=environment(), timeout=30).decode('utf-8').split('\0')
        else:
            files = []
            for current, directories, names in os.walk(ROOT):
                relative = Path(current).relative_to(ROOT)
                directories[:] = [name for name in directories
                    if name not in {'.git', 'node_modules', '__pycache__', '.audit'}
                    and (relative / name).as_posix() != '.agents/logs']
                files.extend((relative / name).as_posix() for name in names
                             if not (Path(current) / name).is_symlink())
        for name in filter(None, files):
            source = ROOT / name
            if source.is_file():
                target = cls.base / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        if (cls.base / 'src/hello.py').is_file():
            p = command(cls.base, [sys.executable, 'scripts/bootstrap_project.py', '--apply',
                '--repo-dir', str(cls.base), '--name', 'Own onboarding product',
                '--profile', 'minimal', '--repository', 'ExampleCo/Onboarding'])
            if p.returncode:
                raise AssertionError('Bootstrap failed before configuration test: ' + p.stdout + p.stderr)
        # An initialized copy already contains the adapted workflow: exercise
        # the same selector/product checks without attempting another init.
        text = (cls.base / WORKFLOW).read_text(encoding='utf-8')
        if 'Check product quality approval configuration' not in text:
            raise AssertionError('Actual initialized workflow lacks mandatory product configuration')
        for folder in ('src', 'tests', 'quality'):
            (cls.base / folder).mkdir(exist_ok=True)
        (cls.base / 'src/__init__.py').write_text('', encoding='utf-8')
        (cls.base / 'tests/__init__.py').write_text('', encoding='utf-8')
        (cls.base / 'src/onboarding_value.py').write_text(
            'def value(item):\n    if type(item) is not int:\n        raise ValueError("integer required")\n    return item * 2\n',
            encoding='utf-8')
        (cls.base / 'tests/test_onboarding_own.py').write_text('''import unittest
from pathlib import Path
from src.onboarding_value import value
class OwnOnboarding(unittest.TestCase):
    def setUp(self):
        p=Path('.audit/checks');p.parent.mkdir(exist_ok=True)
        p.write_text(p.read_text()+'x' if p.exists() else 'x')
    def test_functional(self):
        self.assertEqual(value(4),8)
    def test_adversarial(self):
        with self.assertRaises(ValueError):value(True)
''', encoding='utf-8')
        policy = dict(protected=[WORKFLOW, 'scripts/verify_quality.py', 'scripts/process_tree.py',
            'tests/test_onboarding_own.py', 'tests/__init__.py', 'src/__init__.py'],
            implementation=['src/onboarding_value.py'], pm=[],
            required_kinds=['functional', 'adversarial'], checks=[
                dict(name=kind, kind=kind, argv=[sys.executable, '-m', 'unittest',
                    'tests.test_onboarding_own.OwnOnboarding.test_' + kind], timeout=15)
                for kind in ['functional', 'adversarial']])
        (cls.base / 'quality/product.json').write_text(json.dumps(policy), encoding='utf-8')
        ignore = cls.base / '.gitignore'
        ignore.write_text((ignore.read_text(encoding='utf-8') if ignore.exists() else '') + '\n.audit/\n', encoding='utf-8')
        git(cls.base, 'init', '-q', '-b', 'main')
        for key, value in [('core.autocrlf', 'false'), ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            git(cls.base, 'config', key, value)
        git(cls.base, 'add', '.')
        git(cls.base, 'commit', '-qm', 'Synthetic onboarding fixture, no real approval')
        cls.ref = git(cls.base, 'rev-parse', 'HEAD')
        cls.tree = git(cls.base, 'rev-parse', 'HEAD^{tree}')

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(prefix='kdd-onboarding-case-')
        self.addCleanup(self.case.cleanup)
        self.root = Path(self.case.name) / 'own project'
        git(self.base, 'clone', '-q', '--shared', '--branch', 'main', str(self.base), str(self.root))
        for key in ('maintenance.autoDetach', 'gc.autoDetach'):
            git(self.root, 'config', key, 'false')
        self.output = Path(self.case.name) / 'selected.env'

    def run_step(self, name, registry=None, **changes):
        text = (self.root / WORKFLOW).read_text(encoding='utf-8')
        step = text.split('      - name: ' + name + '\n', 1)[1].split('\n      - ', 1)[0]
        body = textwrap.dedent(step.split('        run: |\n', 1)[1])
        env = dict(environment(), KDD_REQUIRED_EVIDENCE='quality', KDD_QUALITY_POLICY='quality/product.json',
            KDD_APPROVAL_REGISTRY=json.dumps(registry) if registry is not None else '',
            KDD_EXPLICIT_APPROVED_BASELINE_REF='', KDD_EXPLICIT_QUALITY_APPROVED_REF='',
            KDD_APPROVED_BASELINE_REF=self.ref, KDD_QUALITY_APPROVED_REF=self.ref,
            GITHUB_ENV=str(self.output))
        env.update(changes)
        return command(self.root, [sys.executable, '-c', body], env)

    def record(self, quality=True, tree=None):
        row = dict(baseline_ref=self.ref)
        if quality:
            row['quality_ref'] = self.ref
        return dict(schema_version=1, trees={tree or self.tree: row})

    def assert_no_product_run(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / '.audit/checks').exists())
        self.assertNotIn('PASS quality:', result.stdout)

    def test_registered_tree_runs_actual_product_quality_twice(self):
        selected = self.run_step('Select approved references', self.record())
        self.assertEqual(selected.returncode, 0, selected.stdout + selected.stderr)
        data = json.loads(selected.stdout)
        self.assertEqual(data['candidate_tree'], self.tree)
        self.assertEqual(data['baseline_ref'], self.ref)
        self.assertEqual(data['quality_ref'], self.ref)
        self.assertEqual(data['source'], 'registry')
        values = dict(line.split('=', 1) for line in self.output.read_text(encoding='utf-8').splitlines())
        self.assertEqual(values['KDD_APPROVED_BASELINE_REF'], self.ref)
        self.assertEqual(values['KDD_QUALITY_APPROVED_REF'], self.ref)
        check = self.run_step('Check product quality approval configuration', self.record(), **values)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        result = self.run_step('Approve project quality (when configured)', self.record(), **values)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS quality:', result.stdout)
        self.assertEqual(result.stdout.count('RUN '), 4)
        self.assertEqual((self.root / '.audit/checks').read_text(), 'xxxx')
        self.assertEqual(git(self.root, 'status', '--porcelain'), '')

    def test_legacy_global_variables_do_not_supply_native_approval(self):
        result = self.run_step('Select approved references')
        self.assert_no_product_run(result)
        self.assertIn('APPROVAL_REQUIRED', result.stderr)
        self.assertFalse(self.output.exists())

    def test_unknown_tree_rejects_before_product_checks(self):
        result = self.run_step('Select approved references', self.record(tree='f' * 40))
        self.assert_no_product_run(result)
        self.assertIn('APPROVAL_UNKNOWN_TREE', result.stderr)

    def test_missing_quality_entry_does_not_use_legacy_quality_variable(self):
        result = self.run_step('Select approved references', self.record(quality=False))
        self.assert_no_product_run(result)
        self.assertIn('APPROVAL_QUALITY', result.stderr)

    def test_reusable_explicit_mode_still_resolves_reviewed_refs(self):
        result = self.run_step('Select approved references',
            KDD_EXPLICIT_APPROVED_BASELINE_REF=self.ref, KDD_EXPLICIT_QUALITY_APPROVED_REF=self.ref)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        selected = json.loads(result.stdout)
        self.assertEqual(selected['source'], 'explicit')
        self.assertEqual(selected['baseline_ref'], self.ref)
        self.assertEqual(selected['quality_ref'], self.ref)

    def test_registry_and_explicit_modes_cannot_be_mixed(self):
        result = self.run_step('Select approved references', self.record(),
            KDD_EXPLICIT_APPROVED_BASELINE_REF=self.ref)
        self.assert_no_product_run(result)
        self.assertIn('APPROVAL_AMBIGUOUS', result.stderr)


class ApprovalOnboardingSourceCopy(unittest.TestCase):
    def test_initialized_source_without_git_runs_all_six_workflow_cases(self):
        with tempfile.TemporaryDirectory(prefix='kdd-onboarding-no-git-') as directory:
            source = Path(directory)
            for folder in ('.github/workflows', 'scripts', 'tests'):
                (source / folder).mkdir(parents=True)
            workflow = (ROOT / WORKFLOW).read_text(encoding='utf-8')
            if 'Check product quality approval configuration' not in workflow:
                sys.path.insert(0, str(ROOT / 'scripts'))
                import init_project
                workflow = init_project._product_quality_ci(ROOT).decode('utf-8')
            (source / WORKFLOW).write_text(workflow, encoding='utf-8')
            for name in ('approval_registry.py', 'verify_quality.py', 'process_tree.py'):
                shutil.copyfile(ROOT / 'scripts' / name, source / 'scripts' / name)
            shutil.copyfile(Path(__file__), source / 'tests/test_approval_onboarding_consistency.py')
            (source / 'tests/__init__.py').write_text('', encoding='utf-8')
            (source / '.gitignore').write_text('__pycache__/\n.audit/\n', encoding='utf-8')
            self.assertFalse((source / '.git').exists())
            result = command(source, [sys.executable, '-m', 'unittest',
                'tests.test_approval_onboarding_consistency.ApprovalOnboardingIntegration', '-v'])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Ran 6 tests', result.stderr)
            self.assertIn('\nOK', result.stderr)
            self.assertNotIn('skipped=', result.stderr)
            self.assertFalse((source / '.git').exists(), 'source must remain an initialized copy without Git')


if __name__ == '__main__':
    unittest.main()
