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
import zipfile

import yaml

from scripts import ci_postinit_shards as shards


ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'tools/ci/postinit-windows-shards.json'
RUNNER_FILES = ('run_test_suite.py', 'process_tree.py', 'ci_postinit_shards.py',
                'init_post_apply_suite.py')
MODULES = ('test_alpha', 'test_beta', 'test_delta', 'test_gamma')
GROUPS = (('test_alpha', 'test_delta'), ('test_beta', 'test_gamma'))
IDS = [[name + '.Canary.test_body' for name in group] for group in GROUPS]
IDENTITY = dict(run_id='314', run_attempt='2', head_sha='a' * 40, tree='b' * 40,
                runtime_ref='c' * 40, jobs_head_sha='d' * 40)
NATIVE_EVENTS = (
    "github.repository == 'MauricioPerera/KDD' && !inputs.reusable_execution && "
    "(github.event_name == 'pull_request' || "
    "(github.event_name == 'push' && github.ref == 'refs/heads/main'))"
)


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
        self.assertIn('ci_postinit_shards.py collect --repo-root .', verify['run'])
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
        self.assertIn('ci_postinit_shards.py run', run['run'])
        self.assertNotIn('continue-on-error', run)
        upload = by_name['Upload post-init shard receipt']['with']
        self.assertEqual(upload['name'],
                         'kdd-postinit-shard-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.shard }}')
        self.assertEqual(upload['if-no-files-found'], 'error')
        self.assertIs(upload['overwrite'], False)
        self.assertEqual(self.validate['strategy']['matrix']['os'], ['ubuntu-latest', 'windows-latest'])
        first, second = (self.steps['Run unit tests (1/2)'], self.steps['Run unit tests (2/2)'])
        self.assertEqual(first['run'], second['run'])
        self.assertIn('COVERAGE_PROCESS_START', first['env'])
        self.assertNotIn('COVERAGE_PROCESS_START', second['env'])


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
