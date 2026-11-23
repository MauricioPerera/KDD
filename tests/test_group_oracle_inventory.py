"""Exercise atomic guarantees through the group CLI, with real Git and unittest."""
import hashlib
import json
import re
import unittest

from tests import test_group_contracts

ATOM = 'contracts/atom.md'
HELPER = 'tests/inventoried_helper.py'
EVENT_SOURCE = "from pathlib import Path\nwith open('events.log', 'a') as log: log.write('child\\n')\n"


class GroupOracleInventory(unittest.TestCase):
    def setUp(self):
        self.fixture = test_group_contracts.GroupContractsIntegration()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def configure_atom(self, *, skip=False):
        fixture = self.fixture
        source = (
            'import unittest\nfrom tests.inventoried_helper import VALUE\n'
            'class Oracle(unittest.TestCase):\n'
            + ("    @unittest.skip('fixture omits its only case')\n" if skip else '')
            + '    def test_actual(self):\n        self.assertEqual(VALUE, 1)\n'
            + "        with open('events.log', 'a') as log: log.write('atom\\n')\n"
        )
        fixture.write('tests/__init__.py', '')
        fixture.write(HELPER, 'VALUE = 1\n')
        fixture.write('tests/atom.py', source)
        original = (fixture.root / ATOM).read_text(encoding='utf-8')
        fields = ('test_command: "python -m unittest tests/atom.py"\n'
                  'test_runner: python-unittest\noracle_files: ' +
                  json.dumps(['tests/atom.py', 'tests/__init__.py', HELPER]))
        configured = re.sub(r'^test_command: .+$', lambda _: fields, original, flags=re.M)
        digest = hashlib.sha256(source.encode()).hexdigest()
        fixture.write(ATOM, re.sub(r"^tests_sha256: .+$", f"tests_sha256: '{digest}'",
                                  configured, flags=re.M))

    def test_drift_in_child_helper_blocks_the_group_before_running_any_command(self):
        self.configure_atom()
        approved = self.fixture.commit()
        self.fixture.write(HELPER, 'VALUE = 2\n')
        result, receipt = self.fixture.invoke(ref=approved)
        self.assertEqual(result.returncode, 2, receipt)
        self.assertEqual(receipt['verdict'], 'INVALID')
        self.assertEqual(receipt['executed'], [])
        self.assertEqual(self.fixture.events(), [])

    def test_all_skipped_child_cannot_pass_or_launch_following_integration(self):
        self.configure_atom(skip=True)
        approved = self.fixture.commit()
        result, receipt = self.fixture.invoke(ref=approved)
        self.assertNotEqual(result.returncode, 0, receipt)
        self.assertFalse(receipt['ok'])
        self.assertEqual(receipt['executed'], [ATOM])
        self.assertEqual(self.fixture.events(), [])

    def test_valid_child_runs_once_then_the_group_integrations(self):
        self.configure_atom()
        approved = self.fixture.commit()
        result, receipt = self.fixture.invoke(ref=approved)
        self.assertEqual(result.returncode, 0, receipt)
        self.assertEqual(receipt['verdict'], 'PASS')
        self.assertEqual(self.fixture.events(), ['atom', 'sub', 'integration'])

    def test_rechecks_child_helper_after_integration_before_further_execution(self):
        self.configure_atom()
        self.fixture.write('tests/sub.py', EVENT_SOURCE +
                           f"Path({HELPER!r}).write_text('VALUE = 2\\n', encoding='utf-8')\n")
        approved = self.fixture.commit()
        result, receipt = self.fixture.invoke(ref=approved)
        self.assertEqual(result.returncode, 2, receipt)
        self.assertEqual(receipt['stage'], 'inputs-changed')
        self.assertEqual(self.fixture.events(), ['atom', 'child'])
