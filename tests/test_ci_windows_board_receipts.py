"""Full contract, two-pass and Git provenance fixtures for the Windows receipt join."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from tests import test_ci_trusted_execution as trusted_fixture


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'scripts/ci_windows_join.py'


def _json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class WindowsBoardReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture = trusted_fixture.TrustedExecution('runTest')
        cls.addClassCleanup(fixture.doCleanups)
        fixture.workspace()
        fixture.prepare()
        contracts = fixture.repo / 'knowledge/contracts'
        alias = (contracts / 'feature.md').read_text(encoding='utf-8').replace(
            'task: fixture\n', 'task: fixture-alias\n', 1)
        (contracts / 'alias.md').write_text(alias, encoding='utf-8')
        fixture.base = fixture.commit('Review the two command declarations')
        suite_root = fixture.outer / 'suite checkout'
        fixture.git('-c', 'core.autocrlf=false', 'clone', '-q', '--no-hardlinks',
                    str(fixture.repo), str(suite_root))
        cls.fixture = fixture
        cls.suite_root = suite_root
        cls.bundle = fixture.bundle()
        cls.identity = dict(repository='MauricioPerera/KDD', workflow='.github/workflows/validate.yml',
                            run_id=17, run_attempt=2, head_sha=fixture.base,
                            tree=fixture.git('rev-parse', 'HEAD^{tree}'),
                            runtime_ref=fixture.base, platform='windows-latest')
        cls.contracts = cls._contract_receipt()
        cls.suites = cls._suite_receipt()

    @classmethod
    def _execute(cls, profile, number, repo, options):
        report = cls.fixture.outer / f'{profile}-{number}.json'
        argv = [sys.executable, '-I', str(cls.bundle / 'trusted_ci.py'), profile,
                '--repo-root', str(repo), '--report-json', str(report), *options]
        result = cls.fixture.run_command(argv)
        cls.fixture.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = _read(report)
        cls.fixture.assertIs(data['ok'], True)
        cls.fixture.assertEqual(data['trusted_runtime_ref'], cls.fixture.base)
        return data

    @classmethod
    def _receipt(cls, role, **body):
        return dict(schema_version=1, role=role, identity=cls.identity, ok=True, **body)

    @classmethod
    def _contract_receipt(cls):
        data = cls._execute('commands', 1, cls.fixture.repo, [
            '--contracts-dir', 'knowledge/contracts', '--timeout', '600', '--deduplicate', '--workers', '4'])
        rows = []
        for record in data['results']:
            row = {field: record[field] for field in
                   ('path', 'test_command', 'scope', 'shared_from', 'ok', 'exit_code')}
            row['path'] = Path(row['path']).resolve().relative_to(cls.fixture.repo.resolve()).as_posix()
            if row['shared_from']:
                row['shared_from'] = Path(row['shared_from']).resolve().relative_to(cls.fixture.repo.resolve()).as_posix()
            rows.append(row)
        return cls._receipt('contracts', rows=rows)

    @classmethod
    def _suite_receipt(cls):
        passes = []
        for number in (1, 2):
            data = cls._execute('suite', number, cls.suite_root, [
                '--start-directory', 'tests', '--pattern', 'test_*.py', '--workers', '6'])
            record = dict(number=number, runtime=data['trusted_runtime_ref'], workers=data['workers'],
                          expected_ids=data['expected_ids'], executed_ids=data['executed_ids'],
                          ok=data['ok'], errors=len(data['errors']), failures=len(data['failures']),
                          fixture_omitted_ids=data['fixture_omitted_ids'], coverage=None)
            # This fixture exercises coverage metadata binding. Existing coverage
            # integration tests exercise the real producer.
            if number == 1:
                record['coverage'] = dict(pass_no=1, sha256='a' * 64, fragments=1,
                                          lines_total=2, branches_total=1)
            passes.append(record)
        return cls._receipt('suites', passes=passes)

    def setUp(self):
        self.transfers = [deepcopy(self.contracts), deepcopy(self.suites)]
        folder = tempfile.TemporaryDirectory(prefix='kdd windows receipt exchange ')
        self.addCleanup(folder.cleanup)
        self.output = Path(folder.name)
        self.producers = {role: dict(id=index, result='success') for index, role in
                          enumerate(('contracts', 'suites'), 1)}

    def verify(self, *, extra=False, producer_override=None):
        self.assertTrue(DRIVER.is_file(), 'The contracted receipt join is pending implementation.')
        for expected, receipt in zip(('contracts', 'suites'), self.transfers):
            path = self.output / (expected + '.zip')
            with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
                archive.writestr('receipt.json', json.dumps(receipt))
                if extra and expected == 'suites':
                    archive.writestr('unexpected.txt', 'fixture')
            self.producers[expected]['digest'] = hashlib.sha256(path.read_bytes()).hexdigest()
        if producer_override:
            role, field, value = producer_override
            self.producers[role][field] = value
        identity = self.output / 'identity.json'
        producers = self.output / 'producers.json'
        _json(identity, self.identity)
        _json(producers, self.producers)
        return self.fixture.run_command([
            sys.executable, '-I', str(DRIVER), 'verify',
            '--repo-root', str(self.fixture.repo), '--runtime-bundle', str(self.bundle),
            '--identity', str(identity), '--producers', str(producers),
            '--contracts', str(self.output / 'contracts.zip'),
            '--suites', str(self.output / 'suites.zip'),
        ])

    def rejects(self, **options):
        self.assertEqual(self.verify(**options).returncode, 2)

    def test_git_and_runtime_fixture_executes_one_command_and_both_passes(self):
        self.assertEqual((self.fixture.repo / 'runs').read_text(encoding='utf-8'), '1')
        self.assertEqual((self.suite_root / 'runs').read_text(encoding='utf-8'), '2')
        command, shared = self.contracts['rows']
        self.assertEqual(shared['shared_from'], command['path'])
        expected = ['test_feature.Feature.test_value']
        for record in self.suites['passes']:
            self.assertEqual(record['expected_ids'], expected)
            self.assertEqual(record['executed_ids'], expected)

    def test_two_complete_producers_pass(self):
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(json.loads(result.stdout)['ok'], True)

    def test_other_attempt_fails_with_a_matching_upload_digest(self):
        self.transfers[1]['identity']['run_attempt'] += 1
        self.rejects()

    def test_missing_command_row_fails(self):
        self.transfers[0]['rows'].pop()
        self.rejects()

    def test_same_counts_and_different_case_fail(self):
        # Change both executed lists together while retaining the discovery inventory.
        for record in self.transfers[1]['passes']:
            record['executed_ids'] = ['test_feature.Feature.unexpected']
        self.rejects()

    def test_coverage_on_second_pass_fails(self):
        first, second = self.transfers[1]['passes']
        second['coverage'] = first['coverage']
        self.rejects()

    def test_missing_fixture_case_fails(self):
        first = self.transfers[1]['passes'][0]
        first['fixture_omitted_ids'] = first['expected_ids']
        self.rejects()

    def test_incomplete_producer_cannot_satisfy_join(self):
        self.rejects(producer_override=('contracts', 'result', 'skipped'))

    def test_archive_must_match_producer_digest(self):
        self.rejects(producer_override=('suites', 'digest', 'b' * 64))

    def test_archive_with_an_extra_member_fails(self):
        self.rejects(extra=True)


if __name__ == '__main__':
    unittest.main()
