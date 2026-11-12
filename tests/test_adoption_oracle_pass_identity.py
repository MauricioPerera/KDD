"""Prove two managed executions agree on case identity with Git and Python."""

import hashlib
import subprocess
import unittest

import yaml

from tests import test_adoption_trusted_pr
from tests.adoption_remediation_support import AdoptionIntegration


CASE_FIRST = "tests.test_product.Product.test_first"
CASE_SECOND = "tests.test_product.Product.test_second"
CONTRACT = "knowledge/contracts/label.md"
OTHER_CONTRACT = "knowledge/contracts/other.md"
ORACLE = "tests/test_product.py"
HELPER = "tests/test_extra.py"
HELPER_CASE = "tests.test_extra.Extra.test_from_helper"

ORACLE_SOURCE = """\
import os
from pathlib import Path
import unittest
from product import label

SELECTIONS = {selections!r}
MARKER = Path(os.environ['KDD_ADOPTION_TEST_SENTINEL'])


class Product(unittest.TestCase):
    def check_label(self, value):
        with MARKER.open('a', encoding='utf-8') as stream:
            stream.write(self.id() + '\\n')
        self.assertEqual(label(value), value.strip().lower())

    def test_first(self):
        self.check_label(' First ')

    def test_second(self):
        self.check_label(' Second ')


def load_tests(loader, tests, pattern):
    marker = MARKER.with_suffix('.loads')
    previous = int(marker.read_text(encoding='ascii')) if marker.exists() else 0
    marker.write_text(str(previous + 1), encoding='ascii')
    return unittest.TestSuite(Product('test_' + name) for name in SELECTIONS[previous])
"""

HELPER_SOURCE = b"""\
import os
from pathlib import Path
import unittest
from product import label


class Extra(unittest.TestCase):
    def test_from_helper(self):
        with Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).open('a', encoding='utf-8') as stream:
            stream.write(self.id() + '\\n')
        self.assertEqual(label(' Extra '), 'extra')
"""

ADDITIONAL_CASE = b"""\

from tests.test_extra import Extra

load_selected = load_tests


def load_tests(loader, tests, pattern):
    suite = load_selected(loader, tests, pattern)
    suite.addTest(Extra('test_from_helper'))
    return suite
"""


class AdoptionOraclePassIdentityTests(AdoptionIntegration, unittest.TestCase):
    run_step = test_adoption_trusted_pr.TrustedAdoptionPullRequestTests.run_step

    def approve(self, selections, *, other_contract=False, extra_case=False):
        source = ORACLE_SOURCE.format(selections=selections).encode("utf-8")
        if extra_case:
            source += ADDITIONAL_CASE
            self.write(HELPER, HELPER_SOURCE)
        old_seal = hashlib.sha256((self.root / ORACLE).read_bytes()).hexdigest().encode()
        seal = hashlib.sha256(source).hexdigest().encode()
        self.write(ORACLE, source)
        contract = (self.root / CONTRACT).read_bytes().replace(old_seal, seal).replace(
            b"oracle_files: ['tests/test_product.py']",
            b"oracle_files: ['tests/test_product.py', 'tests/__init__.py']")
        if extra_case:
            contract = contract.replace(b"'tests/__init__.py']", b"'tests/__init__.py', 'tests/test_extra.py']")
        self.write(CONTRACT, contract)
        if other_contract:
            self.write(OTHER_CONTRACT, contract.replace(b"task: label\n", b"task: other\n"))
            self.write("knowledge/index.md", (self.root / "knowledge/index.md").read_bytes()
                       + b"- [Other](contracts/other.md)\n")
        self.install()
        self.workflow = yaml.load((self.root / ".github/workflows/kdd-validate.yml").read_text(
            encoding="utf-8"), Loader=yaml.BaseLoader)
        return self.commit("Approve the fixture, contracts and installed launcher")

    def marks(self):
        return (self.root.parent / "oracle-executed").read_text(encoding="utf-8").splitlines()

    def modify_gate_receipt(self, body):
        gate = self.seed / "scripts/validate_test_commands.py"
        source = gate.read_text(encoding="utf-8")
        new = source.replace("    sys.exit(main(sys.argv))", body)
        self.assertNotEqual(source, new)
        gate.write_text(new, encoding="utf-8")

        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.seed), *args],
                                           encoding="utf-8", timeout=30).strip()

        git("add", "scripts/validate_test_commands.py")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-qm", "Pin modified receipt fixture")
        self.first = git("rev-parse", "HEAD")

    def test_equal_counts_with_different_ids_are_rejected(self):
        approved = self.approve((("first",), ("second",)))
        process = self.run_step(approved)
        self.assertEqual(self.marks(), [CASE_FIRST, CASE_SECOND])
        result = self.evidence(process)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(result["stage"], "oracle")
        self.assertIn("different", result["error"].lower())
        self.assertIn("ids", result["error"].lower())

    def test_the_same_global_ids_swapped_between_contracts_are_rejected(self):
        approved = self.approve((("first",), ("second",), ("second",), ("first",)), other_contract=True)
        process = self.run_step(approved)
        self.assertEqual(self.marks(), [CASE_FIRST, CASE_SECOND, CASE_SECOND, CASE_FIRST])
        result = self.evidence(process)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(result["stage"], "oracle")
        self.assertIn("ids", result["error"].lower())

    def test_inverted_order_has_the_same_canonical_receipt_in_terminal_and_ci(self):
        approved = self.approve((("first", "second"), ("second", "first")) * 2)
        hosted = self.run_step(approved)
        terminal = self.invoke("entry", self.root / ".kdd/validate.py", ("--approved-ref", approved))
        self.assertEqual(self.marks(), [CASE_FIRST, CASE_SECOND, CASE_SECOND, CASE_FIRST] * 2)
        for process in (hosted, terminal):
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            record = self.evidence(process)
            self.assertEqual(record["verified_kdd_sha"], self.first)
            self.assertEqual(record["oracle_passes"], [2, 2])
            self.assertEqual(record["executed_tests"], 2)
            self.assertEqual(record.get("oracle_inventory"), [{
                "path": CONTRACT, "ids": [CASE_FIRST, CASE_SECOND],
            }])

    def test_duplicate_case_in_a_contract_cannot_credit_two_executions(self):
        approved = self.approve((("first", "first"), ("first", "first")))
        process = self.run_step(approved)
        self.assertIn(CASE_FIRST, self.marks())
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(self.evidence(process)["stage"], "oracle")
        self.assertIn("duplicate", (process.stdout + process.stderr).lower())

    def test_case_shared_by_two_contracts_counts_in_each_inventory(self):
        approved = self.approve((("first",),) * 4, other_contract=True)
        process = self.run_step(approved)
        self.assertEqual(self.marks(), [CASE_FIRST] * 4)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        record = self.evidence(process)
        self.assertEqual(record["oracle_passes"], [2, 2])
        self.assertEqual(record.get("oracle_inventory"), [
            {"path": CONTRACT, "ids": [CASE_FIRST]}, {"path": OTHER_CONTRACT, "ids": [CASE_FIRST]},
        ])

    def test_counts_from_a_legacy_pin_cannot_substitute_for_a_missing_receipt(self):
        self.modify_gate_receipt('    sys.exit(main(sys.argv[:3]))')
        approved = self.approve((("first",), ("first",)))
        process = self.run_step(approved)
        self.assertEqual(self.marks()[0], CASE_FIRST)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        result = self.evidence(process)
        self.assertEqual(result["stage"], "oracle")
        self.assertIn("receipt", result["error"].lower())

    def test_second_pass_must_produce_a_fresh_receipt(self):
        self.modify_gate_receipt("""    from pathlib import Path
    marker = Path(os.environ['KDD_ADOPTION_TEST_SENTINEL']).with_suffix('.loads')
    if marker.exists() and '--oracle-receipt' in sys.argv:
        offset = sys.argv.index('--oracle-receipt')
        del sys.argv[offset:offset + 2]
    sys.exit(main(sys.argv))""")
        approved = self.approve((("first",), ("second",)))
        process = self.run_step(approved)
        self.assertEqual(self.marks(), [CASE_FIRST, CASE_SECOND])
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        result = self.evidence(process)
        self.assertEqual(result["stage"], "oracle")
        self.assertIn("receipt", result["error"].lower())

    def test_additional_case_in_an_inventoried_helper_is_rejected(self):
        approved = self.approve((("first",), ("first",)), extra_case=True)
        process = self.run_step(approved)
        self.assertEqual(self.marks()[:2], [CASE_FIRST, HELPER_CASE])
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(self.evidence(process)["stage"], "oracle")
        self.assertIn("test_extra.py", process.stdout + process.stderr)

    def test_unrelated_paths_in_a_receipt_fail_even_when_the_gate_is_green(self):
        self.modify_gate_receipt("""    status = main(sys.argv)
    if '--oracle-receipt' in sys.argv:
        from pathlib import Path
        path = Path(sys.argv[sys.argv.index('--oracle-receipt') + 1])
        path.write_text(json.dumps({'schema_version': 1, 'contracts': [
            {'path': 'knowledge/contracts/unrelated.md', 'ids': ['test.wrong']},
        ]}), encoding='utf-8')
    sys.exit(status)""")
        approved = self.approve((("first",), ("first",)))
        process = self.run_step(approved)
        self.assertEqual(self.marks()[0], CASE_FIRST)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual(self.evidence(process)["stage"], "oracle")
        self.assertIn("receipt", self.evidence(process)["error"].lower())

    def test_historical_single_pass_still_works_with_a_legacy_pin(self):
        self.modify_gate_receipt('    sys.exit(main(sys.argv[:3]))')
        self.approve((("first",),))
        process = self.launch()
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(self.marks(), [CASE_FIRST])
        result = self.evidence(process)
        self.assertEqual(result["oracle_passes"], [1])
        self.assertEqual(result["executed_tests"], 1)
        self.assertNotIn("oracle_inventory", result)


if __name__ == "__main__":
    unittest.main()
