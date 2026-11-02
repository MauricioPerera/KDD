"""Acceptance requires all reviewed obligations and real, protected oracles."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_acceptance import verify_acceptance
from validation_runtime import prepare_runtime


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        prepare_runtime()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.write('target.py', 'VALUE = 1\n')
        oracle = ('import unittest\nfrom target import VALUE\n'
                  'class Oracle(unittest.TestCase):\n'
                  '    def test_value(self): self.assertEqual(VALUE, 1)\n')
        self.write('oracle.py', oracle)
        self.write('obligations.py',
                   'import unittest\nclass Checks(unittest.TestCase):\n'
                   '    def test_reviewed_requirement(self): self.assertTrue(True)\n')
        self.write('helper.py', 'EXPECTED = 1\n')
        template = (Path(__file__).resolve().parents[1] /
                    'knowledge/contracts/oracle-inventory.md').read_text(encoding='utf-8')
        import re
        updates = {'target': 'target.py', 'tests': 'oracle.py',
                   'tests_sha256': hashlib.sha256(oracle.encode()).hexdigest(),
                   'touch_only': "['target.py']",
                   'test_command': 'python -m unittest oracle.py',
                   'oracle_files': "['oracle.py', 'helper.py', 'obligations.py']"}
        for key, value in updates.items():
            template = re.sub(r'^' + key + r':.*$', key + ': ' + value, template, flags=re.M)
        template = template.replace('---\n\n## Intent', 'test_runner: python-unittest\n---\n\n## Intent')
        self.contract_text = template
        self.write('knowledge/contracts/task.md', template)
        self.policy = {'schema_version': 1, 'implementation': ['target.py'], 'pm': [],
                       'contracts': [{'path': 'knowledge/contracts/task.md', 'checks': [
                           {'obligation': name, 'tests': 'obligations.py',
                            'test_runner': 'python-unittest',
                            'test_command': 'python -m unittest obligations.py', 'timeout': 5}
                           for name in ('signature', 'dependencies', 'budget', 'forbids', 'invariants')]}]}
        self.freeze()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
                                       stderr=subprocess.STDOUT, text=True).strip()

    def freeze(self):
        self.write('acceptance.json', json.dumps(self.policy))
        self.git('add', '.')
        self.git('-c', 'user.name=Acceptance Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'approved fixture')
        self.ref = self.git('rev-parse', 'HEAD')

    def verify(self):
        return verify_acceptance(self.root, 'acceptance.json', self.ref)

    def test_complete_matrix_and_bound_evidence(self):
        result = self.verify()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['state'], 'acceptance_approved')
        self.assertEqual(result['approved_ref'], self.ref)
        matrix = result['contracts'][0]['obligations']
        self.assertEqual({row['obligation'] for row in matrix},
                         {'oracle-integrity', 'oracle-execution', 'perimeter',
                          'signature', 'dependencies', 'budget', 'forbids', 'invariants'})
        for row in matrix:
            self.assertEqual(row['status'], 'PASS', row)
            self.assertTrue(row['evidence'], row)
        self.assertEqual(len(result['contracts'][0]['contract_sha256']), 64)

    def test_each_missing_obligation_blocks_acceptance(self):
        for name in ('signature', 'dependencies', 'budget', 'forbids', 'invariants'):
            checks = self.policy['contracts'][0]['checks']
            removed = next(check for check in checks if check['obligation'] == name)
            checks.remove(removed)
            self.freeze()
            result = self.verify()
            self.assertFalse(result['ok'], (name, result))
            self.assertNotEqual(result['state'], 'acceptance_approved')
            checks.append(removed)

    def test_bad_implementation_and_neutralized_helper_are_rejected(self):
        self.write('target.py', 'VALUE = 0\n')
        self.assertFalse(self.verify()['ok'])
        self.write('helper.py', 'EXPECTED = 0\n')
        self.assertFalse(self.verify()['ok'])

    def test_noop_empty_and_missing_inventory_never_approve(self):
        for change in (
                lambda text: text.replace('python -m unittest oracle.py', 'python noop.py'),
                lambda text: text.replace("oracle_files: ['oracle.py', 'helper.py', 'obligations.py']\n", ''),
                lambda text: text.replace('test_runner: python-unittest\n', '')):
            self.write('knowledge/contracts/task.md', change(self.contract_text))
            self.freeze()
            self.assertFalse(self.verify()['ok'])
        self.write('knowledge/contracts/task.md', self.contract_text)
        self.write('oracle.py', 'pass\n')
        self.freeze()
        self.assertFalse(self.verify()['ok'])

    def test_uninventoried_check_and_fake_success_command_fail(self):
        check = self.policy['contracts'][0]['checks'][0]
        check['test_command'] = 'python -c "pass"'
        self.freeze()
        self.assertFalse(self.verify()['ok'])
        check.update(tests='outside.py', test_command='python -m unittest outside.py')
        self.write('outside.py', 'pass\n')
        self.freeze()
        self.assertFalse(self.verify()['ok'])

    def test_outside_and_staged_changes_are_rejected(self):
        self.write('outside.py', 'pass\n')
        self.assertFalse(self.verify()['ok'])
        self.git('add', 'outside.py')
        self.assertFalse(self.verify()['ok'])

    def test_policy_tampering_and_non_sha_reference_are_rejected(self):
        self.policy['contracts'][0]['checks'] = []
        self.write('acceptance.json', json.dumps(self.policy))
        self.assertFalse(self.verify()['ok'])
        self.assertFalse(verify_acceptance(self.root, 'acceptance.json', 'HEAD')['ok'])

    def test_fail_timeout_and_self_modification_are_not_success(self):
        for text in (
                'import unittest\nclass C(unittest.TestCase):\n    def test_bad(self): self.fail("bad")\n',
                'import time\ntime.sleep(4)\n',
                'import unittest\nfrom pathlib import Path\nclass C(unittest.TestCase):\n'
                '    def test_bad(self): Path("target.py").write_text("VALUE = 2\\n")\n'):
            self.write('obligations.py', text)
            self.policy['contracts'][0]['checks'][0]['timeout'] = 1
            self.freeze()
            self.assertFalse(self.verify()['ok'])


if __name__ == '__main__':
    unittest.main()
