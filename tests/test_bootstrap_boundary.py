"""Real template copies, native aliases and external canaries; no mocked IO."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IS_TEMPLATE = (ROOT / 'src/hello.py').is_file()


def snapshot(root):
    result = {}
    def visit(path):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            result[name] = ('alias', os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            result[name] = ('directory', stat.S_IMODE(info.st_mode))
            for child in sorted(path.iterdir()):
                visit(child)
        else:
            result[name] = ('file', path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_mtime_ns)
    if root.exists():
        for path in sorted(root.iterdir()):
            visit(path)
    return result


class SandboxFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached',
                                         '--others', '--exclude-standard', '-z']).decode('utf-8').split('\0')
        cls.source = {}
        for relative in filter(None, names):
            path = ROOT / relative
            if path.is_file():
                cls.source[relative] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd bootstrap integration ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.root = self.new_project('project')
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            self.env.pop(key, None)

    def new_project(self, name):
        root = self.area / name
        root.mkdir()
        for relative, (raw, mode) in self.source.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(mode)
        return root

    def command(self, args, root=None, env=None, timeout=180):
        return subprocess.run(args, cwd=root or self.root, env=env or self.env,
                              capture_output=True, text=True, encoding='utf-8', timeout=timeout)

    def cli(self, script='init_project.py', root=None, apply=True, repo_arg=None, extra=()):
        root = root or self.root
        args = [sys.executable, str(root / 'scripts' / script), '--repo-dir', str(repo_arg or root),
                '--repository', 'Example/Bootstrap', '--name', 'Bootstrap project']
        if apply:
            args.append('--apply')
        return self.command([*args, *extra], root=root)

    def directory_alias(self, link, target):
        self.assertTrue(link.parent.resolve().is_relative_to(self.area))
        self.assertTrue(target.resolve().is_relative_to(self.area))
        if os.name != 'nt':
            link.symlink_to(target, target_is_directory=True)
            return
        script = self.area / 'junction.ps1'
        script.write_text('param([string]$Link,[string]$Target)\n'
                          'New-Item -ItemType Junction -Path $Link -Value $Target -ErrorAction Stop | Out-Null\n',
                          encoding='utf-8')
        p = self.command(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                          '-File', str(script), '-Link', str(link), '-Target', str(target)])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(link.exists())

    def move_to_alias(self, root, relative, name):
        source, outside = root / relative, self.area / name
        self.assertTrue(source.resolve().is_relative_to(self.area))
        self.assertTrue(outside.resolve().is_relative_to(self.area))
        source.rename(outside)
        self.directory_alias(source, outside)
        return outside

    def unchanged(self, before, path, label):
        after = snapshot(path)
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        self.assertEqual(changed, [], label + ' changed paths: ' + ', '.join(changed[:12]))

    def rejects(self, root, outside, script='init_project.py', apply=True):
        before, external = snapshot(root), snapshot(outside)
        p = self.cli(script, root, apply=apply)
        self.unchanged(external, outside, 'external canary')
        self.unchanged(before, root, 'project')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('BOOTSTRAP_PATH', p.stdout + p.stderr)


@unittest.skipUnless(IS_TEMPLATE, 'template-only bootstrap integration: project already initialized')
class BootstrapBoundary(SandboxFixture):
    def test_linked_source_cannot_delete_external_files(self):
        outside = self.move_to_alias(self.root, 'src', 'outside-src')
        self.rejects(self.root, outside)

    def test_linked_workflows_cannot_overwrite_external_files(self):
        outside = self.move_to_alias(self.root, '.github/workflows', 'outside-workflows')
        self.rejects(self.root, outside)

    def test_linked_knowledge_is_rejected_before_cleanup(self):
        outside = self.move_to_alias(self.root, 'knowledge', 'outside-knowledge')
        self.rejects(self.root, outside)

    def test_linked_reports_are_rejected_before_cleanup(self):
        outside = self.move_to_alias(self.root, 'docs/reports', 'outside-reports')
        self.rejects(self.root, outside)

    def test_bootstrap_rejects_native_platform_aliases(self):
        cases = ['README.md', 'KDD-START-HERE.md'] if os.name != 'nt' else ['src', '.github/workflows']
        for index, relative in enumerate(cases):
            with self.subTest(relative=relative):
                root = self.root if index == 0 else self.new_project('second-alias')
                outside = self.area / ('canary-' + str(index))
                if os.name == 'nt':
                    outside = self.move_to_alias(root, relative, 'canary-' + str(index))
                else:
                    outside.mkdir()
                    target = outside / 'external.md'
                    target.write_text('# External canary\n', encoding='utf-8')
                    (root / relative).unlink(missing_ok=True)
                    (root / relative).symlink_to(target)
                self.rejects(root, outside, 'bootstrap_project.py')

    def test_managed_hardlinks_are_rejected_without_truncation(self):
        files = ['README.md', 'CHANGELOG.md', 'completion-legacy.json',
                 'knowledge/index.md', '.github/workflows/validate.yml']
        for index, relative in enumerate(files):
            with self.subTest(relative=relative):
                root = self.root if index == 0 else self.new_project('hardlink-' + str(index))
                outside = self.area / ('hardlink-canary-' + str(index))
                outside.mkdir()
                target = outside / 'external'
                shutil.copyfile(root / relative, target)
                (root / relative).unlink()
                os.link(target, root / relative)
                self.assertGreater((root / relative).stat().st_nlink, 1)
                self.rejects(root, outside)

    def test_hardlinked_guide_is_rejected_before_initialization(self):
        outside = self.area / 'guide-canary'
        outside.mkdir()
        target = outside / 'guide.md'
        target.write_text('# External guide\n', encoding='utf-8')
        os.link(target, self.root / 'KDD-START-HERE.md')
        self.rejects(self.root, outside, 'bootstrap_project.py')

    def test_dry_run_rejects_unsafe_paths_without_writes(self):
        outside = self.move_to_alias(self.root, 'src', 'dry-run-canary')
        self.rejects(self.root, outside, apply=False)

    def test_internal_alias_is_rejected_even_without_escape(self):
        saved = self.root / 'saved-source'
        self.assertTrue(saved.resolve().is_relative_to(self.area))
        (self.root / 'src').rename(saved)
        self.directory_alias(self.root / 'src', saved)
        self.rejects(self.root, saved)

    def test_hardlinked_sample_scan_is_rejected_before_cleanup(self):
        outside = self.area / 'scan-canary'
        outside.mkdir()
        scan = self.root / 'compliance/scan/findings.json'
        target = outside / 'findings.json'
        shutil.copyfile(scan, target)
        scan.unlink()
        os.link(target, scan)
        self.assertGreater(scan.stat().st_nlink, 1)
        self.rejects(self.root, outside)

    def test_unmanaged_alias_and_own_files_are_preserved(self):
        outside = self.area / 'custom-resources'
        outside.mkdir()
        (outside / 'own.txt').write_text('Own content\n', encoding='utf-8')
        custom = self.root / 'custom'
        custom.mkdir()
        self.directory_alias(custom / 'shared', outside)
        (custom / 'own.txt').write_text('Project-owned\n', encoding='utf-8')
        before, external = snapshot(custom), snapshot(outside)
        p = self.cli('bootstrap_project.py')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.unchanged(before, custom, 'unmanaged data')
        self.unchanged(external, outside, 'unmanaged target')

    def test_regular_copies_initialize_with_both_public_entries(self):
        for index, script in enumerate(['init_project.py', 'bootstrap_project.py']):
            with self.subTest(entry=script):
                root = self.root if index == 0 else self.new_project('wrapper')
                p = self.cli(script, root)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertFalse((root / 'src/hello.py').exists())
                self.assertFalse((root / 'knowledge/tasks/TASK-002.md').exists())
                identity = json.loads((root / 'completion-legacy.json').read_text(encoding='utf-8'))
                self.assertEqual(identity['repository'], 'Example/Bootstrap')
                self.assertEqual(identity['legacy_pairs'], {})

    def test_alias_of_explicit_project_root_remains_supported(self):
        alias = self.area / 'selected-root'
        self.directory_alias(alias, self.root)
        p = self.cli(repo_arg=alias)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse((self.root / 'src/hello.py').exists())


if __name__ == '__main__':
    unittest.main()
