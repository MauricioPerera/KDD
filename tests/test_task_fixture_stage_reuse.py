"""Real Git controls for private task fixture snapshots."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def trace_starts(trace):
    with trace.open(encoding='utf-8') as stream:
        events = (json.loads(line) for line in stream)
        return [event['argv'] for event in events if event.get('event') == 'start']


def assert_private(test, first, second):
    for project in (first, second):
        test.assertEqual(project.git('status', '--porcelain'), '')
        test.assertFalse((project.root / '.git/objects/info/alternates').exists())
        test.assertEqual(Path(project.git('rev-parse', '--show-toplevel')).resolve(),
                         project.root.resolve())
    files = {'.git/config', '.git/index', 'src/feature1.py',
             'quality/product.json'}
    tree = first.root / '.git/objects'
    objects = {path.relative_to(first.root) for path in tree.rglob('*')
               if path.is_file() and (second.root / path.relative_to(first.root)).is_file()}
    test.assertTrue(objects, 'the equivalent fixtures have Git objects in common')
    for name in files | objects:
        left, right = first.root / name, second.root / name
        test.assertFalse(left.is_symlink() or right.is_symlink(), str(name))
        test.assertFalse(os.path.samefile(left, right), str(name))
    head = second.git('rev-parse', 'HEAD')
    first.write('case-marker.txt', 'private data\n')
    unique = first.commit('Commit confined to one disposable case')
    test.assertEqual(second.git('rev-parse', 'HEAD'), head)
    test.assertFalse((second.root / 'case-marker.txt').exists())
    test.assertNotEqual(second.command(['git', 'cat-file', '-e', unique],
                                      check=False).returncode, 0)


def base_projects(test, builder, trace):
    from tests.test_git_task_multi_oracle import SECONDARY, SECONDARY_TEST

    updated = SECONDARY_TEST + '\n# different private oracle for one case\n'
    with patch.dict(os.environ, {'GIT_DEFAULT_HASH': 'sha1'}):
        first = builder.project()
        second = builder.project()
        variant = builder.project(secondary=updated)
    with patch.dict(os.environ, {'GIT_DEFAULT_HASH': 'sha256'}):
        sha256 = builder.project()
    starts = trace_starts(trace)
    test.assertEqual(sum('init' in argv for argv in starts), 2,
                     'one real Git init for each format')
    for project in (first, second, variant):
        test.assertEqual(project.git('rev-parse', '--show-object-format'), 'sha1')
        test.assertEqual(len(project.ref), 40)
    test.assertEqual(sha256.git('rev-parse', '--show-object-format'), 'sha256')
    test.assertEqual(len(sha256.ref), 64)
    test.assertEqual((variant.root / SECONDARY).read_bytes(), updated.encode('utf-8'))
    test.assertEqual((first.root / SECONDARY).read_bytes(), SECONDARY_TEST.encode('utf-8'))
    test.assertEqual(first.git('rev-parse', 'HEAD^{tree}'), second.git('rev-parse', 'HEAD^{tree}'))
    assert_private(test, first, second)


def integrated_projects(test, builder, trace):
    scenario = getattr(builder, 'integrated_project', None)
    test.assertTrue(callable(scenario), 'integrated_project() is the fixture entrypoint')
    with patch.dict(os.environ, {'GIT_DEFAULT_HASH': 'sha1'}):
        first, second = scenario(), scenario()
    starts = trace_starts(trace)
    test.assertEqual(sum('init' in argv for argv in starts), 1)
    test.assertLessEqual(len(starts), 85, 'build one integrated fixture for both cases')
    test.assertEqual(first.git('show-ref'), second.git('show-ref'))
    test.assertEqual(first.ref, second.ref)
    test.assertEqual(first.git('rev-parse', 'HEAD'), second.git('rev-parse', 'HEAD'))
    for project in (first, second):
        test.assertEqual(project.act('show', 1)['status'], 'in_progress')
        test.assertEqual(project.git('rev-parse', project.ref), project.ref)
        test.assertFalse(list((project.root / 'docs/task-evidence').glob('*.json')))
    assert_private(test, first, second)
    test.assertEqual(second.act('show', 1)['status'], 'in_progress')


class TaskFixtureStageReuse(unittest.TestCase):
    def run_probe(self, mode):
        with tempfile.TemporaryDirectory(prefix='kdd-task-stage-reuse-') as area:
            path = Path(area).resolve()
            env = dict(os.environ, TMP=str(path), TEMP=str(path), TMPDIR=str(path),
                       GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_TRACE2_EVENT=str(path / 'trace.jsonl'))
            for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR'):
                env.pop(name, None)
            result = subprocess.run([sys.executable, '-I', '-B', __file__, '--probe', mode],
                                    cwd=ROOT, env=env, capture_output=True, check=False,
                                    timeout=120, encoding='utf-8', errors='backslashreplace')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_repeated_projects_build_one_seed_per_format_and_keep_variant_private(self):
        self.run_probe('base')

    def test_integrated_projects_keep_private_state_and_reuse_setup(self):
        self.run_probe('integrated')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--probe':
        sys.path.insert(0, str(ROOT))
        from tests.test_git_task_multi_oracle import GitTaskMultiOracle

        mode = {'base': base_projects, 'integrated': integrated_projects}[sys.argv[2]]
        builder = GitTaskMultiOracle()
        try:
            mode(unittest.TestCase(), builder, Path(os.environ['GIT_TRACE2_EVENT']))
        finally:
            builder.doCleanups()
    else:
        unittest.main()
