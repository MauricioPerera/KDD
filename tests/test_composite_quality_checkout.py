"""Exercise the composite's real checkout and quality steps with local Git."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.test_fixture_preparation import configure_git, directory_alias

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / '.github/actions/validate-contracts/action.yml'
OFFICIAL_URL = 'https://github.com/MauricioPerera/KDD'


class CompositeQualityCheckout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix='kdd composite ')
        cls.addClassCleanup(temp.cleanup)
        cls.area = Path(temp.name)
        cls.tooling = cls.area / 'tools'
        cls.tooling.mkdir()
        cls.git(cls.tooling, 'init', '-q')
        configure_git(cls.tooling, {'user.name': 'KDD fixture', 'user.email': 'fixture@example.invalid',
                                    'core.autocrlf': 'false'}, ephemeral=True)
        (cls.tooling / 'scripts').mkdir()
        for name in ('verify_quality.py', 'oracle_inventory.py', 'process_tree.py', 'validate_contracts.py', 'optional_evidence.py'):
            shutil.copyfile(ROOT / 'scripts' / name, cls.tooling / 'scripts' / name)
        cls.tooling_ref = cls.commit(cls.tooling, 'Pinned tool fixture')
        (cls.tooling / 'scripts/verify_quality.py').write_text('raise SystemExit(17)\n', encoding='utf-8')
        cls.commit(cls.tooling, 'Newer tool fixture must not be selected')
        cls.steps = {step['name']: step for step in yaml.safe_load(ACTION.read_text(encoding='utf-8'))['runs']['steps']}
        git = Path(shutil.which('git')).resolve()
        cls.bash = git.parent.parent / 'bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        if not cls.bash or not Path(cls.bash).is_file():
            raise RuntimeError('The composite action integration requires Git Bash')

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], encoding='utf-8',
                                       stderr=subprocess.PIPE, timeout=30).strip()

    @classmethod
    def commit(cls, root, message):
        cls.git(root, 'add', '.')
        cls.git(root, 'commit', '-qm', message)
        return cls.git(root, 'rev-parse', 'HEAD')

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='case ', dir=self.area)
        self.addCleanup(temp.cleanup)
        self.scratch = Path(temp.name)
        self.consumer = self.scratch / 'consumer repo'
        self.runner_temp = self.scratch / 'runner temp'
        self.consumer.mkdir()
        self.runner_temp.mkdir()
        self.git(self.consumer, 'init', '-q')
        configure_git(self.consumer, {'user.name': 'KDD consumer', 'user.email': 'fixture@example.invalid',
                                       'core.autocrlf': 'false'}, ephemeral=True)
        (self.consumer / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/process_tree.py', self.consumer / 'scripts/process_tree.py')
        (self.consumer / 'oracle.py').write_text(
            "from pathlib import Path\n"
            "marker = Path('rounds.txt')\n"
            "marker.write_text((marker.read_text() if marker.exists() else '') + 'x')\n",
            encoding='utf-8')
        contracts = self.consumer / 'project contracts'
        contracts.mkdir()
        oracle = self.consumer / 'oracle.py'
        seal = sha256(oracle.read_text(encoding='utf-8').encode()).hexdigest()
        (contracts / 'caller.md').write_text(
            "---\ntype: 'Task Contract'\ntitle: 'Caller contract'\ndescription: 'Caller test'\n"
            "tags: ['fixture']\ntask: caller\nintent: 'Validate the caller oracle'\n"
            "target: oracle.py\nsignature: 'def oracle():'\n"
            "test_command: 'python oracle.py'\nbudget:\n  cyclomatic_max: 4\n  nesting_max: 2\n"
            "tests: oracle.py\ntests_sha256: '" + seal + "'\n"
            "touch_only: ['oracle.py']\ndeps_allowed: ['stdlib']\nforbids: ['network']\n---\n"
            "## Intent\nFixture.\n## Interface\nFixture.\n## Invariants\nFixture.\n"
            "## Examples\nFixture.\n## Do / Don't\nFixture.\n## Tests\nFixture.\n"
            "## Constraints\nPARAR y reportar si falta el oraculo.\n",
            encoding='utf-8')
        self.policy = {
            'protected': ['oracle.py', 'scripts/process_tree.py'],
            'implementation': [], 'pm': ['rounds.txt'],
            'required_kinds': ['functional', 'adversarial'],
            'checks': [
                {'name': 'functional', 'kind': 'functional', 'argv': [sys.executable, 'oracle.py'], 'timeout': 10},
                {'name': 'adversarial', 'kind': 'adversarial',
                 'argv': [sys.executable, '-c', 'assert 7 != 9'], 'timeout': 10},
            ],
        }
        (self.consumer / 'quality.json').write_text(json.dumps(self.policy), encoding='utf-8')
        self.ref = self.commit(self.consumer, 'Approved consumer')
        self.output = self.scratch / 'github-output'
        self.env = dict(os.environ, PYTHONUTF8='1', GIT_CONFIG_COUNT='1', GIT_ALLOW_PROTOCOL='file',
                        GIT_CONFIG_KEY_0='url.' + self.tooling.resolve().as_uri() + '.insteadOf',
                        GIT_CONFIG_VALUE_0=OFFICIAL_URL + '.git',
                        GITHUB_OUTPUT=str(self.output), GITHUB_WORKSPACE=str(self.consumer),
                        RUNNER_TEMP=str(self.runner_temp), KDD_REF=self.tooling_ref,
                        KDD_QUALITY_POLICY='quality.json', KDD_QUALITY_APPROVED_REF=self.ref,
                        KDD_CONTRACTS_DIR='project contracts')
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')

    def run_step(self, name):
        step = self.steps[name]
        env = dict(self.env)
        binding = step.get('env', {}).get('KDD_TOOLING_ROOT')
        if binding is not None:
            step_id = self.steps['Check out KDD tooling repo']['id']
            self.assertEqual(binding, '${{ steps.' + step_id + '.outputs.root }}')
            env['KDD_TOOLING_ROOT'] = str(self.tools_root)
        return subprocess.run([str(self.bash), '--noprofile', '--norc', '-e', '-o', 'pipefail',
                               '-c', step['run']], cwd=self.consumer, env=env,
                              capture_output=True, text=True, encoding='utf-8', timeout=45)

    def install_tools(self):
        name = 'Check out KDD tooling repo'
        step = self.steps[name]
        if 'run' in step:
            result = self.run_step(name)
            if result.returncode == 0:
                rows = dict(line.split('=', 1) for line in self.output.read_text(encoding='utf-8').splitlines())
                self.assertIn('root', rows)
                self.tools_root = Path(rows['root'])
            return result
        # Before the change checkout v7 ran on the consumer's relative path.
        # Reproduce that step with an actual checkout at the pinned object.
        nested = self.consumer / step['with']['path']
        result = subprocess.run(['git', 'clone', '-q', '--no-checkout', str(self.tooling), str(nested)],
                                cwd=self.consumer, env=self.env, capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        if result.returncode == 0:
            self.git(nested, 'checkout', '-q', '--detach', self.env['KDD_REF'])
            self.tools_root = nested
        return result

    def quality(self):
        return self.run_step('Approve project quality (when configured)')

    def assert_tools_installed(self):
        result = self.install_tools()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        root = self.tools_root.resolve()
        self.assertEqual(self.git(root, 'rev-parse', 'HEAD'), self.tooling_ref)
        return root

    def test_action_keeps_tools_outside_consumer_and_executes_quality_twice(self):
        root = self.assert_tools_installed()
        validation = self.run_step('Validate contracts (REQUIRED)')
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.assertIn('1 archivo(s)', validation.stdout)
        result = self.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.consumer / 'rounds.txt').read_text(), 'xx')
        self.assertTrue(root.is_relative_to(self.runner_temp.resolve()))
        self.assertFalse(root.is_relative_to(self.consumer.resolve()))
        self.assertEqual(self.git(self.consumer, 'status', '--porcelain'), '?? rounds.txt')

    def test_existing_consumer_kdd_path_is_preserved(self):
        directory = self.consumer / '_kdd'
        directory.mkdir()
        file = directory / 'product.txt'
        file.write_bytes(b'consumer bytes')
        self.ref = self.commit(self.consumer, 'Consumer-owned directory')
        self.env['KDD_QUALITY_APPROVED_REF'] = self.ref
        self.assert_tools_installed()
        result = self.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(file.read_bytes(), b'consumer bytes')
        self.assertEqual(self.git(self.consumer, 'status', '--porcelain'), '?? rounds.txt')

    def test_out_of_perimeter_file_remains_a_failure(self):
        self.assert_tools_installed()
        (self.consumer / 'outside.py').write_text('x = 1\n', encoding='utf-8')
        result = self.quality()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('outside.py', result.stdout + result.stderr)
        self.assertFalse((self.consumer / 'rounds.txt').exists())

    def test_runner_temp_inside_consumer_is_rejected_without_writes(self):
        nested = self.consumer / 'nested'
        nested.mkdir()
        alias = self.scratch / 'alias'
        directory_alias(alias, nested, self.scratch)
        for location in (self.consumer, nested, alias):
            with self.subTest(location=location):
                self.env['RUNNER_TEMP'] = str(location)
                result = self.install_tools()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.git(self.consumer, 'status', '--porcelain'), '')
                self.assertFalse(self.output.exists())
                self.assertEqual(list(nested.iterdir()), [])

    def test_all_script_steps_take_the_checkout_output_from_yaml(self):
        checkout = self.steps['Check out KDD tooling repo']
        self.assertIn('id', checkout)
        binding = '${{ steps.' + checkout['id'] + '.outputs.root }}'
        validators = {name: step for name, step in self.steps.items()
                      if '/scripts/' in step.get('run', '')}
        self.assertIn('Approve project quality (when configured)', validators)
        self.assertIn('Validate contracts (REQUIRED)', validators)
        self.assertIn("Run each contract's test_command (OPTIONAL — gated by run-test-commands)", validators)
        self.assertIn('Summarize optional evidence', validators)
        for name, step in validators.items():
            with self.subTest(step=name):
                self.assertEqual(step.get('env', {}).get('KDD_TOOLING_ROOT'), binding)
                self.assertIn('"$KDD_TOOLING_ROOT/scripts/', step['run'])
                self.assertNotIn('_kdd/scripts/', step['run'])
        self.assertIn('steps.' + checkout['id'] + ".outcome == 'success'",
                      self.steps['Summarize optional evidence']['if'])

    def test_missing_approval_or_consumer_helper_never_executes_checks(self):
        self.assert_tools_installed()
        self.env['KDD_QUALITY_APPROVED_REF'] = ''
        missing_ref = self.quality()
        self.assertNotEqual(missing_ref.returncode, 0)
        self.assertIn('quality-approved-ref', missing_ref.stdout + missing_ref.stderr)
        (self.consumer / 'scripts/process_tree.py').unlink()
        self.env['KDD_QUALITY_APPROVED_REF'] = self.commit(self.consumer, 'Policy without approved helper')
        missing_helper = self.quality()
        self.assertNotEqual(missing_helper.returncode, 0)
        self.assertIn('scripts/process_tree.py', (missing_helper.stdout + missing_helper.stderr).replace('\\', '/'))
        self.assertFalse((self.consumer / 'rounds.txt').exists())

    def test_unavailable_pin_fails_before_quality(self):
        self.env['KDD_REF'] = '0' * 40
        if 'run' not in self.steps['Check out KDD tooling repo']:
            # The hosted checkout already rejects a missing Git object.
            result = subprocess.run(['git', '-C', str(self.tooling), 'cat-file', '-e', self.env['KDD_REF']],
                                    capture_output=True, timeout=30)
        else:
            result = self.install_tools()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.consumer / 'rounds.txt').exists())

    def test_missing_optional_quality_stays_skip(self):
        self.assert_tools_installed()
        self.env.update(KDD_QUALITY_POLICY='absent.json', KDD_QUALITY_APPROVED_REF='')
        result = self.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SKIP:', result.stdout)


if __name__ == '__main__':
    unittest.main()
