"""Real task commits and external hardlink canaries; no mocked filesystem/Git."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_task_git import Repository, journal, model

ROOT = Path(__file__).resolve().parents[1]


class TaskWriteBoundary(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd task aliases ')
        self.addCleanup(self.area.cleanup)
        self.outside = Path(self.area.name)
        self.repo = Repository()
        self.addCleanup(self.repo.close)
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                        KDD_PYTHON=sys.executable)
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + self.env.get('PATH', '')

    def state(self):
        status = self.repo.git('status', '--porcelain')
        return {'head': self.repo.git('rev-parse', 'HEAD'), 'status': status,
                'refs': self.repo.git('for-each-ref', '--format=%(refname) %(objectname)'),
                'index': (self.repo.root / '.git/index').read_bytes(),
                'index_node': (self.repo.root / 'knowledge/index.md').read_bytes(),
                'tasks': {p.name: p.read_bytes() for p in (self.repo.root / 'knowledge/tasks').glob('*.md')}}

    def cli(self, operation, *arguments):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/tasks.py'),
            '--repo-root', str(self.repo.root), operation, 'TASK-001', *arguments, '--json'],
            cwd=self.repo.root, env=self.env, capture_output=True, text=True,
            encoding='utf-8', timeout=45)

    def alias(self, name):
        target = self.repo.root / name
        link = self.outside / ('external-' + target.name)
        os.link(target, link)
        self.assertEqual(target.stat().st_nlink, 2)
        return link, link.read_bytes()

    def rejected(self, operation, name='knowledge/tasks/TASK-001.md', *arguments):
        link, content = self.alias(name)
        before = self.state()
        result = self.cli(operation, *arguments)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('TASK_PATH:', result.stderr)
        self.assertEqual(self.state(), before)
        self.assertEqual(link.read_bytes(), content)
        self.assertFalse((self.repo.root / '.git/kdd-tasks.lock').exists())

    def test_create_rejects_hardlinked_index(self):
        self.rejected('create', 'knowledge/index.md', '--title', 'Own task',
                      '--description', 'Own integration', '--contract', self.repo.contract)

    def test_ready_rejects_hardlinked_node(self):
        self.repo.act('create')
        self.rejected('ready', 'knowledge/tasks/TASK-001.md', '--approved-ref', self.repo.approved)

    def test_start_rejects_before_creating_task_branch(self):
        self.repo.act('create'); self.repo.act('ready', approved_ref=self.repo.approved)
        self.rejected('start', 'knowledge/tasks/TASK-001.md', '--assignee', 'developer')
        self.assertNotIn('task/TASK-001', self.repo.git('branch', '--format=%(refname:short)'))

    def test_block_rejects_hardlinked_node(self):
        self.repo.start()
        self.rejected('block', 'knowledge/tasks/TASK-001.md', '--reason', 'Needs a reviewer')

    def test_resume_rejects_hardlinked_node(self):
        self.repo.start(); self.repo.act('block', reason='Needs a reviewer')
        self.rejected('resume', 'knowledge/tasks/TASK-001.md', '--reason', 'Review supplied')

    def test_finish_rejects_before_executing_the_real_oracle(self):
        oracle = ('import unittest\nfrom pathlib import Path\nfrom src.value import value\n'
                  'Path(".proof-ran").write_text("executed")\n'
                  'class ValueTests(unittest.TestCase):\n'
                  ' def test_value(self): self.assertEqual(value(), 7)\n')
        self.repo = Repository(oracle=oracle)
        self.addCleanup(self.repo.close)
        with (self.repo.root / '.gitignore').open('a') as stream:
            stream.write('.proof-ran\n')
        self.repo.commit('Ignore own oracle execution marker')
        self.repo.start(); self.repo.integrate()
        self.rejected('finish')
        self.assertFalse((self.repo.root / '.proof-ran').exists())

    def board(self, operation, payload):
        module = (ROOT / 'tools/kdd-board/src/git-task-store.ts').as_uri()
        code = ('import {GitTaskStore} from ' + json.dumps(module) + ';'
            'const store=new GitTaskStore(process.argv[1]);'
            'try { const input=JSON.parse(process.argv[3]);'
            'console.log(JSON.stringify(await (process.argv[2]==="create"?'
            'store.create(input):store.transition("TASK-001",input))));'
            '} catch(error) {console.log(JSON.stringify({code:error.code,status:error.status}));'
            'process.exitCode=2;}')
        return subprocess.run(['node', '--input-type=module', '-e', code, str(self.repo.root),
            operation, json.dumps(payload)], env=self.env, cwd=self.repo.root,
            capture_output=True, text=True, encoding='utf-8', timeout=60)

    def test_board_transition_rejects_alias_without_committing(self):
        self.repo.act('create')
        link, content = self.alias('knowledge/tasks/TASK-001.md'); before = self.state()
        result = self.board('ready', {'status': 'ready', 'approved_ref': self.repo.approved})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['code'], 'TASK_PATH')
        self.assertEqual(self.state(), before); self.assertEqual(link.read_bytes(), content)

    def test_board_create_rejects_alias_without_committing(self):
        link, content = self.alias('knowledge/index.md'); before = self.state()
        result = self.board('create', {'task_id': 'TASK-001', 'title': 'Own task',
            'description': 'Own task integration', 'contract': self.repo.contract})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['code'], 'TASK_PATH')
        self.assertEqual(self.state(), before); self.assertEqual(link.read_bytes(), content)

    def test_complete_regular_task_keeps_real_proof_and_scoped_commits(self):
        self.repo.start(); self.repo.integrate()
        before = self.repo.git('rev-parse', 'HEAD')
        result = self.cli('finish')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)['task']; self.assertEqual(data['status'], 'done')
        evidence = json.loads((self.repo.root / data['evidence']).read_text())
        self.assertEqual(evidence['tested_commit'], before)
        self.assertGreater(evidence['passed_tests'], 0)
        changed = self.repo.git('diff', '--name-only', before, 'HEAD').splitlines()
        self.assertEqual(set(changed), {'knowledge/tasks/TASK-001.md', data['evidence']})
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_real_commit_hook_failure_restores_node_index_and_branch(self):
        self.repo.act('create'); self.repo.act('ready', approved_ref=self.repo.approved)
        head = self.repo.git('rev-parse', 'HEAD')
        original = (self.repo.root / 'knowledge/tasks/TASK-001.md').read_bytes()
        indexed = self.repo.git('ls-files', '--stage')
        hook = self.repo.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 37\n', encoding='utf-8'); hook.chmod(0o755)
        result = self.cli('start', '--assignee', 'developer')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TASK_GIT:', result.stderr)
        self.assertEqual(self.repo.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.repo.git('ls-files', '--stage'), indexed)
        self.assertEqual((self.repo.root / 'knowledge/tasks/TASK-001.md').read_bytes(), original)
        self.assertNotIn('task/TASK-001', self.repo.git('branch', '--format=%(refname:short)'))
        self.assertEqual(self.repo.git('status', '--porcelain'), '')

    def test_direct_publication_rejects_shared_inode_before_backup(self):
        link, content = self.alias('knowledge/index.md'); before = self.state()
        with self.assertRaisesRegex(model.TaskError, 'TASK_PATH:'):
            journal._publish(self.repo.root, before['head'],
                {'knowledge/index.md': b'new index\n'}, (None, 'Own rejected write'))
        self.assertEqual(self.state(), before); self.assertEqual(link.read_bytes(), content)

    def test_regular_destinations_and_missing_leaf_remain_supported(self):
        self.assertEqual(journal.safe_path(self.repo.root, 'knowledge/index.md'),
                         self.repo.root / 'knowledge/index.md')
        self.assertEqual(journal.safe_path(self.repo.root, 'docs/new-evidence.json'),
                         self.repo.root / 'docs/new-evidence.json')

    def test_existing_directory_is_not_a_file_destination(self):
        with self.assertRaisesRegex(model.TaskError, 'TASK_PATH:'):
            journal.safe_path(self.repo.root, 'knowledge/contracts')

    def test_shared_inode_path_is_rejected_without_any_write(self):
        link, content = self.alias('knowledge/index.md')
        with self.assertRaisesRegex(model.TaskError, 'TASK_PATH:'):
            journal.safe_path(self.repo.root, 'knowledge/index.md')
        self.assertEqual(link.read_bytes(), content)

    def test_source_copy_without_git_or_init_test_runs_independent_controls(self):
        source = self.outside / 'source'; (source / 'tests').mkdir(parents=True)
        shutil.copytree(ROOT / 'scripts', source / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('test_task_write_boundary.py', 'test_task_git.py', 'test_fixture_preparation.py'):
            shutil.copyfile(ROOT / 'tests' / name, source / 'tests' / name)
        (source / 'tests/__init__.py').write_text('')
        self.assertFalse((source / '.git').exists())
        self.assertFalse((source / 'tests/test_init_project.py').exists())
        result = subprocess.run([sys.executable, '-m', 'unittest',
            'tests.test_task_write_boundary.TaskWriteBoundary.test_ready_rejects_hardlinked_node',
            'tests.test_task_write_boundary.TaskWriteBoundary.test_complete_regular_task_keeps_real_proof_and_scoped_commits'],
            cwd=source, env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 2 tests', result.stderr); self.assertNotIn('skipped=', result.stderr)


if __name__ == '__main__':
    unittest.main()
