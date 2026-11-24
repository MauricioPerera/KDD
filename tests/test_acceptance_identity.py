"""Exercise acceptance on real commits and compare managed case identities."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_contract_acceptance
from scripts.oracle_execution import execute_oracle


ROOT = Path(__file__).resolve().parents[1]
SELECTABLE = """\
import os
from pathlib import Path
import unittest

class Oracle(unittest.TestCase):
    def test_first(self):
        self.assertEqual(1 + 1, 2)

    def test_second(self):
        self.assertEqual(2 + 2, 4)

def load_tests(loader, tests, pattern):
    marker = Path(os.environ["KDD_FIXTURE_RUN_STATE"])
    ran = marker.exists()
    marker.touch()
    names = ("test_first", "test_second")
    if os.environ["KDD_FIXTURE_ALTERNATE"] == "1":
        selected = names[1:] if ran else names[:1]
    else:
        selected = names[::-1] if ran else names
    return unittest.TestSuite(Oracle(name) for name in selected)
"""


BOUND_METHOD = """\
import os
from pathlib import Path
import unittest

def first(self):
    self.assertEqual(2 + 2, 4)

def second(self):
    self.assertEqual(3 + 3, 6)

class Oracle(unittest.TestCase):
    test_value = first

def load_tests(loader, tests, pattern):
    marker = Path(os.environ["KDD_FIXTURE_RUN_STATE"])
    Oracle.test_value = second if marker.exists() else first
    marker.touch()
    return unittest.TestSuite([Oracle("test_value")])
"""


NODE_TESTS = """\
import assert from "node:assert/strict";
import { writeFileSync, existsSync } from "node:fs";
import test from "node:test";

const marker = process.env.KDD_FIXTURE_RUN_STATE;
const repeat = existsSync(marker);
writeFileSync(marker, "");
const alternate = process.env.KDD_FIXTURE_ALTERNATE === "1";
function first() { test("first node case", () => assert.equal(2 + 2, 4)); }
function second() { test("second node case", () => assert.equal(3 + 3, 6)); }
const order = repeat ? [second, first] : [first, second];
if (alternate) order[0]();
else for (const add of order) add();
"""


NODE_SHARED = """\
import assert from "node:assert/strict";
export function register(parent) {
    return parent.test("shared leaf", () => assert.equal(2 + 2, 4));
}
"""

NODE_NESTED = """\
import { existsSync, writeFileSync } from "node:fs";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { register } from "./shared.mjs";

const marker = process.env.KDD_FIXTURE_RUN_STATE;
const repeat = existsSync(marker);
writeFileSync(marker, "");
const alternate = process.env.KDD_FIXTURE_ALTERNATE === "1";
test("suite", { concurrency: true }, async (root) => {
    await Promise.all([
        root.test("parent", async (parent) => {
            await delay(25);
            if (!alternate || !repeat) await register(parent);
        }),
        root.test("parent", async (parent) => {
            if (!alternate || repeat) await register(parent);
        }),
    ]);
});
"""


class AcceptanceIdentity(unittest.TestCase):
    def setUp(self):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("GIT_CONFIG_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        git_environment = patch.dict(os.environ, env, clear=True)
        git_environment.start()
        self.addCleanup(git_environment.stop)
        self.fixture = self.new_fixture("sha1")
        state = tempfile.TemporaryDirectory(prefix="kdd-pass-identity-")
        self.addCleanup(state.cleanup)
        self.state = Path(state.name) / "recorded"

    def new_fixture(self, object_format):
        fixture = test_contract_acceptance.AcceptanceTests()
        with patch.dict(os.environ, {"GIT_DEFAULT_HASH": object_format}):
            fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture

    def execute(self, approved_ref, alternate=False):
        status = self.fixture.git("status", "--short")
        env = dict(os.environ, KDD_FIXTURE_RUN_STATE=str(self.state),
                   KDD_FIXTURE_ALTERNATE=str(int(alternate)))
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(ROOT / "scripts/verify_acceptance.py"),
             "--repo-root", str(self.fixture.root), "--policy", "acceptance.json",
             "--approved-ref", approved_ref],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False,
        )
        self.assertEqual(self.fixture.git("status", "--short"), status)
        return result.returncode, json.loads(result.stdout)

    def set_oracle(self, name, fixture_text=SELECTABLE):
        self.fixture.write(name, fixture_text)
        if name == "oracle.py":
            digest = hashlib.sha256(fixture_text.encode("utf-8")).hexdigest()
            contract = re.sub(r"(?m)^tests_sha256: .+$", "tests_sha256: " + digest,
                              self.fixture.contract_text)
            self.fixture.write("knowledge/contracts/task.md", contract)
        self.fixture.freeze()

    def row(self, result, obligation):
        return next(row for row in result["contracts"][0]["obligations"] if row["obligation"] == obligation)

    def assert_bound_python_names(self, evidence, names):
        actual = []
        for identity in evidence.get("case_ids", []):
            label, digest = identity.split(":")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            actual.append(bytes.fromhex(label).decode("utf-8"))
        self.assertEqual(sorted(actual), sorted(names))

    def assert_two_different_receipts(self, obligation, count=1):
        code, result = self.execute(self.fixture.ref, alternate=True)
        self.assertEqual(code, 1, result)
        self.assertFalse(result["ok"])
        self.assertNotEqual(result["state"], "acceptance_approved")
        row = self.row(result, obligation)
        self.assertEqual(row["status"], "FAIL")
        first, second = row["evidence"]
        self.assertEqual([first["executed_tests"], second["executed_tests"]], [count, count])
        self.assertIn("inventory", json.dumps(row).lower())
        return first, second

    def test_reject_different_ids_with_equal_counts_and_stdout(self):
        self.set_oracle("oracle.py")
        first, second = self.assert_two_different_receipts("oracle-execution")
        self.assertEqual(first["stdout"], second["stdout"])
        self.assert_bound_python_names(first, ["oracle.Oracle.test_first"])
        self.assert_bound_python_names(second, ["oracle.Oracle.test_second"])

    def test_same_python_name_with_a_different_bound_method_is_rejected(self):
        self.set_oracle("oracle.py", BOUND_METHOD)
        first, second = self.assert_two_different_receipts("oracle-execution")
        for receipt in (first, second):
            self.assert_bound_python_names(receipt, ["oracle.Oracle.test_value"])
        self.assertNotEqual(first["case_ids"], second["case_ids"])

    def test_obligation_checks_compare_their_cases(self):
        self.set_oracle("obligations.py")
        first, second = self.assert_two_different_receipts("budget")
        self.assertEqual(first["stdout"], second["stdout"])
        self.assert_bound_python_names(first, ["obligations.Oracle.test_first"])
        self.assert_bound_python_names(second, ["obligations.Oracle.test_second"])

    def test_reordered_equal_inventory_keeps_two_receipts(self):
        self.set_oracle("oracle.py")
        self.fixture.write(
            "second_oracle.py",
            "import unittest\nclass Oracle(unittest.TestCase):\n"
            "    def test_first(self): self.assertEqual(2, 2)\n",
        )
        path = "knowledge/contracts/task.md"
        contract = (self.fixture.root / path).read_text(encoding="utf-8")
        contract = contract.replace("python -m unittest oracle.py",
                                    "python -m unittest oracle.py second_oracle.py")
        contract = contract.replace("'obligations.py']", "'obligations.py', 'second_oracle.py']")
        self.fixture.write(path, contract)
        self.fixture.freeze()
        code, result = self.execute(self.fixture.ref)
        self.assertEqual(code, 0, result)
        row = self.row(result, "oracle-execution")
        self.assertEqual(row["status"], "PASS")
        names = ["oracle.Oracle.test_first", "oracle.Oracle.test_second", "second_oracle.Oracle.test_first"]
        first, second = row["evidence"]
        for receipt in (first, second):
            self.assert_bound_python_names(receipt, names)
        self.assertEqual(sorted(first["case_ids"]), sorted(second["case_ids"]))

    def test_annotated_tag_object_is_not_an_approved_commit(self):
        sha1 = self.fixture
        for object_format, width in (("sha1", 40), ("sha256", 64)):
            with self.subTest(object_format=object_format):
                self.fixture = sha1 if object_format == "sha1" else self.new_fixture("sha256")
                self.fixture.git(
                    "-c", "user.name=Acceptance Test", "-c", "user.email=test@example.invalid",
                    "-c", "tag.gpgSign=false", "tag", "-a", "fixture-tag", "-m", "tag fixture",
                )
                tag = self.fixture.git("rev-parse", "refs/tags/fixture-tag")
                self.assertEqual(len(tag), width)
                self.assertEqual(self.fixture.git("cat-file", "-t", tag), "tag")
                code, rejected = self.execute(tag)
                self.assertEqual(code, 1, rejected)
                self.assertFalse(rejected["ok"])
                self.assertEqual(rejected["contracts"], [])
                self.assertIn("commit", rejected["error"].lower())

    def test_sha1_width_is_not_a_complete_sha256_commit_oid(self):
        self.fixture = self.new_fixture("sha256")
        self.assertEqual(len(self.fixture.ref), 64)
        code, result = self.execute(self.fixture.ref[:40])
        self.assertEqual(code, 1, result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["contracts"], [])

    def test_exact_commit_oid_still_approves_both_git_object_formats(self):
        sha1 = self.fixture
        for object_format, width in (("sha1", 40), ("sha256", 64)):
            with self.subTest(object_format=object_format):
                self.fixture = sha1 if object_format == "sha1" else self.new_fixture("sha256")
                self.assertEqual(len(self.fixture.ref), width)
                code, accepted = self.execute(self.fixture.ref.upper())
                self.assertEqual(code, 0, accepted)
                self.assertEqual(accepted["approved_ref"], self.fixture.ref)

    def node_oracle(self, fixture_text=NODE_TESTS, *, shared=False):
        self.fixture.write("oracle.mjs", fixture_text)
        inventory = ["oracle.mjs", "helper.py", "obligations.py"]
        if shared:
            self.fixture.write("shared.mjs", NODE_SHARED)
            inventory.append("shared.mjs")
        self.seal_node_contract("oracle.mjs", ["oracle.mjs"], inventory)

    def seal_node_contract(self, primary, selected, inventory):
        source = (self.fixture.root / primary).read_text(encoding="utf-8")
        updates = {
            "tests": primary,
            "oracle_files": json.dumps(inventory),
            "tests_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "test_runner": "node-test",
            "test_command": "node --test " + " ".join(selected),
        }
        start, header, body = self.fixture.contract_text.split("---\n", 2)
        self.assertEqual(start, "")
        options = [line for line in header.splitlines() if line.partition(":")[0] not in updates]
        options.extend(key + ": " + value for key, value in updates.items())
        contract = "---\n" + "\n".join(options) + "\n---\n" + body
        self.fixture.write("knowledge/contracts/task.md", contract)
        self.fixture.freeze()

    def node_placements(self, receipt):
        evidence = []
        case_ids = receipt.get("case_ids", [])
        self.assertEqual(len(case_ids), len(set(case_ids)))
        for case_id in case_ids:
            owner, stack = json.loads(case_id)
            self.assertTrue(stack)
            for filename, line, column, name in stack:
                location = Path(filename)
                self.assertFalse(location.is_absolute())
                self.assertNotIn("..", location.parts)
                content = (self.fixture.root / location).read_text(encoding="utf-8").splitlines()
                self.assertGreater(line, 0)
                self.assertLessEqual(line, len(content))
                self.assertGreater(column, 0)
                call = content[line - 1][column - 1:]
                self.assertRegex(call, r'^(?:[A-Za-z_]+\.)?(?:test|describe|it)\(' + re.escape(json.dumps(name)))
            evidence.append((owner, stack[-1][0], tuple(item[3] for item in stack)))
        return sorted(evidence)

    def assert_node_names(self, receipt, expected):
        placements = [("oracle.mjs", "oracle.mjs", (name,)) for name in expected]
        self.assertEqual(self.node_placements(receipt), sorted(placements))

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_node_cases_stay_identified_after_reordering(self):
        self.node_oracle()
        code, result = self.execute(self.fixture.ref)
        self.assertEqual(code, 0, result)
        row = self.row(result, "oracle-execution")
        self.assertEqual(row["status"], "PASS")
        first, second = row["evidence"]
        for receipt in (first, second):
            self.assert_node_names(receipt, ["first node case", "second node case"])
        self.assertEqual(sorted(first["case_ids"]), sorted(second["case_ids"]))

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_node_cases_differ_even_when_counts_are_equal(self):
        self.node_oracle()
        first, second = self.assert_two_different_receipts("oracle-execution")
        self.assert_node_names(first, ["first node case"])
        self.assert_node_names(second, ["second node case"])


    def nested_parents(self, receipt):
        placements = self.node_placements(receipt)
        leaves = [placement for placement in placements if placement[1] == "shared.mjs"]
        self.assertTrue(all(leaf == ("oracle.mjs", "shared.mjs", ("suite", "parent", "shared leaf"))
                            for leaf in leaves))
        stacks = [json.loads(case_id)[1] for case_id in receipt["case_ids"]]
        return sorted(stack[-2][1] for stack in stacks if stack[-1][3] == "shared leaf")

    def nested_parent_lines(self):
        lines = [index for index, line in enumerate(NODE_NESTED.splitlines(), 1)
                 if 'root.test("parent",' in line]
        self.assertEqual(len(lines), 2)
        return lines

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_nested_node_case_moved_to_a_different_parent_is_rejected(self):
        self.node_oracle(NODE_NESTED, shared=True)
        first, second = self.assert_two_different_receipts("oracle-execution", count=4)
        first_parent, second_parent = self.nested_parent_lines()
        self.assertEqual(self.nested_parents(first), [first_parent])
        self.assertEqual(self.nested_parents(second), [second_parent])

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_same_node_registration_under_both_parents_stays_distinct(self):
        self.node_oracle(NODE_NESTED, shared=True)
        code, result = self.execute(self.fixture.ref)
        self.assertEqual(code, 0, result)
        row = self.row(result, "oracle-execution")
        first, second = row["evidence"]
        self.assertEqual(row["status"], "PASS")
        self.assertEqual([first["executed_tests"], second["executed_tests"]], [5, 5])
        self.assertEqual([len(receipt.get("case_ids", [])) for receipt in (first, second)], [5, 5])
        self.assertEqual(sorted(first["case_ids"]), sorted(second["case_ids"]))
        self.assertEqual(self.nested_parents(first), self.nested_parent_lines())

    def multiple_node_files(self):
        self.fixture.write("shared.mjs", 'import { describe, it } from "node:test";\n'
                           'describe("shared root", () => {\n'
                           '    it("shared leaf", () => {});\n'
                           '});\n')
        for filename in ("first.mjs", "second.mjs"):
            self.fixture.write(filename, 'import "./shared.mjs";\n')
        return dict(tests="first.mjs", oracle_files=["first.mjs", "second.mjs", "shared.mjs"],
                    test_runner="node-test", test_command="node --test first.mjs second.mjs")

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_node_default_count_receipt_is_preserved(self):
        metadata = self.multiple_node_files()
        result = execute_oracle(metadata, self.fixture.root, timeout=30)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["executed_tests"], 2)
        self.assertNotIn("case_ids", result)
        expected = {str((self.fixture.root / filename).resolve()): {"executed": 1, "skipped": 0, "ok": True}
                    for filename in ("first.mjs", "second.mjs")}
        self.assertEqual(result["evidence"]["files"], expected)
        legacy_receipt = execute_oracle(metadata, self.fixture.root, timeout=30, record_ids=True)
        self.assertFalse(legacy_receipt["ok"], legacy_receipt)
        self.assertIn("python-unittest", legacy_receipt["error"])

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_node_report_keeps_owner_when_two_selected_files_use_a_helper(self):
        metadata = self.multiple_node_files()
        inventory = metadata["oracle_files"] + ["helper.py", "obligations.py"]
        self.seal_node_contract("first.mjs", ["first.mjs", "second.mjs"], inventory)
        code, result = self.execute(self.fixture.ref)
        self.assertEqual(code, 0, result)
        row = self.row(result, "oracle-execution")
        self.assertEqual(row["status"], "PASS")
        for receipt in row["evidence"]:
            self.assertEqual(receipt["executed_tests"], 2)
            self.assertEqual(self.node_placements(receipt), [
                ("first.mjs", "shared.mjs", ("shared root", "shared leaf")),
                ("second.mjs", "shared.mjs", ("shared root", "shared leaf")),
            ])

    @unittest.skipUnless(shutil.which("node"), "Node is required for the managed Node runner")
    def test_ambiguous_node_id_does_not_approve_a_receipt(self):
        self.node_oracle('import test from "node:test";\n'
                         'for (let i = 0; i < 2; i++) test("same location", () => {});\n')
        code, result = self.execute(self.fixture.ref)
        self.assertEqual(code, 1, result)
        row = self.row(result, "oracle-execution")
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("Duplicate oracle case IDs", json.dumps(row))


if __name__ == "__main__":
    unittest.main()
