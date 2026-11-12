"""Real Git controls for the amount and isolation of fixture preparation."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_ci_trusted_execution as trusted
from tests import test_generated_task_evidence as generated
from tests import test_group_contracts as groups


TASK_SCRIPTS = {
    'task_git.py', 'task_model.py', 'task_evidence.py', 'tasks.py',
    'validate_tasks.py', 'validate_contracts.py', 'oracle_inventory.py',
    'process_tree.py', 'verify_quality.py', 'oracle_execution.py',
    'unittest_oracle_runner.py', 'node_oracle_reporter.mjs',
}


def commands(trace):
    result = []
    for line in trace.read_text(encoding='utf-8-sig').splitlines():
        event = json.loads(line)
        if event.get('event') != 'start':
            continue
        argv = event['argv'][1:]
        while argv and argv[0].startswith('-'):
            option = argv.pop(0)
            if option in ('-C', '-c') and argv:
                argv.pop(0)
        if argv:
            result.append(argv)
    return result


class FixtureWork(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix='kdd-fixture-work-'))
        self.area = Path(temporary).resolve()

    def test_task_fixture_commits_only_its_runtime_scripts(self):
        project = generated.TaskProject(self.area / 'task product')
        files = project.git('ls-tree', '-r', '--name-only', project.ref, 'scripts').splitlines()
        self.assertEqual(set(files), {'scripts/' + name for name in TASK_SCRIPTS})
        for name in TASK_SCRIPTS:
            relative = 'scripts/' + name
            result = project.command(['git', 'rev-parse', project.ref + ':' + relative])
            source = generated.ROOT / relative
            self.assertEqual((project.root / relative).read_bytes(), source.read_bytes())
            digest = project.command(['git', 'hash-object', '--no-filters', str(source)]).stdout.strip()
            self.assertEqual(result.stdout.strip(), digest, relative)

    def test_task_fixture_runs_real_quality_and_preserves_existing_files(self):
        root = self.area / 'consumer'
        (root / 'scripts').mkdir(parents=True)
        extra = root / 'scripts' / 'consumer_local.py'
        extra.write_bytes(b'CONSUMER = True\n')
        project = generated.TaskProject(root)
        self.assertEqual(project.git('show', project.ref + ':scripts/consumer_local.py'), 'CONSUMER = True')
        _, finished = project.complete(1)
        artifact = root / finished['task']['evidence']
        self.assertEqual(json.loads(artifact.read_bytes())['passed_tests'], 2)
        result = project.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('RUN '), 4, result.stdout)
        self.assertEqual(extra.read_bytes(), b'CONSUMER = True\n')
        self.assertEqual(project.git('status', '--porcelain'), '')

    def fixture_pair(self, cls, label, location):
        trace = self.area / (label + '.jsonl')
        overrides = {'GIT_TRACE2_EVENT': str(trace), 'GIT_CONFIG_COUNT': '1',
                     'GIT_CONFIG_KEY_0': 'core.autocrlf', 'GIT_CONFIG_VALUE_0': 'true'}
        with patch.dict(os.environ, overrides):
            cls.setUpClass()
            self.addCleanup(cls.doClassCleanups)
            pair = [cls('runTest'), cls('runTest')]
            for case in pair:
                self.addCleanup(case.doCleanups)
                case.setUp()
        first, second = pair
        launched = commands(trace)
        totals = Counter(argv[0] for argv in launched)
        self.assertEqual(totals['init'], 1)
        self.assertEqual(totals['clone'], 2)
        seeds = {Path(argv[-2]).resolve(strict=True) for argv in launched if argv[0] == 'clone'}
        self.assertEqual(len(seeds), 1, seeds)
        seed = seeds.pop()
        first_root, second_root = (getattr(case, location) for case in pair)
        self.assertNotEqual(first_root, second_root)
        for case, root in zip(pair, (first_root, second_root)):
            self.assertEqual(case.git('status', '--porcelain'), '')
            self.assertEqual(case.git('config', '--local', '--get', 'core.autocrlf'), 'false')
            self.assertFalse((root / '.git/objects/info/alternates').exists())
        head = first.git('rev-parse', 'HEAD')
        self.assertEqual(head, second.git('rev-parse', 'HEAD'))
        for oid in (head, first.git('rev-parse', 'HEAD^{tree}')):
            paths = [root / '.git' / 'objects' / oid[:2] / oid[2:]
                     for root in (seed, first_root, second_root)]
            self.assertEqual([path.stat().st_nlink for path in paths], [1, 1, 1])
            self.assertEqual(paths[0].read_bytes(), paths[1].read_bytes())
            self.assertEqual(paths[0].read_bytes(), paths[2].read_bytes())
        return first, second, seed

    def check_mutation_isolated(self, first, second, seed, location, relative):
        first_root, second_root = (getattr(case, location) for case in (first, second))
        before = second.git('write-tree')
        original = (second_root / relative).read_bytes()
        self.assertEqual((first_root / relative).read_bytes(), original)
        self.assertEqual(second.git('hash-object', '--no-filters', relative),
                         second.git('rev-parse', 'HEAD:' + relative),
                         'checkout must match its committed blob')
        seed_bytes = (seed / relative).read_bytes()
        seed_index = (seed / '.git/index').read_bytes()
        seed_head = (seed / '.git/HEAD').read_bytes()
        seed_branch = seed_head.decode('ascii').strip().removeprefix('ref: ')
        seed_ref = (seed / '.git' / seed_branch).read_bytes()
        (first_root / relative).write_bytes(b'fixture worktree mutation\n')
        first.git('add', '--', relative)
        first.git('update-ref', 'refs/heads/only-first-fixture', first.git('rev-parse', 'HEAD'))
        self.assertNotEqual(first.git('write-tree'), before)
        self.assertEqual(second.git('write-tree'), before)
        self.assertEqual((second_root / relative).read_bytes(), original)
        self.assertNotIn('only-first-fixture', second.git('for-each-ref', 'refs/heads/'))
        self.assertEqual((seed / relative).read_bytes(), seed_bytes)
        self.assertEqual((seed / '.git/index').read_bytes(), seed_index)
        self.assertEqual((seed / '.git/HEAD').read_bytes(), seed_head)
        self.assertEqual((seed / '.git' / seed_branch).read_bytes(), seed_ref)
        self.assertFalse((seed / '.git/refs/heads/only-first-fixture').exists())
        oid = first.git('rev-parse', ':' + relative)
        probe = subprocess.run(['git', '-C', str(second_root), 'cat-file', '-e', oid],
                               capture_output=True, check=False, timeout=30)
        self.assertNotEqual(probe.returncode, 0, oid)

    def test_group_cases_share_setup_and_execute_independently(self):
        first, second, seed = self.fixture_pair(groups.GroupContractsIntegration, 'group', 'root')
        for case in (first, second):
            self.assertEqual(case.events(), [])
            result, payload = case.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(payload['ok'], payload)
            self.assertEqual(case.events(), ['atom', 'sub', 'integration'])
        self.check_mutation_isolated(first, second, seed, 'root', 'src/add.py')

    def test_runtime_cases_share_setup_and_execute_independently(self):
        first, second, seed = self.fixture_pair(trusted.TrustedExecution, 'runtime', 'repo')
        for case in (first, second):
            marker = case.repo / 'runs'
            self.assertFalse(marker.exists())
            result = case.execute(case.bundle())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(marker.read_text(encoding='utf-8'), '1')
        self.check_mutation_isolated(first, second, seed, 'repo', 'feature.py')


if __name__ == '__main__':
    unittest.main()
