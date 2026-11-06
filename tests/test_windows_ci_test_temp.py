"""Real process and filesystem checks for the native KDD CI temp setup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_fixture_preparation import directory_alias

ROOT = Path(__file__).resolve().parents[1]
STEP_NAME = '      - name: Prepare native Windows test temp'
CONDITION = "        if: ${{ github.repository == 'MauricioPerera/KDD' && matrix.os == 'windows-latest' && !inputs.reusable_execution }}"


def workflow_text():
    return (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')


def workflow_step():
    lines = workflow_text().splitlines()
    if STEP_NAME not in lines:
        return '', ''  # Existing workflow performs no temp preparation.
    start = lines.index(STEP_NAME)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('      - ')), len(lines))
    block = lines[start:end]
    run = block.index('        run: |')
    code = '\n'.join(line[10:] if line.startswith('          ') else line for line in block[run + 1:])
    return code, '\n'.join(block)


class WindowsCITestTemp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-ci-temp-oracle-')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.root = self.area / 'repo'; self.root.mkdir()
        self.base = self.area / 'runner temp \u00f1'; self.base.mkdir()
        self.envfile = self.area / 'github-env'
        self.envfile.write_bytes(b'KEEP=before\n')
        self.env = dict(os.environ, PYTHONUTF8='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1', RUNNER_TEMP=str(self.base), GITHUB_ENV=str(self.envfile))
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE', 'GIT_CEILING_DIRECTORIES'):
            self.env.pop(name, None)
        self.git(self.root, 'init', '-q', '-b', 'main')

    def git(self, root, *args, check=True, environment=None):
        return subprocess.run(['git', '-C', str(root), *args], env=self.env if environment is None else environment,
            capture_output=True, text=True, encoding='utf-8', timeout=30, check=check)

    def step(self):
        return workflow_step()

    def execute(self, **changes):
        code, _ = self.step()
        return subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=self.root,
            env=dict(self.env, **changes), capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_real_children_inherit_private_temp_and_other_environment_is_preserved(self):
        directories = []
        for number in (1, 2):
            with self.subTest(invocation=number):
                self.envfile.write_bytes(b'KEEP=before\n')
                result = self.execute()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                assignments = dict(line.split('=', 1) for line in self.envfile.read_text(encoding='utf-8').splitlines())
                self.assertEqual(set(assignments), {'KEEP', 'TEMP', 'TMP', 'TMPDIR'})
                self.assertEqual(assignments.pop('KEEP'), 'before')
                self.assertEqual(len(set(assignments.values())), 1)
                directory = Path(assignments['TEMP']).resolve(strict=True)
                self.assertEqual(directory.parent, self.base.resolve())
                directories.append(directory)
                self.assertNotEqual(self.git(directory, 'rev-parse', '--is-inside-work-tree', check=False).returncode, 0)
                environment = dict(self.env, **assignments)
                python = subprocess.run([sys.executable, '-X', 'utf8', '-c',
                    'import json,tempfile; from pathlib import Path;\nwith tempfile.TemporaryDirectory() as p: print(json.dumps(str(Path(p).parent)))'],
                    env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(python.returncode, 0, python.stderr)
                self.assertEqual(Path(json.loads(python.stdout)).resolve(), directory)
                node = shutil.which('node')
                self.assertIsNotNone(node, 'Node24 is a required dependency of the native KDD workflow')
                probe = subprocess.run([node, '-e',
                    "const fs=require('fs'),os=require('os'),path=require('path'); const p=fs.mkdtempSync(path.join(os.tmpdir(),'kdd-child-')); console.log(JSON.stringify(path.dirname(p))); fs.rmdirSync(p);"],
                    env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertEqual(Path(json.loads(probe.stdout)).resolve(), directory)
                child = directory / 'git-child'; child.mkdir()
                self.git(child, 'init', '-q', '-b', 'main', environment=environment)
                self.assertEqual(self.git(child, 'rev-parse', '--show-toplevel', environment=environment).stdout.strip().replace('\\', '/'), child.as_posix())
                _, block = self.step()
                self.assertIn(CONDITION, block.splitlines())
                self.assertIn('        shell: python', block.splitlines())
                workflow = workflow_text()
                self.assertLess(workflow.index('      - name: Run required MCP SDK protocol smoke'), workflow.index(STEP_NAME))
                self.assertLess(workflow.index(STEP_NAME), workflow.index('      - name: Validate contracts'))
                emitted = [json.loads(line.removeprefix('KDD_WINDOWS_TEMP ')) for line in result.stdout.splitlines() if line.startswith('KDD_WINDOWS_TEMP ')]
                self.assertEqual(len(emitted), 1)
                self.assertEqual(Path(emitted[0]['runner_temp']).resolve(), self.base.resolve())
                self.assertEqual(Path(emitted[0]['test_temp']).resolve(), directory)
        self.assertEqual(len(directories), 2)
        self.assertNotEqual(*directories)

    def test_invalid_or_git_owned_bases_fail_without_environment_writes(self):
        file = self.area / 'regular-file'; file.write_bytes(b'owned sentinel\n')
        inside = self.root / 'inside'; inside.mkdir()
        foreign = self.area / 'foreign'; foreign.mkdir(); self.git(foreign, 'init', '-q', '-b', 'main')
        foreign_base = foreign / 'temp'; foreign_base.mkdir()
        invalid_git = self.area / 'bad-config'; invalid_git.mkdir(); self.git(invalid_git, 'init', '-q', '-b', 'main')
        (invalid_git / '.git/config').write_bytes(b'[broken git config\n')
        alias = self.area / 'alias'
        directory_alias(alias, self.root, self.area)
        self.addCleanup(alias.rmdir if os.name == 'nt' else alias.unlink)
        for base in (self.area / 'missing', file, inside, foreign_base, invalid_git, alias):
            with self.subTest(base=base.name):
                before = self.envfile.read_bytes()
                result = self.execute(RUNNER_TEMP=str(base))
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.envfile.read_bytes(), before)
                self.assertEqual(list(self.base.iterdir()), [])
        self.assertEqual(file.read_bytes(), b'owned sentinel\n')

    def test_real_env_write_errors_clean_only_the_new_empty_directory(self):
        sentinel = self.base / 'keep.dat'; sentinel.write_bytes(b'preserve previous job data\n')
        bad_directory = self.area / 'env-directory'; bad_directory.mkdir()
        for output in (bad_directory, self.area / 'absent-parent/env'):
            with self.subTest(output=output.name):
                result = self.execute(GITHUB_ENV=str(output))
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.envfile.read_bytes(), b'KEEP=before\n')
                self.assertEqual(list(self.base.iterdir()), [sentinel])
                self.assertEqual(sentinel.read_bytes(), b'preserve previous job data\n')
                self.assertEqual(list(bad_directory.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
