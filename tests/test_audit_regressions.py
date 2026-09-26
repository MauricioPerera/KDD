"""Independent regressions from the September KDD audit; no frozen oracle edits."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import behavior_contract as bc
import mcp_gate_dispatch as gd
import preflight
import rule_engine
import run_behavior as runner
import validate_behavior
import validate_contracts
import validate_okf
import validate_skills
import validate_perimeter
import validate_test_commands as commands

CONTRACT = {'schema': bc.SCHEMA, 'domain': {'type': 'integer', 'min': 0, 'max': 2},
            'cases': {'mode': 'exhaustive', 'batch_size': 3},
            'property': {'op': 'eq', 'args': [{'var': 'input'}, {'var': 'result'}]}}


class AuditRegressions(unittest.TestCase):
    def test_quoted_commands_share_the_same_dialect(self):
        for scalar in ['"python -c \\"print(1)\\""', "'python -c ''print(1)'''", 'python ok.py']:
            text = '\n---\ntest_command: ' + scalar + '\n---\n'
            expected = commands.extract_test_command(text)
            for parser in [validate_contracts, validate_okf, validate_skills, validate_perimeter]:
                self.assertEqual(parser.parse_frontmatter(text)[0]['test_command'], expected)

    def test_nonfinite_numbers_fail_bounds_with_or_without_integer_flag(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            for integer in [False, True]:
                with self.subTest(value=value, integer=integer):
                    rules = {'bounds': [{'field': 'x', 'min': 0, 'max': 10, 'integer': integer}]}
                    self.assertTrue(rule_engine.evaluate(rules, {'x': value}, {}))
                    self.assertTrue(rule_engine.evaluate({'type': [{'field': 'x', 'kind': 'number'}]}, {'x': value}, {}))

    def test_malformed_expression_nodes_are_findings(self):
        for node in [{'var': []}, {'var': {}}, {'op': [], 'args': []}, {'op': {}, 'args': []}]:
            self.assertIn('BHV_PROPERTY', [rule for rule, _ in bc.validate(dict(CONTRACT, property=node))])

    def test_file_argument_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'bad.behavior.json'
            file.write_text('{broken', encoding='utf8')
            self.assertEqual(validate_behavior.main([str(file)]), 1)

    def test_canonical_command_parser_and_mixed_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, prefix, code in [('a', '', 0), ('b', '\n \n', 1)]:
                Path(tmp, name + '.py').write_text('raise SystemExit({})'.format(code), encoding='utf8')
                text = prefix + '---\ntest_command: "python {}.py"\n---\n'.format(name)
                self.assertEqual(commands.extract_test_command(text), validate_contracts.parse_frontmatter(text)[0]['test_command'])
                Path(tmp, name + '.md').write_text(text, encoding='utf8')
            results = commands.run_all(tmp, tmp)
            self.assertEqual([r['ok'] for r in results], [True, False])

    def test_behavior_is_dispatched_and_preflight_propagates_failure(self):
        self.assertIn('validate_behavior', gd.LEVEL1_GATES)
        def fake(name, params, repo_root, timeout=120):
            return {'exit_code': int(name == 'validate_behavior'), 'stdout': '', 'stderr': ''}
        self.assertFalse(preflight.run_preflight(runner=fake)['overall_ok'])
        self.assertEqual(gd.build_argv('validate_behavior', {})[2:], ['behavior'])

    def test_approved_contract_cannot_be_weakened(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c, r = root / 'c.json', root / 'r.json'
            c.write_text(json.dumps(CONTRACT), encoding='utf8')
            r.write_text(json.dumps({'schema': 'kdd-behavior-adapters/v1', 'adapters': [
                {'name': 'python', 'tool': sys.executable, 'source': 'a.py', 'command': ['{tool}', '{source}']}]}), encoding='utf8')
            Path(root, 'a.py').write_text('import sys,json\nprint(json.dumps([0 for x in json.load(sys.stdin)]))', encoding='utf8')
            approved = {'contract_sha256': runner._hash(c), 'adapters_sha256': runner._hash(r)}
            self.assertEqual(runner.execute(root, c, r, **approved)['status'], 'FAIL')
            weakened = copy.deepcopy(CONTRACT)
            weakened['property'] = {'op': 'eq', 'args': [{'var': 'result'}, {'var': 'result'}]}
            c.write_text(json.dumps(weakened), encoding='utf8')
            with patch.object(runner, '_run', side_effect=AssertionError('must not execute')):
                report = runner.execute(root, c, r, **approved)
                self.assertEqual(report['error'], 'CONTRACT_HASH_MISMATCH')
                self.assertEqual(runner.execute(root, c, r)['status'], 'ERROR')
            cli = subprocess.run([sys.executable, runner.__file__, '--root', tmp, '--contract', str(c),
                                  '--contract-sha256', approved['contract_sha256'], '--adapters', str(r),
                                  '--adapters-sha256', approved['adapters_sha256']], capture_output=True, text=True)
            self.assertEqual(cli.returncode, 1)
            self.assertEqual(json.loads(cli.stdout)['error'], 'CONTRACT_HASH_MISMATCH')


if __name__ == '__main__':
    unittest.main()
