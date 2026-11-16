"""Post-init partitions with real Python workers and independent inventory."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

from scripts import ci_postinit_shards as shards
from scripts import init_project as bootstrap


ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'tools/ci/postinit-windows-shards.json'
RUNNER_FILES = ('run_test_suite.py', 'process_tree.py', 'ci_postinit_shards.py',
                'init_post_apply_suite.py', 'init_project.py', 'bootstrap_transaction.py')
MODULES = ('test_alpha', 'test_beta', 'test_delta', 'test_gamma')
GROUPS = (('test_alpha', 'test_delta'), ('test_beta', 'test_gamma'))
IDS = [[name + '.Canary.test_body' for name in group] for group in GROUPS]
IDENTITY = dict(run_id='314', run_attempt='2', head_sha='a' * 40, tree='b' * 40,
                runtime_ref='c' * 40, jobs_head_sha='d' * 40)
NATIVE_EVENTS = (
    "github.repository == 'MauricioPerera/KDD' && !inputs.reusable_execution && "
    "github.workflow_ref == format('{0}/.github/workflows/validate.yml@{1}', github.repository, github.ref) && "
    "(github.event_name == 'pull_request' || "
    "(github.event_name == 'push' && github.ref == 'refs/heads/main'))"
)
GATES = 'TestInitProject.test_gates_verdes_post_apply_en_copia'
API_RUN = 'repos/MauricioPerera/KDD/actions/runs/314'
API_JOB_LIST = API_RUN + '/attempts/2/jobs?per_page=100'
OUTER_FIXTURE = """import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

class TestInitProject(unittest.TestCase):
    def test_gates_verdes_post_apply_en_copia(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'initialized'
            shutil.copytree(Path.cwd(), target, ignore=shutil.ignore_patterns('.git', '__pycache__'))
            subprocess.run([sys.executable, 'scripts/init_project.py', '--repo-dir', str(target),
                            '--apply', '--repository', 'ExampleCo/Shop'], check=True)
            self.assertFalse((target / 'src/hello.py').exists())
            (target / 'tests/test_init_project.py').unlink()
            subprocess.run([sys.executable, 'scripts/init_post_apply_suite.py', '--repo-root',
                            str(target), '--report-json', str(target / 'suite.json')], check=True)
"""


def _profile(root, groups=GROUPS):
    path = root / PROFILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(schema_version=1, groups=groups)), encoding='utf-8')


def _miniature(root):
    (root / 'tests').mkdir(parents=True)
    (root / 'scripts').mkdir()
    for name in RUNNER_FILES:
        shutil.copyfile(ROOT / 'scripts' / name, root / 'scripts' / name)
    for name in MODULES:
        (root / 'tests' / (name + '.py')).write_text(
            'from pathlib import Path\nimport unittest\n\n'
            'class Canary(unittest.TestCase):\n'
            '    def test_body(self):\n'
            '        Path(__name__ + ".executed").write_text(__name__, encoding="utf-8")\n'
            '        self.assertTrue(Path(__name__ + ".executed").is_file())\n',
            encoding='utf-8')
    _profile(root)


def _template(root, leak_canary):
    for name in bootstrap.MANIFEST + bootstrap.REQUIRED_AFTER_DELETE:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
    workflow = ''.join(before for before, _ in bootstrap._PRODUCT_CI_REPLACEMENTS)
    workflow += '      - name: Approve project quality (when configured)\n'
    (root / '.github/workflows/validate.yml').write_text(workflow, encoding='utf-8')
    (root / 'tests/test_init_project.py').write_text(OUTER_FIXTURE, encoding='utf-8')
    path = root / 'tests/test_alpha.py'
    with path.open('a', encoding='utf-8') as stream:
        # Executed in actual worker imports, including the verifier's discovery.
        stream.write('import os\n'
                     'assert not any(os.environ.get(key) for key in '
                     '("KDD_POSTINIT_SHARD", "KDD_POSTINIT_RAW_REPORT", "GH_TOKEN", '
                     '"GITHUB_TOKEN", "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH"))\n'
                     'from pathlib import Path\n'
                     f'Path({str(leak_canary)!r}).touch()\n')


def _call(root, script, arguments, env=None):
    return subprocess.run([sys.executable, '-I', '-X', 'utf8', str(root / 'scripts' / script),
                           *arguments], cwd=root, env=env, capture_output=True,
                          encoding='utf-8', errors='replace', timeout=45)


def _timestamp(seconds):
    start = datetime(2026, 1, 4, 12, tzinfo=timezone.utc)
    return (start + timedelta(seconds=seconds)).isoformat().replace('+00:00', 'Z')


def _job(shard, start, end):
    return dict(name='Windows post-init ({})'.format(shard), id=700 + shard,
                run_id=314, run_attempt=2, head_sha=IDENTITY['jobs_head_sha'],
                status='completed', conclusion='success',
                steps=[dict(name='Run post-init shard', status='completed',
                            conclusion='success', started_at=_timestamp(start),
                            completed_at=_timestamp(end))])


def _receipt(shard, inventory=IDS, report=None):
    expected = inventory[shard]
    data = {name: IDENTITY[name] for name in
            ('run_id', 'run_attempt', 'head_sha', 'tree', 'runtime_ref')}
    data.update(schema_version=1, shard=shard, inventory=copy.deepcopy(inventory),
                expected_ids=list(expected), ok=True, executed_ids=list(expected),
                fixture_omitted_ids=[])
    if report is not None:
        for name in ('expected_ids', 'executed_ids', 'fixture_omitted_ids', 'ok'):
            data[name] = report[name]
    return data


def _verify(receipts, jobs, expected):
    try:
        return shards.verify(receipts, {'jobs': jobs}, expected, IDENTITY)
    except NotImplementedError as error:
        raise AssertionError(str(error)) from error


def _archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return stream.getvalue()


class PostInitPartitionExecution(unittest.TestCase):
    def setUp(self):
        area = self.enterContext(tempfile.TemporaryDirectory(prefix='kdd-shards-'))
        self.area = Path(area).resolve()
        self.root = self.project('p0')

    def project(self, name):
        root = self.area / name
        _miniature(root)
        return root

    def run_shard(self, root, shard, *, destination='report.json'):
        return _call(root, 'ci_postinit_shards.py',
                     ['suite', '--repo-root', str(root), '--shard', str(shard),
                      '--report-json', str(root / destination)])

    def discover(self, root):
        try:
            return shards.discover(root)
        except NotImplementedError as error:
            self.fail(str(error))

    def test_two_real_workers_reconcile_against_a_separate_full_run(self):
        other = self.project('p1')
        control = self.project('full')
        reverse = (tuple(reversed(GROUPS[0])), GROUPS[1])
        _profile(self.root, reverse)
        _profile(other, reverse)
        _profile(control, reverse)
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(control / 'scripts/run_test_suite.py'),
             '--workers', '1', '--report-json', 'report.json'],
            cwd=control, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        complete = json.loads((control / 'report.json').read_text(encoding='utf-8'))
        receipts = []
        for index, root in enumerate((self.root, other)):
            self.assertFalse((root / '.git').exists())
            result = self.run_shard(root, index)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            shard = json.loads((root / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(shard['expected_ids'], IDS[index])
            self.assertEqual(shard['executed_ids'], IDS[index])
            self.assertEqual(shard['postinit_partition'], {'shard': index, 'inventory': IDS})
            self.assertEqual(shard['workers'], 10 if os.name == 'nt' else 4)
            self.assertEqual({path.stem for path in root.glob('*.executed')}, set(GROUPS[index]))
            self.assertTrue(all(record['pid'] and record['pid'] != os.getpid()
                                for record in shard['modules']))
            self.assertEqual([record['module'] for record in shard['modules']], list(reverse[index]))
            receipts.append(_receipt(index, report=shard))
        independent = self.discover(self.project('discovery'))
        self.assertEqual(sorted(sum(independent, [])), complete['executed_ids'])
        verdict = _verify(receipts, [_job(0, 0, 401), _job(1, 5, 408)], independent)
        self.assertEqual(verdict['wall_bound_seconds'], 409)

    def test_unlisted_module_has_stable_assignment(self):
        _profile(self.root, (('test_alpha',), ('test_beta', 'test_gamma')))
        inventory = self.discover(self.root)
        shard = hashlib.sha256(b'test_delta').digest()[0] % 2
        self.assertIn('test_delta.Canary.test_body', inventory[shard])
        self.assertNotIn('test_delta.Canary.test_body', inventory[1 - shard])
        self.assertEqual(sorted(sum(inventory, [])), sorted(sum(IDS, [])))

    def test_invalid_profile_fails_before_any_worker_runs(self):
        _profile(self.root, (('test_alpha',), ('test_alpha', 'test_beta')))
        result = self.run_shard(self.root, 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate module', result.stderr)
        self.assertFalse(list(self.root.glob('*.executed')))

    def test_discovery_failure_in_other_group_prevents_a_green_subset(self):
        (self.root / 'tests/test_beta.py').write_text('def )\n', encoding='utf-8')
        result = self.run_shard(self.root, 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('test_beta', result.stderr)
        self.assertFalse(list(self.root.glob('*.executed')))

    def test_empty_partition_is_not_a_success(self):
        _profile(self.root, (MODULES, ()))
        result = self.run_shard(self.root, 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('empty partition', result.stderr)
        self.assertFalse(list(self.root.glob('*.executed')))

    def test_class_skip_preserves_acknowledged_ids_in_the_real_worker(self):
        path = self.root / 'tests/test_alpha.py'
        path.write_text(path.read_text(encoding='utf-8').replace(
            'class Canary', '@unittest.skip("control platform fixture")\nclass Canary'),
            encoding='utf-8')
        result = self.run_shard(self.root, 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((self.root / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['expected_ids'], IDS[0])
        self.assertEqual(report['executed_ids'], IDS[0])
        self.assertEqual([row['id'] for row in report['skipped']], [IDS[0][0]])
        self.assertEqual(report['fixture_omitted_ids'], [])
        self.assertFalse((self.root / 'test_alpha.executed').exists())

    def test_failed_worker_retains_its_actual_report(self):
        path = self.root / 'tests/test_alpha.py'
        path.write_text(path.read_text(encoding='utf-8').replace(
            'self.assertTrue(', 'self.assertFalse('), encoding='utf-8')
        result = self.run_shard(self.root, 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / 'report.json').is_file(), result.stdout + result.stderr)
        report = json.loads((self.root / 'report.json').read_text(encoding='utf-8'))
        self.assertIs(report['ok'], False)
        self.assertEqual(report['expected_ids'], IDS[0])
        self.assertEqual([row['id'] for row in report['failures']], [IDS[0][0]])

    def test_destination_is_exclusive(self):
        path = self.root / 'report.json'
        path.write_bytes(b'previous report')
        result = self.run_shard(self.root, 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report destination already exists', result.stderr)
        self.assertEqual(path.read_bytes(), b'previous report')
        self.assertFalse(list(self.root.glob('*.executed')))

    def test_launcher_delegates_only_when_shard_is_explicit(self):
        base_env = os.environ.copy()
        base_env.pop('KDD_POSTINIT_SHARD', None)
        for group in (None, '1'):
            with self.subTest(group=group):
                env = base_env if group is None else dict(base_env, KDD_POSTINIT_SHARD=group)
                path = self.root / ('launcher-{}.json'.format(group))
                result = _call(self.root, 'init_post_apply_suite.py',
                               ['--repo-root', str(self.root), '--report-json', str(path)], env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(path.read_text(encoding='utf-8'))
                expected = sorted(sum(IDS, [])) if group is None else IDS[1]
                self.assertEqual(report['expected_ids'], expected)


class CommonDeadlineVerification(unittest.TestCase):
    def setUp(self):
        self.receipts = [_receipt(0), _receipt(1)]
        self.jobs = [_job(0, 0, 400), _job(1, 5, 408)]

    def check(self):
        return _verify(self.receipts, self.jobs, IDS)

    def test_upper_bound_includes_second_resolution(self):
        self.jobs[1] = _job(1, 5, 599)
        self.assertEqual(self.check()['wall_bound_seconds'], 600)
        self.jobs[1] = _job(1, 5, 600)
        with self.assertRaisesRegex(ValueError, '600'):
            self.check()

    def test_individually_fast_steps_can_miss_common_deadline(self):
        self.jobs[1] = _job(1, 210, 610)
        with self.assertRaisesRegex(ValueError, '600'):
            self.check()

    def test_missing_or_duplicate_partitions_are_rejected(self):
        for receipts in ([_receipt(0)], [_receipt(0), _receipt(0)]):
            with self.subTest(receipts=len(receipts)):
                self.receipts = receipts
                with self.assertRaisesRegex(ValueError, 'shard|partition|receipt'):
                    self.check()

    def test_receipts_must_match_attempt_checkout_tree_and_runtime(self):
        for key in ('run_id', 'run_attempt', 'head_sha', 'tree', 'runtime_ref'):
            with self.subTest(key=key):
                changed = _receipt(1)
                changed[key] = '9' if key.startswith('run_') else '9' * 40
                self.receipts[1] = changed
                with self.assertRaisesRegex(ValueError, key):
                    self.check()

    def test_jobs_from_other_attempt_or_pr_head_are_rejected(self):
        for key, value in (('run_attempt', 1), ('run_id', 313), ('head_sha', 'e' * 40)):
            with self.subTest(key=key):
                self.jobs[1] = _job(1, 5, 408)
                self.jobs[1][key] = value
                with self.assertRaisesRegex(ValueError, key):
                    self.check()

    def test_step_requires_an_unambiguous_successful_interval(self):
        for change in ({'conclusion': 'cancelled'}, {'status': 'in_progress'},
                       {'started_at': None}, {'completed_at': _timestamp(5)},
                       {'started_at': '2026-01-04T12:00:05'}):
            with self.subTest(change=change):
                self.jobs[1] = _job(1, 5, 408)
                self.jobs[1]['steps'][0].update(change)
                with self.assertRaisesRegex(ValueError, 'step|interval|timestamp'):
                    self.check()
        self.jobs[1] = _job(1, 5, 408)
        self.jobs[1]['steps'] *= 2
        with self.assertRaisesRegex(ValueError, 'step'):
            self.check()

    def test_duplicate_job_id_and_failed_job_are_rejected(self):
        self.jobs[1]['id'] = self.jobs[0]['id']
        with self.assertRaisesRegex(ValueError, 'job'):
            self.check()
        self.jobs[1] = _job(1, 5, 408)
        self.jobs[1]['conclusion'] = 'failure'
        with self.assertRaisesRegex(ValueError, 'job'):
            self.check()

    def test_discovery_rejects_an_omission_agreed_by_both_workers(self):
        incomplete = [IDS[0][:1], IDS[1]]
        self.receipts = [_receipt(0, incomplete), _receipt(1, incomplete)]
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.check()

    def test_missing_duplicate_and_foreign_executions_are_rejected(self):
        for values in (IDS[1][:1], IDS[1] * 2, [IDS[0][0], IDS[1][0]]):
            with self.subTest(values=values):
                self.receipts[1]['executed_ids'] = values
                with self.assertRaisesRegex(ValueError, 'executed_ids|account'):
                    self.check()
        self.receipts[1] = _receipt(1)
        self.receipts[1]['fixture_omitted_ids'] = [IDS[1][0]]
        with self.assertRaisesRegex(ValueError, 'omitted|account'):
            self.check()


class PostInitReceiptIntegration(unittest.TestCase):
    def setUp(self):
        area = self.enterContext(tempfile.TemporaryDirectory(prefix='kdd-shard-job-'))
        self.area = Path(area).resolve()
        self.root = self.area / 'checkout'
        _miniature(self.root)
        self.canary = self.area / 'import-canary'
        _template(self.root, self.canary)
        self.env = {name: value for name, value in os.environ.items()
                    if not name.startswith(('GIT_', 'GITHUB_', 'KDD_POSTINIT_'))}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-qm', 'Fixture for independent post-init checkout')
        self.identity = dict(IDENTITY, head_sha=self.git('rev-parse', 'HEAD'),
                             tree=self.git('rev-parse', 'HEAD^{tree}'))
        self.env.update(GITHUB_RUN_ID='314', GITHUB_RUN_ATTEMPT='2',
                        GITHUB_SHA=self.identity['head_sha'], GITHUB_WORKSPACE=str(self.root),
                        RUNNER_TEMP=str(self.area), KDD_TRUSTED_RUNTIME_REF=IDENTITY['runtime_ref'],
                        KDD_TRUSTED_BUNDLE=str(self.root / 'scripts'))

    def git(self, *args):
        result = subprocess.run(
            ['git', '-c', 'user.name=KDD Fixture', '-c', 'user.email=kdd@example.test',
             '-c', 'core.autocrlf=false', '-c', 'commit.gpgsign=false', *args],
            cwd=self.root, env=self.env, capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def execute(self, index):
        destination = self.area / ('receipt-{}.json'.format(index))
        result = _call(self.root, 'ci_postinit_shards.py',
                       ['run', '--repo-root', str(self.root), '--shard', str(index),
                        '--receipt', str(destination)], self.env)
        return result, destination

    def replay(self, receipts, corrupt=None):
        responses = {API_JOB_LIST: dict(total_count=2, jobs=[_job(0, 0, 401), _job(1, 5, 408)])}
        for index, receipt in enumerate(receipts):
            name = 'kdd-postinit-shard-314-2-{}'.format(index)
            archive = _archive([('receipt.json', receipt.read_bytes())])
            rows = [dict(name=name, id=821 + index, expired=False,
                         digest='sha256:' + hashlib.sha256(archive).hexdigest())]
            responses[API_RUN + '/artifacts?name=' + name + '&per_page=100'] = dict(
                total_count=len(rows), artifacts=rows)
            responses['repos/MauricioPerera/KDD/actions/artifacts/{}/zip'.format(821 + index)] = archive
        if corrupt is not None:
            corrupt(responses)
        def request(path):
            self.assertIn(path, responses)
            response = responses[path]
            return response if isinstance(response, bytes) else json.dumps(response).encode()
        return request

    def test_real_launcher_receipts_pass_independent_initialized_discovery(self):
        receipts = []
        for index in (0, 1):
            result, receipt = self.execute(index)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(receipt.read_bytes())
            self.assertEqual(data['expected_ids'], IDS[index])
            self.assertEqual(data['head_sha'], self.identity['head_sha'])
            self.assertEqual(data['tree'], self.identity['tree'])
            self.assertEqual(data['inventory'], IDS)
            receipts.append(receipt)
        self.canary.unlink()
        channels = {name: 'synthetic-value' for name in (
            'GH_TOKEN', 'GITHUB_TOKEN', 'GITHUB_ENV', 'GITHUB_OUTPUT', 'GITHUB_PATH')}
        with patch.dict(os.environ, channels):
            try:
                verdict = shards.collect(self.root, self.identity, self.replay(receipts))
            except NotImplementedError as error:
                self.fail(str(error))
        self.assertEqual(verdict['wall_bound_seconds'], 409)
        self.assertTrue(self.canary.is_file(), 'the independent discovery did not run')
        self.assertTrue((self.root / 'src/hello.py').is_file())

    def test_green_outer_fixture_cannot_publish_without_a_real_report(self):
        (self.root / 'tests/test_init_project.py').write_text(
            'import unittest\nclass TestInitProject(unittest.TestCase):\n'
            '    def test_gates_verdes_post_apply_en_copia(self): self.assertTrue(True)\n',
            encoding='utf-8')
        result, destination = self.execute(0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('report', result.stderr)
        self.assertFalse(destination.exists())

    def test_fixture_omissions_require_backing_worker_outcomes(self):
        path = self.root / 'tests/test_init_project.py'
        path.write_text(OUTER_FIXTURE + '''
            import json
            path = Path(os.environ['KDD_POSTINIT_RAW_REPORT'])
            report = json.loads(path.read_bytes())
            report.update(executed_ids=[], tests_run=0,
                          fixture_omitted_ids=report['expected_ids'])
            path.write_text(json.dumps(report), encoding='utf-8')
''', encoding='utf-8')
        result, destination = self.execute(0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fixture omission', result.stderr)
        self.assertFalse(destination.exists())

    def test_collect_binds_archive_digest_and_rejects_truncated_lists(self):
        receipts = [self.area / ('candidate-{}.json'.format(i)) for i in (0, 1)]
        for index, path in enumerate(receipts):
            path.write_text(json.dumps(dict(_receipt(index),
                head_sha=self.identity['head_sha'], tree=self.identity['tree'])), encoding='utf-8')
        edits = (
            ('digest', lambda data: data.update({
                'repos/MauricioPerera/KDD/actions/artifacts/821/zip': b'altered'})),
            ('list|count', lambda data: data[API_JOB_LIST].update(total_count=3)),
        )
        for message, edit in edits:
            with self.subTest(message=message):
                try:
                    with self.assertRaisesRegex(ValueError, message):
                        shards.collect(self.root, self.identity, self.replay(receipts, edit))
                except NotImplementedError as error:
                    self.fail(str(error))

    def test_collect_rejects_two_matching_receipts_with_incomplete_discovery(self):
        receipts = [self.area / ('candidate-{}.json'.format(i)) for i in (0, 1)]
        incomplete = [IDS[0][:1], IDS[1]]
        for index, path in enumerate(receipts):
            path.write_text(json.dumps(dict(_receipt(index, incomplete),
                head_sha=self.identity['head_sha'], tree=self.identity['tree'])), encoding='utf-8')
        try:
            with self.assertRaisesRegex(ValueError, 'inventory'):
                shards.collect(self.root, self.identity, self.replay(receipts))
        except NotImplementedError as error:
            self.fail(str(error))

    def test_bound_git_wins_over_executable_in_checkout_and_path(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8'))
        verify = next(step for step in workflow['jobs']['validate']['steps']
                      if step.get('name') == 'Verify Windows post-init partitions')
        driver = b"print('bound-driver-canary')\n"
        (self.root / 'scripts/ci_postinit_shards.py').write_bytes(driver)
        self.git('add', 'scripts/ci_postinit_shards.py')
        self.git('commit', '-qm', 'Driver canary')
        real_git = shutil.which('git')
        self.assertIsNotNone(real_git)
        if os.name == 'nt':
            shutil.copyfile(Path(os.environ['SystemRoot']) / 'System32/where.exe', self.root / 'git.exe')
        else:
            fake = self.root / 'git'
            fake.write_text('#!/bin/sh\nexit 72\n', encoding='utf-8')
            fake.chmod(0o755)
        env = dict(self.env, KDD_POSTINIT_GIT=real_git, GH_TOKEN='synthetic-token',
                   KDD_POSTINIT_TOOL_PATH=self.env['PATH'],
                   KDD_POSTINIT_DRIVER_SHA256=hashlib.sha256(driver).hexdigest(),
                   PATH=str(self.root) + os.pathsep + self.env['PATH'])
        result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', verify['run']],
                                cwd=self.root, env=env, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=35)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stdout.strip(), 'bound-driver-canary')

    def test_api_uses_bound_executable_and_only_github_host(self):
        client = str(Path(sys.executable).resolve())
        malicious = str(self.root)
        with (
            patch.dict(os.environ, dict(GH_TOKEN='synthetic-token', GH_HOST='example.test',
                                         PATH=malicious, KDD_POSTINIT_GH=client)),
            patch.object(shards.subprocess, 'check_output', return_value=b'{}') as execute,
        ):
            self.assertEqual(shards._request(API_JOB_LIST), b'{}')
        argv = execute.call_args.args[0]
        self.assertEqual(argv, [client, 'api', '--hostname', 'github.com', API_JOB_LIST])
        passed = execute.call_args.kwargs['env']
        self.assertEqual(passed['GH_TOKEN'], 'synthetic-token')
        self.assertNotIn('GH_HOST', passed)
        self.assertNotIn(malicious, passed.get('PATH', '').split(os.pathsep))


class WindowsPostInitWorkflow(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(
            (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8'))
        self.validate = self.workflow['jobs']['validate']
        self.steps = {step.get('name'): step for step in self.validate['steps']}

    def test_only_native_windows_defers_and_requires_shards(self):
        command = self.steps["Run each contract's test_command"]
        condition = ' '.join(command.get('env', {}).get('KDD_SKIP_INIT_POST_APPLY_SUITE', '').split())
        native = "matrix.os == 'windows-latest' && " + NATIVE_EVENTS
        self.assertEqual(condition, '${{ ' + native + " && '1' || '' }}")
        verify = self.steps.get('Verify Windows post-init partitions', {})
        self.assertEqual(' '.join(verify.get('if', '').split()), '${{ ' + native + ' }}')
        self.assertIn('collect', verify['run'])
        self.assertEqual(verify['env']['GH_TOKEN'], '${{ github.token }}')
        self.assertNotIn('continue-on-error', verify)
        order = list(self.steps)
        self.assertLess(order.index('Run unit tests (2/2)'), order.index(verify['name']))
        self.assertLess(order.index(verify['name']), order.index('Export Pages CI inventory'))

    def test_two_shards_publish_attempt_scoped_receipts_and_keep_suite_profiles(self):
        job = self.workflow['jobs'].get('postinit_windows')
        self.assertIsNotNone(job, 'two independent post-init executors are required')
        self.assertEqual(job['name'], 'Windows post-init (${{ matrix.shard }})')
        self.assertEqual(' '.join(job['if'].split()), '${{ ' + NATIVE_EVENTS + ' }}')
        self.assertNotIn('needs', job)
        self.assertEqual(job['runs-on'], 'windows-latest')
        self.assertEqual(job['strategy']['matrix']['shard'], [0, 1])
        self.assertIs(job['strategy']['fail-fast'], False)
        by_name = {step.get('name'): step for step in job['steps']}
        run = by_name['Run post-init shard']
        self.assertIn('run', run['run'])
        self.assertNotIn('continue-on-error', run)
        upload = by_name['Upload post-init shard receipt']['with']
        self.assertEqual(upload['name'],
                         'kdd-postinit-shard-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.shard }}')
        self.assertEqual(upload['if-no-files-found'], 'error')
        self.assertIs(upload['overwrite'], False)
        self.assertEqual(self.validate['strategy']['matrix']['os'], ['ubuntu-latest', 'windows-latest'])
        first, second = (self.steps['Run unit tests (1/2)'], self.steps['Run unit tests (2/2)'])
        for step in (first, second):
            self.assertEqual(step['run'],
                'python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . '
                '--start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" '
                '--report-dir "$RUNNER_TEMP/kdd-suite-reports"')
            self.assertNotIn('if', step)
            self.assertNotIn('continue-on-error', step)
            self.assertEqual(step['env']['KDD_SKIP_INIT_POST_APPLY_SUITE'], '1')
        self.assertEqual(first['env']['COVERAGE_PROCESS_START'],
            "${{ (!inputs.reusable_execution && github.repository == 'MauricioPerera/KDD') && "
            "format('{0}/kdd-python-coverage-{1}-{2}/coverage.ini', runner.temp, github.run_id, "
            "github.run_attempt) || '' }}")
        self.assertNotIn('COVERAGE_PROCESS_START', second['env'])

    def test_protected_workflow_verifies_driver_bytes_before_executing(self):
        verify = self.steps.get('Verify Windows post-init partitions', {})
        pin = verify.get('env', {}).get('KDD_POSTINIT_DRIVER_SHA256')
        self.assertIsInstance(pin, str)
        driver = subprocess.check_output(['git', '--no-replace-objects', 'show',
            'HEAD:scripts/ci_postinit_shards.py'], cwd=ROOT) if (ROOT / '.git').exists() else (
            ROOT / 'scripts/ci_postinit_shards.py').read_bytes()
        self.assertEqual(pin, hashlib.sha256(driver.replace(b'\r\n', b'\n')).hexdigest())
        shard = next(step for step in self.workflow['jobs']['postinit_windows']['steps']
                     if step.get('name') == 'Run post-init shard')
        self.assertEqual(shard['env']['KDD_POSTINIT_DRIVER_SHA256'], pin)
        expected_shell = '${{ steps.postinit-python.outputs.python-path }} -I {0}'
        self.assertEqual(verify['shell'], expected_shell)
        self.assertEqual(shard['shell'], expected_shell)
        for job in (self.validate, self.workflow['jobs']['postinit_windows']):
            steps = job['steps']
            bind = next(index for index, step in enumerate(steps) if step.get('id') == 'postinit-tools')
            setup = next(index for index, step in enumerate(steps) if step.get('id') == 'postinit-python')
            self.assertLess(setup, bind)
            self.assertEqual(steps[bind]['working-directory'], '${{ runner.temp }}')
            self.assertNotIn("'GH_TOKEN'", steps[bind]['run'])
            self.assertFalse(any('Select approved references' in step.get('name', '')
                                 for step in steps[:bind]))
        for step in (shard, verify):
            self.assertEqual(step['env']['KDD_POSTINIT_GIT'], '${{ steps.postinit-tools.outputs.git }}')
            self.assertEqual(step['env']['KDD_POSTINIT_GH'], '${{ steps.postinit-tools.outputs.gh }}')
        for required in ('hashlib.sha256', 'KDD_POSTINIT_DRIVER_SHA256', 'RUNNER_TEMP'):
            self.assertIn(required, verify['run'])
        self.assertLess(verify['run'].index('hashlib.sha256'), verify['run'].index('subprocess.run'))


class ReceiptArchive(unittest.TestCase):
    def read(self, raw):
        try:
            return shards.read_receipt_archive(raw)
        except NotImplementedError as error:
            self.fail(str(error))

    def test_reads_the_single_named_receipt(self):
        receipt = _receipt(0)
        raw = _archive([('receipt.json', json.dumps(receipt))])
        self.assertEqual(self.read(raw), receipt)

    def test_rejects_extra_alias_link_and_oversized_entries(self):
        link = zipfile.ZipInfo('receipt.json')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        for entries in ([('receipt.json', '{}'), ('extra.json', '{}')],
                        [('./receipt.json', '{}')], [(link, 'elsewhere')],
                        [('receipt.json', b' ' * (1024 * 1024 + 1))]):
            with self.subTest(entry=str(entries[0][0])):
                with self.assertRaisesRegex(ValueError, 'receipt|archive'):
                    self.read(_archive(entries))

    def test_rejects_duplicate_json_fields(self):
        with self.assertRaisesRegex(ValueError, 'receipt|duplicate'):
            self.read(_archive([('receipt.json', '{"ok": false, "ok": true}')]))


if __name__ == '__main__':
    unittest.main()
