"""Real HTTP and Git controls for Board onboarding boundaries."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'tools' / 'kdd-board'


def outside_directory():
    """Choose a writable temporary parent without a Git ancestor."""
    candidates = [Path(tempfile.gettempdir()), Path(ROOT.anchor)]
    for parent in candidates:
        if not parent.is_dir() or any((p / '.git').exists() for p in (parent, *parent.parents)):
            continue
        try:
            return tempfile.TemporaryDirectory(prefix='kdd-board-onboarding-', dir=parent)
        except OSError:
            continue
    raise RuntimeError('No writable temporary directory outside a Git repository')


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, encoding='utf-8', timeout=60)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def board(root):
    env = dict(os.environ, KDD_PROJECT_DIR=str(root), KDD_PYTHON=sys.executable, PYTHONUTF8='1')
    env.pop('GIT_DIR', None)
    env.pop('GIT_WORK_TREE', None)
    script = r"""
import {createServer} from './src/server.ts';
const s = createServer('audit-only');
await new Promise(resolve => s.listen(0,'127.0.0.1',resolve));
try {
  const base = `http://127.0.0.1:${s.address().port}`;
  const headers = {authorization:'Bearer audit-only'};
  const mode = await fetch(base+'/api/board',{headers});
  const tasks = await fetch(base+'/api/tasks',{headers});
  console.log(JSON.stringify({mode:await mode.json(),tasks:await tasks.json(),
    modeStatus:mode.status,tasksStatus:tasks.status}));
} finally { await new Promise(resolve => s.close(resolve)); }
"""
    return subprocess.run(['node', '--input-type=module', '-e', script], cwd=BOARD,
                          env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)


class BoardOnboardingAudit(unittest.TestCase):
    def setUp(self):
        if not (BOARD / 'node_modules' / 'zod' / 'package.json').is_file():
            if not (ROOT / 'src' / 'hello.py').is_file():
                self.skipTest('initialized Python-only copy; Board runtime dependencies are not installed')
            self.fail('Board runtime dependencies must be installed in the template')
        self.temp = outside_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_initialized_project_starts_empty_without_git(self):
        spec = importlib.util.spec_from_file_location('onboarding_init', ROOT / 'scripts' / 'init_project.py')
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(ROOT / 'scripts'))
        if not all((ROOT / name).is_file() for name in module.MANIFEST):
            self.skipTest('source is already initialized; no template examples remain')
        project = self.root / 'initialized'
        project.mkdir()
        for name in set(module.MANIFEST) | set(module.REQUIRED_AFTER_DELETE):
            destination = project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'init_project.py'),
                                 '--repo-dir', str(project), '--apply', '--name', 'Fresh',
                                 '--repository', 'example/fresh'], capture_output=True,
                                text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((project / '.git').exists())
        self.assertFalse(list((project / 'knowledge' / 'tasks').glob('TASK-*.md')))
        result = board(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tasks'], [])
        self.assertFalse((project / '.kdd-board' / 'tasks.json').exists())

    def test_empty_project_has_no_seeded_tasks_on_restart(self):
        project = self.root / 'new-project'
        project.mkdir()
        (project / 'knowledge').mkdir()
        for _ in range(2):
            result = board(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(response['mode'], {'mode': 'legacy', 'sourceRef': None})
            self.assertEqual(response['tasks'], [])
            self.assertEqual(response['tasksStatus'], 200)
        self.assertFalse((project / '.kdd-board' / 'tasks.json').exists())

    def test_existing_empty_store_is_not_repopulated_or_overwritten(self):
        project = self.root / 'project'
        (project / '.kdd-board').mkdir(parents=True)
        store = project / '.kdd-board' / 'tasks.json'
        store.write_text('[]\n', encoding='utf-8')
        result = board(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tasks'], [])
        self.assertEqual(store.read_text(encoding='utf-8'), '[]\n')

    def test_existing_legacy_task_is_preserved(self):
        project = self.root / 'project'
        (project / '.kdd-board').mkdir(parents=True)
        store = project / '.kdd-board' / 'tasks.json'
        value = [{'id': 'task-existing', 'title': 'Existing work', 'status': 'backlog',
                  'updatedAt': '2026-01-01T00:00:00Z'}]
        raw = json.dumps(value) + '\n'
        store.write_text(raw, encoding='utf-8')
        result = board(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['tasks'], value)
        self.assertEqual(store.read_text(encoding='utf-8'), raw)

    def test_nested_project_rejects_parent_repo_before_writes(self):
        parent = self.root / 'parent'
        parent.mkdir()
        git(parent, 'init', '-q', '-b', 'main')
        git(parent, 'config', 'user.name', 'Audit')
        git(parent, 'config', 'user.email', 'audit@example.invalid')
        git(parent, 'commit', '-q', '--allow-empty', '-m', 'initial')
        project = parent / 'new-project'
        project.mkdir()
        before = git(parent, 'rev-parse', 'HEAD')
        result = board(project)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_PROJECT_ROOT', result.stderr)
        self.assertEqual(git(parent, 'rev-parse', 'HEAD'), before)
        self.assertFalse((project / '.kdd-board').exists())

    def test_git_task_store_rejects_nested_root_directly(self):
        parent = self.root / 'parent'
        parent.mkdir()
        git(parent, 'init', '-q', '-b', 'main')
        project = parent / 'project'
        project.mkdir()
        env = dict(os.environ, KDD_PROJECT_DIR=str(project))
        source = "import {isGitProject} from './src/git-task-store.ts'; isGitProject(process.env.KDD_PROJECT_DIR);"
        result = subprocess.run(['node', '--input-type=module', '-e', source], cwd=BOARD,
                                env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_PROJECT_ROOT', result.stderr)

    def test_real_project_root_preserves_git_mode(self):
        project = self.root / 'project'
        project.mkdir()
        git(project, 'init', '-q', '-b', 'main')
        git(project, 'config', 'user.name', 'Audit')
        git(project, 'config', 'user.email', 'audit@example.invalid')
        git(project, 'commit', '-q', '--allow-empty', '-m', 'initial')
        result = board(project)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response['mode']['mode'], 'git')
        self.assertEqual(response['mode']['sourceRef'], 'main')
        self.assertEqual(response['tasksStatus'], 200)
        self.assertFalse((project / '.kdd-board').exists())

    def test_worktree_root_is_a_valid_project(self):
        project = self.root / 'project'
        project.mkdir()
        git(project, 'init', '-q', '-b', 'main')
        git(project, 'config', 'user.name', 'Audit')
        git(project, 'config', 'user.email', 'audit@example.invalid')
        git(project, 'config', 'maintenance.auto', 'false')
        git(project, 'config', 'gc.auto', '0')
        git(project, 'commit', '-q', '--allow-empty', '-m', 'initial')
        worktree = self.root / 'worktree'
        git(project, 'worktree', 'add', '-q', '-b', 'task/audit', str(worktree))
        self.assertTrue((worktree / '.git').is_file())
        result = board(worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode']['mode'], 'git')
        self.assertEqual(json.loads(result.stdout)['tasksStatus'], 200)
        self.assertFalse((worktree / '.kdd-board').exists())

    def test_existing_http_fixture_works_when_temp_is_inside_git(self):
        parent = self.root / 'parent'
        parent.mkdir()
        git(parent, 'init', '-q', '-b', 'main')
        bindir = self.root / 'bin'
        bindir.mkdir()
        if os.name == 'nt':
            bindir = Path(sys.executable).parent
        else:
            (bindir / 'python').symlink_to(sys.executable)
        env = dict(os.environ, TEMP=str(parent), TMP=str(parent), TMPDIR=str(parent),
                   PYTHONUTF8='1')
        env['PATH'] = str(bindir) + os.pathsep + env.get('PATH', '')
        result = subprocess.run(['node', '--test', 'tests/http-hardening.test.ts'],
                                cwd=BOARD, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('fail 0', result.stdout)


if __name__ == '__main__':
    unittest.main()
