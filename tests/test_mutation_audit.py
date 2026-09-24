import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import mutation_audit


class MutationAuditTests(unittest.TestCase):
    def test_generates_controlled_mutations(self):
        source = "def f(value):\n    if value == 1:\n        return True\n    return False\n"
        mutants = mutation_audit.mutation_sources(source)
        self.assertEqual([item["operator"] for item in mutants], [
            "invert-bool", "flip-comparison", "negate-branch"
        ])
        self.assertEqual(len({item["source"] for item in mutants}), 3)

    def test_real_test_detects_mutant(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "src" / "app.py").write_text(
                "def is_one(value):\n    if value == 1:\n        return True\n    return False\n", encoding="utf-8"
            )
            (repo / "tests" / "test_app.py").write_text(textwrap.dedent("""
                import unittest
                from src.app import is_one
                class TestApp(unittest.TestCase):
                    def test_one(self):
                        self.assertTrue(is_one(1))
                        self.assertFalse(is_one(2))
            """), encoding="utf-8")
            contracts = repo / "contracts"
            contracts.mkdir()
            (contracts / "task.md").write_text(textwrap.dedent("""
                ---
                type: 'Task Contract'
                target: src/app.py
                tests: tests/test_app.py
                test_command: python -m unittest tests.test_app
                ---
            """), encoding="utf-8")
            result = mutation_audit.audit_contract(str(contracts / "task.md"), str(repo))
            self.assertGreaterEqual(result["detected"], 1)
            self.assertEqual(result["survived"], 0)

    def test_non_python_target_is_explicitly_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            repo = Path(root)
            contracts = repo / "contracts"
            contracts.mkdir()
            (contracts / "task.md").write_text(
                "---\ntype: 'Task Contract'\ntarget: src/app.ts\n---\n", encoding="utf-8"
            )
            result = mutation_audit.audit_contract(str(contracts / "task.md"), str(repo))
            self.assertEqual(result["status"], "SKIP")


if __name__ == "__main__":
    unittest.main()
