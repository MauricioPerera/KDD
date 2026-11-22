"""Exercise the compact receipt through real Git, trusted suite runs and ZIP exchange."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from tests import test_ci_trusted_execution as trusted


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'scripts/ci_windows_join.py'
MIB = 1024 * 1024
GENERATED = """import unittest


class ReceiptValidationAtScale(unittest.TestCase):
    def check_case(self):
        self.assertTrue(self._testMethodName[-5:].isdigit())


for number in range(2660):
    name = 'test_evidence_of_expected_and_executed_case_id_on_the_native_windows_runner_'
    setattr(ReceiptValidationAtScale, name + f'{number:05}', ReceiptValidationAtScale.check_case)
"""


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('utf-8') + b'\n'


def _load(path):
    return json.loads(path.read_bytes())


def _digest(ids):
    return hashlib.sha256(('\n'.join(sorted(ids)) + '\n').encode('utf-8')).hexdigest()


def _zip(directory, role, member, data):
    target = directory / (role + '.zip')
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        archive.writestr(member, data)
    return target, hashlib.sha256(target.read_bytes()).hexdigest()


class CompactWindowsReceipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixture = trusted.TrustedExecution('runTest')
        cls.addClassCleanup(fixture.doCleanups)
        fixture.workspace()
        fixture.prepare()
        cls.fixture = fixture
        cls.runtime = fixture.base
        cls.bundle = fixture.bundle()
        (fixture.repo / 'tests/test_receipt_inventory_scale.py').write_text(GENERATED, encoding='utf-8')
        (fixture.repo / 'scripts/ci_timings.py').write_bytes((ROOT / 'scripts/ci_timings.py').read_bytes())
        head = fixture.commit('Review the real scale oracle and its timing producer')
        cls.identity = dict(repository='MauricioPerera/KDD', workflow='.github/workflows/validate.yml',
                            platform='windows-latest', run_id=211, run_attempt=7, head_sha=head,
                            tree=fixture.git('rev-parse', 'HEAD^{tree}'), runtime_ref=cls.runtime)
        cls.suite_temp = fixture.outer / 'suites'
        cls.command_temp = fixture.outer / 'commands'
        cls.suite_reports = cls._suites()
        cls._run_report(cls.command_temp, 'commands', 1, [
            '--contracts-dir', 'knowledge/contracts', '--workers', '4', '--deduplicate'])
        discovered = fixture.run_command([sys.executable, '-I', str(ROOT / 'site/ci_inventory.py'),
                                          'discover', '--repo-root', str(fixture.repo)])
        fixture.assertEqual(discovered.returncode, 0, discovered.stdout + discovered.stderr)
        cls.ids = json.loads(discovered.stdout)
        fixture.assertEqual(len(cls.ids), 2661)
        cls.inventory = _digest(cls.ids)
        # Model the uploader's immutable coverage metadata. The covered suite
        # and the two pass reports are executed through the real runtime.
        cls.coverage = _json_bytes({
            'kdd': dict(head_sha=head, platform='windows-latest',
                        run_id='211', attempt='7', suite_pass=1, fragments=1),
            'totals': dict(num_statements=2, num_branches=1),
        })
        path = cls.suite_temp / 'kdd-python-coverage-211-7' / 'coverage.json'
        path.parent.mkdir()
        path.write_bytes(cls.coverage)

    @classmethod
    def _run_report(cls, temp, role, number, options):
        name = 'suite' if role == 'suite' else 'command'
        directory = temp / ('kdd-' + name + '-reports')
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'evidence-{number}.json'
        result = cls.fixture.run_command([sys.executable, '-I', str(cls.bundle / 'trusted_ci.py'),
            role, '--repo-root', str(cls.fixture.repo), '--report-json', str(path), *options])
        cls.fixture.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return path

    @classmethod
    def _suites(cls):
        return [cls._run_report(cls.suite_temp, 'suite', n, [
            '--start-directory', 'tests', '--pattern', 'test_*.py', '--workers', '6'])
            for n in (1, 2)]

    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='kdd compact receipt ')
        self.addCleanup(directory.cleanup)
        self.exchange = Path(directory.name)

    def produce(self, role='suites', *, rejection=None):
        temp = self.suite_temp if role == 'suites' else self.command_temp
        output = temp / 'kdd-windows-receipts' / 'receipt.json'
        output.unlink(missing_ok=True)
        identity = self.identity
        execution = dict(self.fixture.env, RUNNER_TEMP=str(temp),
                         GITHUB_SHA=identity['head_sha'], GITHUB_REPOSITORY=identity['repository'],
                         GITHUB_RUN_ID=str(identity['run_id']), GITHUB_RUN_ATTEMPT=str(identity['run_attempt']),
                         KDD_TRUSTED_RUNTIME_REF=self.runtime)
        proc = self.fixture.run_command([sys.executable, '-I', str(DRIVER), 'produce',
            '--repo-root', str(self.fixture.repo), '--role', role], env=execution)
        if rejection:
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn(rejection, proc.stdout + proc.stderr)
            self.assertFalse(output.exists())
            return None
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertLessEqual(output.stat().st_size, MIB)
        return _load(output)

    def verify(self, suite_data, *, expected=0, error=None):
        contract, contract_sha = _zip(self.exchange, 'contracts', 'receipt.json',
                                      _json_bytes(self.produce('contracts')))
        suite, suite_sha = _zip(self.exchange, 'suites', 'receipt.json', suite_data)
        coverage, coverage_sha = _zip(self.exchange, 'coverage', 'coverage.json', self.coverage)
        identity = self.exchange / 'identity.json'
        producers = self.exchange / 'producers.json'
        timings = self.exchange / 'timings.json'
        timings.unlink(missing_ok=True)
        identity.write_bytes(_json_bytes(self.identity))
        producers.write_bytes(_json_bytes({
            role: dict(id=position, digest=digest, result='success')
            for position, (role, digest) in enumerate(
                (('contracts', contract_sha), ('suites', suite_sha), ('coverage', coverage_sha)), 1)
        }))
        proc = self.fixture.run_command([sys.executable, '-I', str(DRIVER), 'verify',
            '--repo-root', str(self.fixture.repo), '--runtime-bundle', str(self.bundle),
            '--identity', str(identity), '--producers', str(producers),
            '--suite-inventory-sha256', self.inventory, '--contracts', str(contract),
            '--suites', str(suite), '--coverage', str(coverage), '--timings-output', str(timings)])
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        if error:
            self.assertIn(error, proc.stdout + proc.stderr)
            self.assertFalse(timings.exists())
        if expected == 0:
            return json.loads(proc.stdout), _load(timings)
        return None

    @contextmanager
    def changed_report(self, number, field, value):
        report = self.suite_reports[number]
        info = report.stat()
        stamp = (info.st_atime_ns, info.st_mtime_ns)
        raw = report.read_bytes()
        data = json.loads(raw)
        data[field] = value
        report.write_bytes(_json_bytes(data))
        os.utime(report, ns=stamp)
        try:
            yield
        finally:
            report.write_bytes(raw)
            os.utime(report, ns=stamp)

    def test_large_receipt_stores_one_complete_list_and_fits_the_existing_limit(self):
        receipt = self.produce()
        self.assertEqual(receipt['schema_version'], 2)
        self.assertEqual(receipt['inventory'], self.ids)
        self.assertEqual(set(receipt), {'schema_version', 'role', 'identity', 'ok',
                                        'inventory', 'passes', 'timing'})
        self.assertEqual(set(receipt['timing']), {'schema_version', 'kind', 'identity',
                                                  'complete', 'missing', 'sources'})
        self.assertEqual(receipt['timing']['missing'], ['commands-report'])
        self.assertIs(receipt['timing']['complete'], False)
        expanded = deepcopy(receipt)
        del expanded['inventory']
        expanded['schema_version'] = 1
        for number, (row, legacy) in enumerate(zip(receipt['passes'], expanded['passes']), 1):
            self.assertEqual(row['number'], number)
            for key in ('expected_ids', 'executed_ids'):
                self.assertNotIn(key, row)
                self.assertEqual(row[key + '_sha256'], self.inventory)
                del legacy[key + '_sha256']
                legacy[key] = self.ids
        self.assertGreater(len(_json_bytes(expanded)), MIB)
        self.assertLess(2 * len(_json_bytes(receipt)), len(_json_bytes(expanded)))

    def test_real_producers_join_with_all_cases_and_the_first_pass_coverage(self):
        receipt = self.produce()
        joined, timings = self.verify(_json_bytes(receipt))
        self.assertEqual(joined, dict(ok=True, contracts=1, passes=[2661, 2661],
                                     suite_inventory_sha256=self.inventory,
                                     coverage_sha256=hashlib.sha256(self.coverage).hexdigest()))
        self.assertEqual([row['kind'] for row in timings['sources']], ['commands', 'suite', 'suite'])
        suite_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in self.suite_reports}
        self.assertEqual({row['source_sha256'] for row in timings['sources'][1:]}, suite_hashes)
        self.assertEqual(receipt['passes'][0]['coverage']['pass_no'], 1)
        self.assertIsNone(receipt['passes'][1]['coverage'])

    def test_producer_checks_expected_and_executed_ids_in_each_pass(self):
        changed = [*self.ids[:-1], 'test_replacement.Fixture.test_replacement']
        for number in (0, 1):
            for field in ('expected_ids', 'executed_ids'):
                with self.subTest(pass_number=number + 1, field=field):
                    with self.changed_report(number, field, changed):
                        self.produce(rejection='suite inventory')

    def test_producer_rejects_a_different_but_internally_matching_pass(self):
        changed = sorted([*self.ids[:-1], 'test_replacement.Fixture.test_replacement'])
        with self.changed_report(1, 'expected_ids', changed):
            with self.changed_report(1, 'executed_ids', changed):
                self.produce(rejection='suite inventory')

    def test_producer_rejects_duplicate_ids_with_the_same_count(self):
        with self.changed_report(1, 'executed_ids', [*self.ids[:-1], self.ids[0]]):
            self.produce(rejection='duplicate suite IDs')

    def test_join_checks_each_digest_and_the_independent_inventory(self):
        original = self.produce()
        for number in (0, 1):
            for field in ('expected_ids_sha256', 'executed_ids_sha256'):
                altered = deepcopy(original)
                altered['passes'][number][field] = 'b' * 64
                with self.subTest(pass_number=number + 1, field=field):
                    self.verify(_json_bytes(altered), expected=2, error='suite inventory')
        substitute = [*self.ids[:-1], 'test_substitute.Fixture.test_substitute']
        altered = deepcopy(original)
        altered['inventory'] = sorted(substitute)
        for row in altered['passes']:
            row['expected_ids_sha256'] = row['executed_ids_sha256'] = _digest(substitute)
        self.verify(_json_bytes(altered), expected=2, error='suite inventory')

    def test_v2_preserves_same_attempt_runtime_and_pass_metadata_checks(self):
        receipt = self.produce()
        stale = deepcopy(receipt)
        stale['identity']['run_attempt'] += 1
        self.verify(_json_bytes(stale), expected=2, error='stale or mismatched receipt')
        for index in (0, 1):
            invalid = {'number': 2 - index, 'runtime': self.identity['head_sha'],
                       'workers': 5, 'ok': False, 'fixture_omitted_ids': [self.ids[0]]}
            for field, value in invalid.items():
                with self.subTest(pass_number=index + 1, field=field):
                    changed = deepcopy(receipt)
                    changed['passes'][index][field] = value
                    self.verify(_json_bytes(changed), expected=2, error='invalid suite pass')

    def test_join_rejects_noncanonical_order_and_second_pass_coverage(self):
        receipt = self.produce()
        unordered = deepcopy(receipt)
        unordered['inventory'].reverse()
        self.verify(_json_bytes(unordered), expected=2, error='suite inventory')
        receipt['passes'][1]['coverage'] = receipt['passes'][0]['coverage']
        self.verify(_json_bytes(receipt), expected=2, error='coverage is missing, misplaced or inconsistent')

    def test_join_rejects_an_additional_inventory_inside_timing_diagnostics(self):
        original = self.produce()
        for field in ('inventory', 'missing'):
            with self.subTest(field=field):
                receipt = deepcopy(original)
                receipt['timing'][field] = self.ids
                payload = _json_bytes(receipt)
                self.assertLess(len(payload), MIB)
                self.verify(payload, expected=2, error='unexpected diagnostics metadata')
        original['timing']['complete'] = True
        self.verify(_json_bytes(original), expected=2, error='unexpected diagnostics metadata')

    def test_receipt_transport_still_rejects_an_uncompressed_member_over_one_mib(self):
        payload = _json_bytes(self.produce())
        self.verify(payload + b' ' * (MIB + 1 - len(payload)),
                    expected=2, error='invalid archive member')

    def test_workflow_pins_the_receipt_driver(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8'))
        steps = workflow['jobs']['require_windows']['steps']
        verifier, = [step for step in steps if step.get('name') == 'Verify Windows validation receipts']
        pin = verifier['env']['KDD_WINDOWS_JOIN_DRIVER_SHA256']
        if (ROOT / '.git').exists():
            raw = subprocess.check_output(['git', '--no-replace-objects', '-C', str(ROOT),
                                           'show', 'HEAD:scripts/ci_windows_join.py'], timeout=20)
        else:
            # The initialized source copy can have CRLF and has no Git blob.
            raw = DRIVER.read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(pin, hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
