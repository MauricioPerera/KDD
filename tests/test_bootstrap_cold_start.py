"""Actual generated preparation commands with an empty cache and official archive."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import unittest
from tests import test_bootstrap_boundary as support


@unittest.skipUnless(support.IS_TEMPLATE, 'template-only bootstrap integration: project already initialized')
class BootstrapColdStart(support.SandboxFixture):
    def initialize(self, profile='minimal', root=None):
        root = root or self.root
        p = self.cli('bootstrap_project.py', root, extra=['--profile', profile])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return (root / 'KDD-START-HERE.md').read_text(encoding='utf-8')

    def setup_command(self, guide):
        commands = [line.strip() for line in guide.splitlines()
                    if line.strip().startswith('python scripts/validate_workflows.py install')]
        self.assertEqual(len(commands), 1, 'Guide must prepare the reviewed tool explicitly')
        self.assertEqual(commands[0], 'python scripts/validate_workflows.py install')
        return commands[0].split()

    def cold_environment(self):
        env = dict(self.env)
        for key in list(env):
            if key.startswith('KDD_ACTIONLINT_'):
                env.pop(key)
        # Keep an intentionally explicit interpreter/Git/Node path, without the
        # reviewed tool's parent even when a caller installed it elsewhere.
        binary = self.env.get('KDD_ACTIONLINT_BINARY') or shutil.which('actionlint.exe' if os.name == 'nt' else 'actionlint')
        excluded = str(Path(binary).parent).casefold() if binary else None
        env['PATH'] = os.pathsep.join(p for p in env['PATH'].split(os.pathsep)
                                      if p.casefold() != excluded and 'actionlint' not in p.casefold())
        empty = self.area / 'fresh runner temp'
        empty.mkdir()
        for key in ('TMPDIR', 'TEMP', 'TMP'):
            env[key] = str(empty)
        self.assertIsNone(shutil.which('actionlint.exe' if os.name == 'nt' else 'actionlint', path=env['PATH']))
        self.assertEqual(list(empty.iterdir()), [])
        self.assertFalse(any(k.startswith('KDD_ACTIONLINT_') for k in env))
        return env, empty

    def reviewed_archive(self):
        pins = json.loads((self.root / 'tools/workflow-syntax/actionlint.json').read_text(encoding='utf-8'))
        system = 'windows' if os.name == 'nt' else ('darwin' if sys.platform == 'darwin' else 'linux')
        machine = {'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}[platform.machine().lower()]
        key = system + '_' + machine
        pin = pins['platforms'][key]
        selected = self.env.get('KDD_ACTIONLINT_BINARY') or shutil.which(pin['executable'])
        binary = (Path(selected) if selected else Path(tempfile.gettempdir()) / 'kdd-actionlint'
                  / pins['version'] / key / pin['executable'])
        package = Path(self.env.get('KDD_ACTIONLINT_ARCHIVE', str(binary.parent / pin['archive'])))
        self.assertTrue(package.is_file(), 'Provide the reviewed official archive as offline fixture data')
        raw = package.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pin['archive_sha256'])
        archive = self.area / pin['archive']
        archive.write_bytes(raw)
        return archive, pin

    def test_all_generated_profiles_prepare_tool_before_profile(self):
        for index, profile in enumerate(['minimal', 'standard', 'strict']):
            with self.subTest(profile=profile):
                root = self.root if index == 0 else self.new_project(profile)
                guide = self.initialize(profile, root)
                self.setup_command(guide)
                self.assertLess(guide.index('python scripts/validate_workflows.py install'),
                                guide.index('python scripts/run_profile.py'))
                self.assertIn('--archive', guide)
                if profile == 'minimal':
                    self.assertNotIn('--approved-ref', guide)
                else:
                    self.assertIn('--approved-ref <SHA_APROBADO>', guide)

    def test_quickstart_prepares_tool_before_first_suite(self):
        text = (support.ROOT / 'knowledge/quickstart.md').read_text(encoding='utf-8')
        command = 'python scripts/validate_workflows.py install'
        self.assertIn(command, text)
        self.assertLess(text.index(command), text.index('python -m unittest discover'))
        self.assertIn('--archive', text)

    def test_cold_guide_installs_verified_bytes_and_runs_real_oracles(self):
        guide = self.initialize()
        args = self.setup_command(guide)
        archive, pin = self.reviewed_archive()
        env, empty = self.cold_environment()
        for args_git in [('init', '-q', '-b', 'main'), ('config', 'user.name', 'Cold test'),
                         ('config', 'user.email', 'cold@example.invalid'),
                         ('config', 'maintenance.autoDetach', 'false'), ('config', 'gc.autoDetach', 'false'),
                         ('add', '-A'), ('commit', '-qm', 'Initialized cold project')]:
            p = self.command(['git', *args_git], env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
        before = self.command(['git', 'status', '--porcelain=v1'], env=env).stdout
        p = self.command([sys.executable, *args[1:], '--archive', str(archive)], env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        data = json.loads(p.stdout)
        binary = Path(data['binary'])
        self.assertTrue(binary.resolve().is_relative_to(empty.resolve()))
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), pin['binary_sha256'])
        self.assertEqual(hashlib.sha256(Path(data['archive']).read_bytes()).hexdigest(), pin['archive_sha256'])
        self.assertFalse(any(k.startswith('KDD_ACTIONLINT_') for k in env))
        p = self.command([sys.executable, '-m', 'unittest', 'tests.test_workflow_syntax',
                          'tests.test_workflow_syntax_ci'], env=env, timeout=240)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertRegex(p.stderr, r'Ran 27 tests in ')
        self.assertRegex(p.stderr, r'\nOK\s*\Z')
        self.assertNotIn('skipped=', p.stderr)
        after = self.command(['git', 'status', '--porcelain=v1'], env=env).stdout
        self.assertEqual(before, after)

    def test_empty_cache_missing_tool_is_explicit_failure(self):
        self.initialize()
        env, _ = self.cold_environment()
        p = self.command([sys.executable, 'scripts/validate_workflows.py', 'check', '--repo-root', '.'], env=env)
        self.assertNotEqual(p.returncode, 0)
        result = json.loads(p.stdout)
        self.assertIs(result['ok'], False)
        self.assertEqual(result['code'], 'WORKFLOW_SYNTAX_TOOL')


if __name__ == '__main__':
    unittest.main()
