"""Exercise the paired diagnostic with actual Git objects and suite workers."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'scripts/ci_windows_paired.py'
RUNTIME_FILES = ('trusted_ci.py', 'run_test_suite.py', 'validate_test_commands.py',
                 'validate_contracts.py', 'process_tree.py', 'execution_profile.py')
COMMON = 'test_cases.Example.test_observe'
EXTRA = 'test_cases.Example.test_extra'
REPLACEMENT = 'test_cases.Example.test_replacement'
MOVE_HEAD = 'test_cases.Example.test_move_head'
FIXTURE = '''
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

class Example(unittest.TestCase):
    def test_observe(self):
        config = os.environ.get('COVERAGE_PROCESS_START')
        if config:
            self.assertTrue(Path(config).is_file())
        with Path('observation.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(time=time.monotonic_ns(), temp=tempfile.gettempdir(),
                                         coverage=config,
                                         skip_init=os.environ.get('KDD_SKIP_INIT_POST_APPLY_SUITE'))) + '\\n')
'''
ADDED = '''
    def test_extra(self):
        self.assertEqual(2 + 3, 5)
'''
DRIFT = '''
    def test_move_head(self):
        if not os.environ.get('COVERAGE_PROCESS_START'):
            import subprocess
            subprocess.run(['git', '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid',
                            '-c', 'commit.gpgsign=false', 'commit', '--quiet',
                            '--allow-empty', '-m', 'Same tree, different commit'], check=True)
'''
COVERAGE_FIXTURE = '''
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['prepare', 'report'])
parser.add_argument('--repo-root', default='.')
parser.add_argument('--output', required=True)
for name in ('head-sha', 'run-id', 'attempt', 'platform'):
    parser.add_argument('--' + name)
args = parser.parse_args()
root, output = Path(args.repo_root).resolve(), Path(args.output).resolve()
assert not output.is_relative_to(root)
if args.command == 'prepare':
    output.mkdir(parents=True, exist_ok=False)
    config = '[run]\\nbranch = true\\nparallel = true\\ndata_file = ' + (output / '.coverage').as_posix() + '\\n'
    (output / 'coverage.ini').write_text(config, encoding='utf-8')
else:
    rows = [json.loads(line) for line in (root / 'observation.jsonl').read_text().splitlines()]
    assert Path(rows[0]['coverage']).resolve() == output / 'coverage.ini', rows
    assert len(rows) == 2 and rows[1]['coverage'] is None, rows
    identity = dict(head_sha=args.head_sha, run_id=args.run_id, attempt=args.attempt,
                    platform=args.platform, fragments=1, suite_pass=1)
    report = dict(kdd=identity, meta=dict(branch_coverage=True),
                  totals=dict(num_statements=2, covered_lines=2, num_branches=2, covered_branches=2))
    (output / 'coverage.json').write_text(json.dumps(report), encoding='utf-8')
'''


def digest(ids):
    return hashlib.sha256(('\n'.join(sorted(ids)) + '\n').encode('utf-8')).hexdigest()


class PairedSuiteIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='kdd-paired-integration-')
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                     'COVERAGE_PROCESS_START', 'COVERAGE_FILE'):
            self.env.pop(name, None)
        self.seed = self.area / 'seed'
        self.seed.mkdir()
        self.git(self.seed, 'init', '--quiet', '--initial-branch=main', '--template=')
        self.git(self.seed, 'config', 'core.autocrlf', 'false')
        self.write(self.seed / '.gitignore', 'observation.jsonl\n__pycache__/\n')
        self.write(self.seed / 'scripts/ci_coverage.py', COVERAGE_FIXTURE)
        for name in RUNTIME_FILES:
            shutil.copyfile(ROOT / 'scripts' / name, self.seed / 'scripts' / name)
        self.write(self.seed / 'tests/test_cases.py', FIXTURE)
        self.reference = self.commit(self.seed)
        self.write(self.seed / 'tests/test_cases.py', FIXTURE + ADDED)
        self.candidate = self.commit(self.seed)
        self.bundle = self.area / 'trusted'
        self.checked([sys.executable, '-I', str(ROOT / 'scripts/trusted_ci.py'),
                      'prepare', '--repo-root', str(self.seed), '--trusted-ref',
                      self.reference, '--bundle-dir', str(self.bundle)])

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')

    def command(self, argv, *, env=None):
        return subprocess.run(argv, env=env or self.env, capture_output=True,
                              encoding='utf-8', timeout=120, check=False)

    def checked(self, argv):
        result = self.command(argv)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def git(self, root, *args):
        return self.checked(['git', '-C', str(root), *args])

    def commit(self, root):
        self.git(root, 'add', '--all')
        self.git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Paired probe fixture')
        return self.git(root, 'rev-parse', 'HEAD')

    def arm(self, directory, role, commit, ids):
        root = directory / role
        self.git(self.seed, 'clone', '--quiet', '--no-hardlinks', str(self.seed), str(root))
        self.git(root, 'checkout', '--quiet', '--detach', commit)
        return dict(checkout=str(root), commit=commit, tree=self.git(root, 'rev-parse', 'HEAD^{tree}'),
                    ids_sha256=digest(ids))

    def plan(self, root, *, order=('reference', 'candidate'), candidate=None, ids=None):
        root.mkdir()
        return dict(schema_version=1, order=list(order), runtime_ref=self.reference,
                    bundle=str(self.bundle), arms={
                        'reference': self.arm(root, 'reference', self.reference, [COMMON]),
                        'candidate': self.arm(root, 'candidate', candidate or self.candidate,
                                              ids if ids is not None else [COMMON, EXTRA]),
                    })

    def execute(self, root, plan):
        path = root / 'plan.json'
        self.write(path, json.dumps(plan))
        output = root / 'output'
        # Deliberately stale parent coverage; only the probe's first pass may enable it.
        stale = root / 'stale.ini'
        self.write(stale, '[run]\nparallel = true\ndata_file = ' + (root / '.stale-coverage').as_posix() + '\n')
        env = dict(self.env, COVERAGE_PROCESS_START=str(stale), KDD_SKIP_INIT_POST_APPLY_SUITE='0')
        return self.command([sys.executable, '-I', str(PROBE), '--plan', str(path),
                             '--output', str(output)], env=env)

    @staticmethod
    def observations(arm):
        path = Path(arm['checkout']) / 'observation.jsonl'
        return [json.loads(row) for row in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

    def test_control_runs_real_suite_and_reconciles_candidate_ids(self):
        root = self.area / 'control'
        root.mkdir()
        arm = self.arm(root, 'candidate', self.candidate, [COMMON, EXTRA])
        report = root / 'report.json'
        self.checked([sys.executable, '-I', str(self.bundle / 'trusted_ci.py'), 'suite',
                      '--repo-root', arm['checkout'], '--workers', '6', '--report-json', str(report)])
        evidence = json.loads(report.read_text(encoding='utf-8'))
        self.assertTrue(evidence['ok'])
        self.assertEqual(evidence['workers'], 6)
        self.assertEqual(digest(evidence['executed_ids']), arm['ids_sha256'])
        self.assertEqual(len(self.observations(arm)), 1)

    def test_orders_execute_two_fresh_passes_and_keep_their_evidence(self):
        orders = (('reference', 'candidate'), ('candidate', 'reference'))
        for index, order in enumerate(orders):
            with self.subTest(order=order):
                root = self.area / ('order-' + str(index))
                plan = self.plan(root, order=order)
                result = self.execute(root, plan)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                summary = json.loads((root / 'output/comparison.json').read_text(encoding='utf-8'))
                self.assertEqual(summary['order'], list(order))
                self.assertEqual(summary['runtime_ref'], self.reference)
                observations = []
                for role in order:
                    expected = plan['arms'][role]
                    actual = summary['arms'][role]
                    self.assertEqual((actual['commit'], actual['tree']), (expected['commit'], expected['tree']))
                    self.assertEqual([item['number'] for item in actual['passes']], [1, 2])
                    self.assertEqual([item['coverage'] for item in actual['passes']], [True, False])
                    folder = root / 'output' / role
                    coverage = json.loads((folder / 'coverage/coverage.json').read_text(encoding='utf-8'))
                    self.assertEqual(coverage['kdd']['head_sha'], expected['commit'])
                    self.assertEqual(coverage['kdd']['suite_pass'], 1)
                    for item in actual['passes']:
                        raw = json.loads((folder / ('suite-%s.json' % item['number'])).read_text(
                            encoding='utf-8'))
                        self.assertTrue(raw['ok'])
                        self.assertEqual(raw['workers'], 6)
                        self.assertEqual(raw['trusted_runtime_ref'], self.reference)
                        self.assertEqual(digest(raw['expected_ids']), expected['ids_sha256'])
                        self.assertEqual(digest(raw['executed_ids']), expected['ids_sha256'])
                        self.assertEqual(item['ids_sha256'], expected['ids_sha256'])
                        self.assertGreater(item['duration_seconds'], 0)
                    rows = self.observations(expected)
                    self.assertEqual(len(rows), 2)
                    config = (folder / 'coverage/coverage.ini').resolve()
                    self.assertEqual(Path(rows[0]['coverage']).resolve(), config)
                    self.assertIsNone(rows[1]['coverage'])
                    self.assertEqual([row['skip_init'] for row in rows], ['1', '1'])
                    self.assertEqual(rows[0]['temp'], rows[1]['temp'])
                    observations.extend(rows)
                timestamps = [row['time'] for row in observations]
                self.assertEqual(timestamps, sorted(set(timestamps)))
                self.assertNotEqual(observations[0]['temp'], observations[2]['temp'])

    def test_rejects_mismatched_checkout_before_running_either_arm(self):
        for field in ('commit', 'tree', 'tracked_content'):
            with self.subTest(field=field):
                root = self.area / field
                plan = self.plan(root)
                if field == 'tracked_content':
                    checkout = Path(plan['arms']['candidate']['checkout'])
                    self.write(checkout / 'tests/test_cases.py', FIXTURE)
                    self.assertEqual(self.git(checkout, 'rev-parse', 'HEAD'), self.candidate)
                    self.assertEqual(self.git(checkout, 'rev-parse', 'HEAD^{tree}'),
                                     plan['arms']['candidate']['tree'])
                else:
                    plan['arms']['candidate'][field] = plan['arms']['reference'][field]
                result = self.execute(root, plan)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('PAIRED_CHECKOUT', result.stderr)
                for arm in plan['arms'].values():
                    self.assertEqual(self.observations(arm), [])

    def test_rejects_stale_output_before_running_either_arm(self):
        root = self.area / 'stale'
        plan = self.plan(root)
        previous = root / 'output/comparison.json'
        self.write(previous, 'do not overwrite')
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_OUTPUT', result.stderr)
        self.assertEqual(previous.read_text(encoding='utf-8'), 'do not overwrite')
        for arm in plan['arms'].values():
            self.assertEqual(self.observations(arm), [])

    def test_rejects_bundle_with_different_runtime_before_running_either_arm(self):
        root = self.area / 'runtime'
        plan = self.plan(root)
        plan['runtime_ref'] = self.candidate
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_RUNTIME', result.stderr)
        for arm in plan['arms'].values():
            self.assertEqual(self.observations(arm), [])

    def test_passing_candidate_that_drops_a_reference_case_is_rejected(self):
        self.write(self.seed / 'tests/test_cases.py', FIXTURE.replace('test_observe', 'test_replacement') + ADDED)
        root = self.area / 'missing'
        plan = self.plan(root, candidate=self.commit(self.seed), ids=[REPLACEMENT, EXTRA])
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_INVENTORY', result.stderr)
        self.assertFalse((root / 'output/comparison.json').exists())

    def test_green_report_with_wrong_declared_digest_is_rejected(self):
        root = self.area / 'digest'
        plan = self.plan(root, ids=[COMMON])
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_INVENTORY', result.stderr)
        self.assertFalse((root / 'output/comparison.json').exists())

    def test_second_pass_that_moves_head_with_the_same_tree_is_rejected(self):
        self.write(self.seed / 'tests/test_cases.py', FIXTURE + ADDED + DRIFT)
        root = self.area / 'move-head'
        plan = self.plan(root, candidate=self.commit(self.seed), ids=[COMMON, EXTRA, MOVE_HEAD])
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_CHECKOUT', result.stderr)
        checkout = Path(plan['arms']['candidate']['checkout'])
        self.assertNotEqual(self.git(checkout, 'rev-parse', 'HEAD'), plan['arms']['candidate']['commit'])
        self.assertEqual(self.git(checkout, 'rev-parse', 'HEAD^{tree}'), plan['arms']['candidate']['tree'])
        self.assertFalse((root / 'output/comparison.json').exists())

    def test_report_for_another_commit_is_rejected_after_both_passes(self):
        wrong_identity = COVERAGE_FIXTURE.replace('head_sha=args.head_sha',
                                                   'head_sha=' + repr(self.reference))
        self.write(self.seed / 'scripts/ci_coverage.py', wrong_identity)
        root = self.area / 'coverage-identity'
        plan = self.plan(root, candidate=self.commit(self.seed))
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_COVERAGE', result.stderr)
        self.assertEqual(len(self.observations(plan['arms']['candidate'])), 2)
        self.assertFalse((root / 'output/comparison.json').exists())

    def test_assertion_failure_cannot_publish_a_comparison(self):
        self.write(self.seed / 'tests/test_cases.py', FIXTURE + ADDED.replace('2 + 3', '2 + 4'))
        root = self.area / 'red'
        plan = self.plan(root, candidate=self.commit(self.seed))
        result = self.execute(root, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAIRED_SUITE', result.stderr)
        self.assertFalse((root / 'output/comparison.json').exists())
