"""Bootstrap real projects and execute their generated CI with a Git fixture."""
import hashlib
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
POLICY = 'quality/product.json'
CONFIG_STEP = 'Check product quality approval configuration'
QUALITY_STEP = 'Approve project quality (when configured)'

PRODUCT = '''import sys
def double(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer required")
    return value * 2
if __name__ == "__main__":
    print(double(int(sys.argv[1])))
'''

ORACLE = '''from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from product import double
mode = sys.argv[1]
if mode == "functional":
    assert double(0) == 0 and double(3) == 6 and double(100) == 200
elif mode == "adversarial":
    for value in (-1, "3", True, None):
        try:
            double(value)
        except ValueError:
            continue
        raise AssertionError("invalid input accepted: " + repr(value))
elif mode == "cli":
    result = subprocess.run([sys.executable, "src/product.py", "3"],
                            capture_output=True, text=True, check=True)
    assert result.stdout == "6\\n" and result.stderr == ""
else:
    raise AssertionError("unknown mode")
print("PRODUCT_ORACLE:" + mode)
'''


def step_block(root, name):
    text = (root / WORKFLOW).read_text(encoding='utf-8')
    marker = '      - name: ' + name + '\n'
    if marker not in text:
        raise AssertionError('Missing generated CI step: ' + name)
    return text.split(marker, 1)[1].split('      - name:', 1)[0]


def step_body(root, name):
    return textwrap.dedent(step_block(root, name).split('        run: |\n', 1)[1])


@unittest.skipUnless((ROOT / 'src/hello.py').is_file(),
                     'template-only bootstrap integration: project already initialized')
class BootstrapProductQualityCiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='kdd-bootstrap-quality-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.area = Path(cls.directory.name)
        cls.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                       GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                    'GITHUB_STEP_SUMMARY'):
            cls.env.pop(key, None)
        cls.template = cls.area / 'template'
        cls.template.mkdir()
        names = cls.command(['git', '-C', str(ROOT), 'ls-files', '--cached',
                             '--others', '--exclude-standard', '-z']).stdout.split('\0')
        for name in filter(None, names):
            source, target = ROOT / name, cls.template / name
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        cls.base = cls.area / 'reviewed-project'
        shutil.copytree(cls.template, cls.base)
        cls.command([sys.executable, str(ROOT / 'scripts/bootstrap_project.py'),
                     '--repo-dir', str(cls.base), '--apply', '--name', 'Own product',
                     '--repository', 'ExampleCo/NewProduct'])
        cls.policy_created_by_bootstrap = (cls.base / POLICY).exists()
        (cls.base / 'src/product.py').write_text(PRODUCT, encoding='utf-8')
        (cls.base / 'tests/product_oracle.py').write_text(ORACLE, encoding='utf-8')
        (cls.base / 'quality').mkdir(exist_ok=True)
        checks = [{'name': kind, 'kind': kind if kind != 'cli' else 'ui',
                   'argv': ['python', 'tests/product_oracle.py', kind], 'timeout': 30}
                  for kind in ('functional', 'adversarial', 'cli')]
        policy = {
            'protected': [WORKFLOW, 'scripts/verify_quality.py',
                          'scripts/optional_evidence.py', 'tests/product_oracle.py'],
            'implementation': ['src/product.py'], 'pm': [],
            'required_kinds': ['functional', 'adversarial', 'ui'], 'checks': checks,
        }
        (cls.base / POLICY).write_text(json.dumps(policy), encoding='utf-8')
        cls.command(['git', 'init', '-q', '--initial-branch=main'], cwd=cls.base)
        for key, value in (('user.name', 'Simulated fixture reviewer'),
                           ('user.email', 'reviewer@example.test'),
                           ('core.autocrlf', 'false'), ('commit.gpgsign', 'false')):
            cls.command(['git', 'config', key, value], cwd=cls.base)
        cls.command(['git', 'add', '.'], cwd=cls.base)
        cls.command(['git', 'commit', '-qm', 'Reviewed test fixture; no real project approval'],
                    cwd=cls.base)
        cls.approved = cls.command(['git', 'rev-parse', 'HEAD'], cwd=cls.base).stdout.strip()

    @classmethod
    def command(cls, args, cwd=None, env=None, check=True):
        return subprocess.run(args, cwd=cwd, env=env or cls.env, capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=120, check=check)

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.area, prefix='case-')
        self.addCleanup(self.case.cleanup)
        self.root = Path(self.case.name) / 'project'
        self.command(['git', 'clone', '-q', '--shared', str(self.base), str(self.root)])

    def run_step(self, name=QUALITY_STEP, **overrides):
        env = dict(self.env, KDD_QUALITY_POLICY=POLICY,
                   KDD_QUALITY_APPROVED_REF=self.approved, KDD_REQUIRED_EVIDENCE='quality',
                   KDD_APPROVED_BASELINE_REF=self.approved,
                   KDD_CONTRACTS_DIR='knowledge/contracts')
        env.update(overrides)
        return self.command([sys.executable, '-c', step_body(self.root, name)],
                            cwd=self.root, env=env, check=False)

    def assert_rejected(self, result, reason=None):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('PASS quality:', result.stdout)
        if reason:
            self.assertIn(reason.lower(), (result.stdout + result.stderr).lower())

    def fresh_template(self, name):
        target = Path(self.case.name) / name
        shutil.copytree(self.template, target)
        return target

    @staticmethod
    def snapshot(root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file()}

    def test_generated_defaults_and_all_profile_guides(self):
        text = (self.root / WORKFLOW).read_text(encoding='utf-8')
        self.assertIn("quality_policy_path:\n        type: string\n        default: 'quality/product.json'", text)
        self.assertIn("required_evidence:\n        type: string\n        default: 'quality'", text)
        self.assertEqual(text.count("inputs.quality_policy_path || 'quality/product.json'"), 2)
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'), 2)
        self.assertEqual(text.count('run: python scripts/run_test_suite.py --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS"'), 2)
        self.assertIn('KDD_QUALITY_OUTCOME: ', text)
        self.assertIn('vars.KDD_QUALITY_APPROVED_REF', text.split('    steps:', 1)[0])
        self.assertLess(text.index('- name: ' + CONFIG_STEP),
                        text.index("- name: Run each contract's test_command"))
        self.assertIn('- name: Validate Git task snapshots and transitions', text)
        self.assertIn('--deduplicate', text)
        self.assertNotIn('continue-on-error:', text)
        self.assertFalse(self.policy_created_by_bootstrap)
        self.assertEqual(list((self.root / 'knowledge/tasks').glob('TASK-*.md')), [])
        self.assertEqual(list((self.root / 'docs/task-evidence').glob('*.json')), [])
        sys.path.insert(0, str(ROOT / 'scripts'))
        import bootstrap_project
        for profile in ('minimal', 'standard', 'strict'):
            with self.subTest(profile=profile):
                guide = bootstrap_project._start_here('Own product', profile)
                self.assertIn('quality/product.json', guide)
                self.assertIn('KDD_QUALITY_APPROVED_REF', guide)
                self.assertIn('KDD_APPROVED_BASELINE_REF', guide)
                if profile == 'minimal':
                    self.assertNotIn('--approved-ref', guide)

    def test_api_and_direct_init_cli_configure_ci_and_preserve_own_policy(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import bootstrap_project
        source_before = (ROOT / WORKFLOW).read_bytes()
        for mode in ('api', 'init-cli'):
            with self.subTest(mode=mode):
                root = self.fresh_template(mode)
                own = root / POLICY
                own.parent.mkdir(exist_ok=True)
                own.write_bytes(b'{"own_policy":"preserve byte for byte"}\n')
                if mode == 'api':
                    result = bootstrap_project.bootstrap_project(
                        str(root), True, 'Own product', 'standard', 'ExampleCo/NewProduct')
                    self.assertTrue(result.get('quality_ci_configured'), result)
                else:
                    self.command([sys.executable, str(ROOT / 'scripts/init_project.py'),
                                  '--repo-dir', str(root), '--apply',
                                  '--repository', 'ExampleCo/NewProduct'])
                self.assertEqual(own.read_bytes(), b'{"own_policy":"preserve byte for byte"}\n')
                self.assertIn('quality/product.json', (root / WORKFLOW).read_text(encoding='utf-8'))
                self.assertEqual((root / WORKFLOW).read_bytes(), (self.base / WORKFLOW).read_bytes())
        self.assertEqual((ROOT / WORKFLOW).read_bytes(), source_before)

    def test_dry_run_is_read_only_and_reports_quality_plan(self):
        root = self.fresh_template('dry-run')
        before = self.snapshot(root)
        result = self.command([sys.executable, str(ROOT / 'scripts/init_project.py'),
                               '--repo-dir', str(root)])
        self.assertIn('quality/product.json', result.stdout)
        self.assertEqual(self.snapshot(root), before)

    def test_workflow_preflight_failure_does_not_delete_or_write(self):
        for mode in ('missing', 'incompatible', 'ambiguous'):
            with self.subTest(mode=mode):
                root = self.fresh_template('bad-' + mode)
                path = root / WORKFLOW
                if mode == 'missing':
                    path.unlink()
                else:
                    text = path.read_text(encoding='utf-8')
                    if mode == 'incompatible':
                        text = text.replace(QUALITY_STEP, 'Different custom approval')
                    else:
                        text += '\n      - name: ' + QUALITY_STEP + '\n'
                    path.write_text(text, encoding='utf-8')
                before = self.snapshot(root)
                result = self.command([sys.executable, str(ROOT / 'scripts/bootstrap_project.py'),
                                       '--repo-dir', str(root), '--apply',
                                       '--repository', 'ExampleCo/NewProduct'], check=False)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(self.snapshot(root), before)

    def test_lf_and_crlf_are_supported_without_unrelated_step_changes(self):
        source = (self.template / WORKFLOW).read_text(encoding='utf-8')
        expected = (self.base / WORKFLOW).read_text(encoding='utf-8')
        for newline in ('\n', '\r\n'):
            with self.subTest(newline=repr(newline)):
                root = self.fresh_template('newline-' + str(len(newline)))
                (root / WORKFLOW).write_bytes(source.replace('\n', newline).encode('utf-8'))
                self.command([sys.executable, str(ROOT / 'scripts/init_project.py'),
                              '--repo-dir', str(root), '--apply',
                              '--repository', 'ExampleCo/NewProduct'])
                self.assertEqual((root / WORKFLOW).read_bytes(),
                                 expected.replace('\n', newline).encode('utf-8'))
        for name in ("Run each contract's test_command", 'Check approved contract and oracle baseline'):
            self.assertEqual(step_block(self.template, name), step_block(self.base, name))

    def test_actual_generated_ci_accepts_reviewed_product_twice_and_reports_pass(self):
        configured = self.run_step(CONFIG_STEP)
        self.assertEqual(configured.returncode, 0, configured.stdout + configured.stderr)
        baseline = self.run_step('Check approved contract and oracle baseline')
        self.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
        result = self.run_step()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS quality: integrity, perimeter and all checks verified twice', result.stdout)
        for name, kind in (('functional', 'functional'), ('adversarial', 'adversarial'), ('cli', 'ui')):
            for iteration in (1, 2):
                self.assertIn('RUN %s/2 %s [%s]' % (iteration, name, kind), result.stdout)
            self.assertEqual(result.stdout.count('PRODUCT_ORACLE:' + name), 2)
        env = dict(self.env, KDD_QUALITY_POLICY=POLICY, KDD_REQUIRED_EVIDENCE='quality',
                   KDD_QUALITY_OUTCOME='success')
        summary = self.command([sys.executable, 'scripts/optional_evidence.py', 'summary',
                                '--layers', 'quality'], cwd=self.root, env=env)
        self.assertIn('PASS [quality] quality/product.json', summary.stdout.replace('\\', '/'))
        self.assertNotIn('SKIP [quality]', summary.stdout)
        self.assertEqual(self.command(['git', 'rev-list', '--count', 'HEAD'],
                                     cwd=self.root).stdout.strip(), '1')

    def test_missing_policy_or_invalid_approval_cannot_skip_generated_ci(self):
        for ref in ('', 'HEAD', 'main', 'f' * 40):
            with self.subTest(ref=ref):
                self.assert_rejected(self.run_step(CONFIG_STEP, KDD_QUALITY_APPROVED_REF=ref))
        self.command(['git', 'config', 'user.name', 'Fixture reviewer'], cwd=self.root)
        self.command(['git', 'config', 'user.email', 'reviewer@example.test'], cwd=self.root)
        tree = self.command(['git', 'rev-parse', 'HEAD^{tree}'], cwd=self.root).stdout.strip()
        orphan = self.command(['git', 'commit-tree', tree, '-m', 'Unrelated review'],
                              cwd=self.root).stdout.strip()
        self.assert_rejected(self.run_step(CONFIG_STEP, KDD_QUALITY_APPROVED_REF=orphan))
        (self.root / POLICY).unlink()
        self.assert_rejected(self.run_step(CONFIG_STEP), 'policy')

    def test_candidate_runner_cannot_fake_pass(self):
        (self.root / 'scripts/verify_quality.py').write_text('print("FAKE_PRODUCT_PASS")\n',
                                                            encoding='utf-8')
        result = self.run_step()
        self.assert_rejected(result, 'protected')
        self.assertNotIn('FAKE_PRODUCT_PASS', result.stdout)

    def test_policy_oracle_and_workflow_tampering_are_rejected(self):
        for name in (POLICY, 'tests/product_oracle.py', WORKFLOW):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b'\n ')
                self.assert_rejected(self.run_step(), 'protected')
                path.write_bytes(original)

    def test_outside_committed_files_are_rejected(self):
        (self.root / 'src/undeclared.py').write_text('unexpected = True\n', encoding='utf-8')
        self.command(['git', 'config', 'user.name', 'Fixture developer'], cwd=self.root)
        self.command(['git', 'config', 'user.email', 'developer@example.test'], cwd=self.root)
        self.command(['git', 'add', 'src/undeclared.py'], cwd=self.root)
        self.command(['git', 'commit', '-qm', 'Unauthorized fixture implementation'], cwd=self.root)
        self.assert_rejected(self.run_step(), 'outside approved perimeter')

    def test_current_product_failure_is_not_approved(self):
        path = self.root / 'src/product.py'
        path.write_text(PRODUCT.replace('value * 2', 'value * 3'), encoding='utf-8')
        self.assert_rejected(self.run_step(), 'Check failed: functional')


if __name__ == '__main__':
    unittest.main()
