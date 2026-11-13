"""Adversarial checks of the two-pass adoption evidence."""

import json
import unittest
from unittest.mock import patch

from tests import test_adoption_oracle_pass_identity as oracle


class AdversarialOracleTests(unittest.TestCase):
    def setUp(self):
        self.consumer = oracle.AdoptionOraclePassIdentityTests()
        self.addCleanup(self.consumer.doCleanups)
        self.consumer.setUp()

    def assert_oracle_rejected(self, process, reason):
        record = self.consumer.evidence(process)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertEqual((record["stage"], record["result"]), ("oracle", "fail"))
        self.assertNotIn("oracle_inventory", record)
        self.assertIn(reason, (process.stdout + process.stderr + record["error"]).lower())

    def clear_marks(self):
        marker = self.consumer.root.parent / "oracle-executed"
        marker.unlink(missing_ok=True)
        marker.with_suffix(".loads").unlink(missing_ok=True)

    def test_a10_malformed_receipts_fail_after_real_execution(self):
        consumer = self.consumer
        attack = consumer.root.parent / "oracle-executed.receipt-input"
        self.change_after_receipt(2, f"receipt.write_bytes(Path({str(attack)!r}).read_bytes())")
        approved = consumer.approve((("first",), ("first",)))
        entry = {"path": oracle.CONTRACT, "ids": [oracle.CASE_FIRST]}
        invalid = {
            "truncated": (b'{"schema_version":', "invalid oracle receipt"),
            "duplicate key": (b'{"schema_version":2,"schema_version":1,"contracts":[]}', "invalid oracle receipt"),
            "boolean version": (json.dumps({"schema_version": True, "contracts": [entry]}), "receipt schema"),
            "missing contract": (json.dumps({"schema_version": 1, "contracts": []}), "selected contracts"),
            "duplicate contract": (json.dumps({"schema_version": 1, "contracts": [entry, entry]}), "repeated contract"),
            "path alias": (json.dumps({"schema_version": 1, "contracts": [dict(entry, path="./" + oracle.CONTRACT)]}),
                           "unexpected or repeated contract"),
            "blank id": (json.dumps({"schema_version": 1, "contracts": [dict(entry, ids=[" "])]}), "invalid case ids"),
            "duplicate id": (json.dumps({"schema_version": 1, "contracts": [dict(entry, ids=entry["ids"] * 2)]}),
                             "invalid case ids"),
        }
        for variant, (payload, reason) in invalid.items():
            with self.subTest(variant=variant):
                self.clear_marks()
                attack.write_bytes(payload.encode("utf-8") if isinstance(payload, str) else payload)
                process = consumer.run_step(approved)
                self.assertEqual(consumer.marks(), [oracle.CASE_FIRST] * 2)
                self.assert_oracle_rejected(process, reason)

    def test_a11_existing_receipt_is_preserved_and_cannot_approve(self):
        consumer = self.consumer
        proof = consumer.root.parent / "receipt-preserved"
        consumer.modify_gate_receipt(f"""    from pathlib import Path
    receipt = Path(sys.argv[sys.argv.index('--oracle-receipt') + 1])
    if receipt.name == 'oracle-pass-2.json':
        receipt.write_bytes(b'foreign receipt')
        status = main(sys.argv)
        Path({str(proof)!r}).write_bytes(receipt.read_bytes())
        sys.exit(status)
    sys.exit(main(sys.argv))""")
        approved = consumer.approve((("first",), ("first",)))
        process = consumer.run_step(approved)
        self.assertEqual(proof.read_bytes(), b"foreign receipt")
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST] * 2)
        self.assert_oracle_rejected(process, "cannot write oracle receipt")

    def test_a11_checkout_receipt_decoys_are_ignored(self):
        consumer = self.consumer
        approved = consumer.approve((("first",), ("first",)))
        decoys = ("oracle-pass-1.json", "oracle-pass-2.json")
        for path in decoys:
            consumer.write(path, b"decoy")
        process = consumer.invoke("entry", consumer.root / ".kdd/validate.py", ("--approved-ref", approved))
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST] * 2)
        self.assertEqual(consumer.evidence(process)["oracle_inventory"],
                         [{"path": oracle.CONTRACT, "ids": [oracle.CASE_FIRST]}])
        for path in decoys:
            self.assertEqual((consumer.root / path).read_bytes(), b"decoy")

    def test_a12_distinct_methods_cannot_share_a_claimed_id(self):
        consumer = self.consumer
        source = oracle.ORACLE_SOURCE.replace(
            "    def check_label", "    def id(self):\n        return 'claimed.same'\n\n    def check_label"
        ).replace("stream.write(self.id()", "stream.write(unittest.TestCase.id(self)")
        with patch.object(oracle, "ORACLE_SOURCE", source):
            approved = consumer.approve((("first",), ("second",)))
        process = consumer.run_step(approved)
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST, oracle.CASE_SECOND])
        self.assert_oracle_rejected(process, "different case ids")

    def change_after_receipt(self, number, statements):
        body = """    from pathlib import Path
    status = main(sys.argv)
    if not status and '--oracle-receipt' in sys.argv:
        receipt = Path(sys.argv[sys.argv.index('--oracle-receipt') + 1])
        if receipt.name == %r:
            root = Path(sys.argv[2])
%s
    sys.exit(status)""" % (f"oracle-pass-{number}.json",
                            "\n".join("            " + line for line in statements.splitlines()))
        self.consumer.modify_gate_receipt(body)

    def test_a13_modified_helper_stops_before_second_pass(self):
        consumer = self.consumer
        self.change_after_receipt(1, "(root / 'tests/__init__.py').write_text('# changed', encoding='ascii')")
        approved = consumer.approve((("first",), ("first",)))
        process = consumer.run_step(approved)
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST])
        self.assert_oracle_rejected(process, "tests/__init__.py")

    def test_a13_new_contract_after_second_receipt_is_rejected(self):
        consumer = self.consumer
        self.change_after_receipt(2, """source = (root / 'knowledge/contracts/label.md').read_bytes()
(root / 'knowledge/contracts/extra.md').write_bytes(source.replace(b'task: label', b'task: extra'))""")
        approved = consumer.approve((("first",), ("first",)))
        process = consumer.run_step(approved)
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST] * 2)
        self.assertTrue((consumer.root / "knowledge/contracts/extra.md").is_file())
        self.assert_oracle_rejected(process, "selected contracts")

    def test_a13_modified_lock_after_second_receipt_is_rejected(self):
        consumer = self.consumer
        self.change_after_receipt(
            2, f"(root / '.kdd/validator.lock').write_text({consumer.second!r}, encoding='ascii')"
        )
        approved = consumer.approve((("first",), ("first",)))
        process = consumer.run_step(approved)
        self.assertEqual(consumer.marks(), [oracle.CASE_FIRST] * 2)
        self.assertEqual((consumer.root / ".kdd/validator.lock").read_text(), consumer.second)
        self.assert_oracle_rejected(process, ".kdd/validator.lock")

    def test_a14_stdout_skip_failure_and_timeout_cannot_approve(self):
        consumer = self.consumer
        source = oracle.ORACLE_SOURCE.replace(
            "        self.assertEqual(label(value), value.strip().lower())",
            """        variant = MARKER.with_suffix('.variant').read_text(encoding='ascii')
        if variant == 'stdout':
            print('PASS: one test executed', flush=True)
            os._exit(0)
        if variant == 'skip':
            self.skipTest('adversarial skip')
        if variant == 'timeout':
            import time
            time.sleep(30)
        self.fail('adversarial failure')""",
        )
        with patch.object(oracle, "ORACLE_SOURCE", source):
            consumer.approve((("first",), ("first",)))
        contract = consumer.root / oracle.CONTRACT
        consumer.write(oracle.CONTRACT, contract.read_bytes().replace(
            b"test_runner: python-unittest", b"test_runner: python-unittest\ntest_timeout: 3"
        ))
        approved = consumer.commit("Approve controlled unsuccessful oracles")
        for variant, diagnostic in (
            ("stdout", "result.json"), ("skip", "skipped=1"),
            ("failure", "adversarial failure"), ("timeout", "timeout"),
        ):
            with self.subTest(variant=variant):
                self.clear_marks()
                (consumer.root.parent / "oracle-executed.variant").write_text(variant, encoding="ascii")
                process = consumer.run_step(approved)
                self.assertEqual(consumer.marks(), [oracle.CASE_FIRST])
                self.assert_oracle_rejected(process, diagnostic)

    def test_a15_reports_the_result_of_an_approved_oracle_forging_evidence(self):
        consumer = self.consumer
        source = oracle.ORACLE_SOURCE.replace(
            "        self.assertEqual(label(value), value.strip().lower())",
            """        import json
        import sys
        file = str(Path(__file__).resolve())
        Path(sys.argv[2]).write_text(json.dumps({{
            'files': {{file: dict(executed=1, skipped=0, ok=True)}},
            'case_ids': {{file: ['synthetic.case']}},
        }}), encoding='utf-8')
        os._exit(0)""",
        )
        with patch.object(oracle, "ORACLE_SOURCE", source):
            approved = consumer.approve((("first",), ("second",)))
        process = consumer.run_step(approved)
        record = consumer.evidence(process)
        self.assertIn(record["result"], {"pass", "fail"})
        self.assertEqual(process.returncode, int(record["result"] == "fail"))
        self.assertEqual(consumer.marks()[0], oracle.CASE_FIRST)
        if record["result"] == "pass":
            self.assertEqual(consumer.marks(), [oracle.CASE_FIRST, oracle.CASE_SECOND])
            self.assertEqual(record["oracle_inventory"], [{"path": oracle.CONTRACT, "ids": ["synthetic.case"]}])
        print("A15 approved Python forgery:", record["result"], flush=True)
