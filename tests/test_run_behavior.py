import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import run_behavior


CONTRACT = {"schema": "kdd-behavior/v1", "domain": {"type": "integer", "min": 0, "max": 3}, "cases": {"mode": "exhaustive", "batch_size": 2}, "property": {"op": "eq", "args": [{"var": "result"}, {"op": "mul", "args": [{"var": "input"}, {"const": 2}]}]}}


class RunBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.contract = os.path.join(self.root, "double.behavior.json")
        self.adapters = os.path.join(self.root, "adapters.json")
        self._write_json(self.contract, CONTRACT)

    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def _adapter(self, source="candidate.py", tool="python"):
        self._write_json(self.adapters, {"schema": "kdd-behavior-adapters/v1", "adapters": [{"name": "python", "tool": tool, "source": source, "command": ["{tool}", "{source}"]}]})

    def _source(self, code):
        with open(os.path.join(self.root, "candidate.py"), "w", encoding="utf-8") as handle:
            handle.write(code)

    def test_pass_records_coverage_and_hashes(self):
        self._source("import json,sys\nprint(json.dumps([n*2 for n in json.load(sys.stdin)]))\n")
        self._adapter()
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["adapters"][0]["cases_checked"], 4)
        self.assertIn("contract_sha256", report)
        self.assertIn("source_sha256", report["adapters"][0])

    def test_two_adapters_have_independent_results(self):
        self._source("import json,sys\nprint(json.dumps([n*2 for n in json.load(sys.stdin)]))\n")
        with open(os.path.join(self.root, "candidate.mjs"), "w", encoding="utf-8") as handle:
            handle.write("import{readFileSync}from'node:fs';console.log(JSON.stringify(JSON.parse(readFileSync(0,'utf8')).map(n=>n*3)));\n")
        self._write_json(self.adapters, {"schema": "kdd-behavior-adapters/v1", "adapters": [
            {"name": "python", "tool": "python", "source": "candidate.py", "command": ["{tool}", "{source}"]},
            {"name": "javascript", "tool": "node", "source": "candidate.mjs", "command": ["{tool}", "{source}"]}]})
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual([item["status"] for item in report["adapters"]], ["PASS", "FAIL"])
        self.assertEqual(report["adapters"][1]["counterexamples"][0], {"input": 1, "result": 3})

    def test_bad_result_is_fail_with_counterexample(self):
        self._source("import json,sys\nprint(json.dumps([n*3 for n in json.load(sys.stdin)]))\n")
        self._adapter()
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["adapters"][0]["status"], "FAIL")
        self.assertEqual(report["adapters"][0]["counterexamples"][0], {"input": 1, "result": 3})

    def test_missing_tool_is_unsupported(self):
        self._source("x = 1\n")
        self._adapter(tool="missing-kdd-runtime")
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["adapters"][0]["status"], "UNSUPPORTED")

    def test_invalid_protocol_is_error(self):
        self._source("print('not json')\n")
        self._adapter()
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["adapters"][0]["status"], "ERROR")
        self.assertIn("error", report["adapters"][0])

    def test_invalid_contract_is_error_without_execution(self):
        invalid = dict(CONTRACT, schema="wrong")
        self._write_json(self.contract, invalid)
        self._adapter()
        report = run_behavior.execute(self.root, self.contract, self.adapters)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["error"], "BHV_SCHEMA")


if __name__ == "__main__":
    unittest.main()
