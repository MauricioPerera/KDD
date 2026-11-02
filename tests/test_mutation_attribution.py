"""Real controls and mutation attribution; synthetic temporary products only."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

from tests import test_mutation_control_evidence as support
import mutation_audit as audit


def digest(content):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


class MutationAttributionTests(unittest.TestCase):
    def project(self, oracle=support.STRONG):
        return support.MutationControls.project(self, oracle)

    def with_fault(self, statement):
        root, contract, area = self.project()
        oracle = ("from pathlib import Path\n"
                  "if Path.cwd().name.startswith('mutant-'):\n " + statement + '\n' + support.STRONG)
        (root / 'tests/test_app.py').write_text(oracle, encoding='utf-8')
        text = contract.read_text(encoding='utf-8')
        contract.write_text(text.replace(digest(support.STRONG), digest(oracle)), encoding='utf-8')
        return root, contract, area

    def inconclusive(self, statement):
        root, contract, _ = self.with_fault(statement)
        before = {path: (root / path).read_bytes()
                  for path in ('src/app.py', 'tests/test_app.py', 'knowledge/contracts/app.md')}
        result = audit.audit_contract(str(contract), str(root), timeout=5)
        self.assertEqual([control['status'] for control in result['controls']], ['PASS', 'PASS'])
        self.assertEqual({path: (root / path).read_bytes() for path in before}, before)
        self.assertEqual(result['detected'], 0, 'an execution error is not an asserted defect detection')
        self.assertEqual(result['survived'], 0, 'zero executed tests do not demonstrate survival')
        self.assertEqual(result['inconclusive'], 3)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(all(row['status'] == 'INCONCLUSIVE' for row in result['mutants']))

    def test_mutant_import_failure_is_inconclusive_after_healthy_controls(self):
        self.inconclusive('import deliberately_missing_mutant_environment_dependency')

    def test_mutant_os_error_is_inconclusive_after_healthy_controls(self):
        self.inconclusive("raise OSError('synthetic missing fixture resource')")

    def test_nonzero_exit_before_running_tests_is_inconclusive(self):
        self.inconclusive('raise SystemExit(23)')

    def test_zero_exit_without_executed_tests_is_not_a_surviving_mutant(self):
        self.inconclusive('raise SystemExit(0)')

    def test_actual_assertions_still_detect_the_three_changed_targets(self):
        root, contract, _ = self.project()
        result = audit.audit_contract(str(contract), str(root), timeout=5)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['detected'], 3)
        self.assertEqual(result['survived'], 0)
        self.assertEqual(result['inconclusive'], 0)
        self.assertEqual([row['status'] for row in result['controls']], ['PASS', 'PASS'])

    def test_an_executed_but_unrelated_assertion_is_still_a_survivor(self):
        oracle = ('import unittest\nclass OwnTests(unittest.TestCase):\n'
                  ' def test_unrelated(self):self.assertEqual(2+2,4)\n')
        root, contract, _ = self.project(oracle)
        result = audit.audit_contract(str(contract), str(root), timeout=5)
        self.assertEqual(result['detected'], 0)
        self.assertEqual(result['survived'], 3)
        self.assertEqual(result['inconclusive'], 0)
        self.assertEqual(result['status'], 'FAIL')

    def test_receipts_bind_actual_mutant_bytes_outputs_and_failed_case(self):
        root, contract, area = self.project()
        observed = area / 'actual-source-hashes.jsonl'
        prefix = ("import hashlib,json\nfrom pathlib import Path\n"
                  "content=Path('src/app.py').read_bytes().replace(b'\\r\\n',b'\\n').replace(b'\\r',b'\\n')\n"
                  'with Path(' + repr(str(observed)) + ").open('a',encoding='utf-8') as stream:\n"
                  " stream.write(json.dumps({'stage':Path.cwd().name,'sha256':hashlib.sha256(content).hexdigest()})+'\\n')\n")
        oracle = prefix + support.STRONG
        (root / 'tests/test_app.py').write_text(oracle, encoding='utf-8')
        contract.write_text(contract.read_text(encoding='utf-8')
                            .replace(digest(support.STRONG), digest(oracle)), encoding='utf-8')
        original = digest((root / 'src/app.py').read_bytes())
        result = audit.audit_contract(str(contract), str(root), timeout=5)
        self.assertEqual(result['detected'], 3)
        executions = [json.loads(line) for line in observed.read_text(encoding='utf-8').splitlines()]
        actual_mutants = {item['sha256'] for item in executions if item['stage'].startswith('mutant-')}
        self.assertEqual(len(actual_mutants), 3)
        for item in result['mutants']:
            for key in ('source', 'mutant_sha256', 'target_sha256', 'oracle_sha256',
                        'command', 'stdout', 'stderr', 'output_sha256', 'failed_tests'):
                self.assertIn(key, item, 'the experiment must retain its actual failure evidence')
            self.assertEqual(item['mutant_sha256'], digest(item['source']))
            self.assertIn(item['mutant_sha256'], actual_mutants)
            self.assertEqual(item['target_sha256'], original)
            self.assertEqual(item['oracle_sha256'], digest(oracle))
            self.assertEqual(item['command'], 'python -m unittest tests/test_app.py')
            self.assertIsInstance(item['stdout'], str)
            self.assertIsInstance(item['stderr'], str)
            self.assertEqual(item['output_sha256'], hashlib.sha256(
                (item['stdout'] + item['stderr']).encode('utf-8')).hexdigest())
            self.assertIn('tests.test_app.TestApp.test_value', item['failed_tests'])
            self.assertIn('AssertionError', item['stderr'])


if __name__ == '__main__':
    unittest.main()
