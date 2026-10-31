"""Integration coverage for the context assembler complexity budget."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import assemble_context as assembler


class ExistingBudget(unittest.TestCase):
    def test_assembler_respects_existing_budget(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_budgets.py'),
                                 str(ROOT / 'knowledge/contracts'), '--repo-root', str(ROOT),
                                 '--contract', 'assemble-context'], capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class AssemblerIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-context-complexity-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'knowledge').mkdir()
        (self.root / 'knowledge/index.md').write_text('INDEX\n', encoding='utf-8')
        self.content = 'ABCD' * 8
        (self.root / 'knowledge/static.md').write_text(self.content, encoding='utf-8')
        self.config = {
            'budget': {'max_tokens': 100, 'output_reserve': 10},
            'slots': [
                {'id': 'task', 'source': 'runtime', 'priority': 10},
                {'id': 'document', 'source': 'static', 'path': 'knowledge/static.md',
                 'priority': 0, 'sign': True},
                {'id': 'index', 'source': 'dynamic', 'provider': 'okf_index', 'priority': 5},
            ],
            'guardrails': {'reference_check': {'on_fail': 'report'}},
        }

    def cli(self, config, task, *extra):
        config_path = self.root / 'context.json'
        config_path.write_text(json.dumps(config), encoding='utf-8')
        return subprocess.run([sys.executable, str(ROOT / 'scripts/assemble_context.py'),
                               'context.json', task, *extra], cwd=self.root,
                              env=dict(os.environ, PYTHONUTF8='1'), capture_output=True,
                              timeout=30)

    def test_real_cli_is_deterministic_and_matches_signed_priority_report(self):
        first = self.cli(self.config, 'hello', '-v')
        second = self.cli(self.config, 'hello', '-v')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(second.returncode, 0, second.stderr)
        report = first.stdout.decode('utf-8')
        lines = [line for line in report.splitlines() if line.strip().startswith('[prio')]
        self.assertEqual(len(lines), 3)
        self.assertIn('document', lines[0])
        self.assertIn('index', lines[1])
        self.assertIn('task', lines[2])
        self.assertIn('sign=' + hashlib.sha256(self.content.encode()).hexdigest()[:12], report)
        self.assertIn('guardrails: ok', report)
        self.assertIn('### slot: document\n' + self.content, report.replace('\r\n', '\n'))
        self.assertNotIn('regex_deny', report)

    def test_actual_files_nodes_rank_and_are_cut_with_honest_inventory(self):
        for name in ('alpha', 'beta', 'gamma'):
            text = "---\ntags: ['topic']\n---\n" + name.upper() + ('x' * 400)
            (self.root / 'knowledge' / (name + '.md')).write_text(text, encoding='utf-8')
        config = {'budget': {'max_tokens': 150, 'output_reserve': 0},
                  'slots': [{'id': 'nodes', 'source': 'dynamic', 'provider': 'okf_nodes',
                             'priority': 0, 'compaction': 'truncate'}]}
        result = assembler.assemble(config, 'alpha topic', str(self.root))
        slot = result['slots'][0]
        self.assertEqual(slot['selected'], ['alpha', 'beta', 'gamma'])
        self.assertEqual(slot['cut'], 'beta')
        self.assertEqual(slot['omitted_nodes'], ['gamma'])
        self.assertLess(result['context'].index('ALPHA'), result['context'].index('BETA'))
        self.assertNotIn('GAMMA', result['context'])
        self.assertIn('[...truncated]', result['context'])
        self.assertLessEqual(result['used'], result['available'])

    def test_fallback_nodes_are_in_alphabetical_order(self):
        for name in ('zulu', 'alpha'):
            (self.root / 'knowledge' / (name + '.md')).write_text(name.upper(), encoding='utf-8')
        config = {'budget': {'max_tokens': 500, 'output_reserve': 0},
                  'slots': [{'id': 'nodes', 'source': 'dynamic', 'provider': 'okf_nodes',
                             'priority': 0, 'compaction': 'none'}]}
        result = assembler.assemble(config, 'unrelated query', str(self.root))
        self.assertEqual(result['slots'][0]['selected'], ['alpha', 'index', 'static', 'zulu'])
        self.assertLess(result['context'].index('ALPHA'), result['context'].index('ZULU'))
        self.assertNotIn('cut', result['slots'][0])
        self.assertNotIn('omitted_nodes', result['slots'][0])

    def test_real_cli_guardrail_aborts_without_writing_project_files(self):
        config = copy.deepcopy(self.config)
        config['guardrails']['regex_deny'] = {'patterns': [r'secret\s*:'], 'on_fail': 'abort'}
        before = {p.relative_to(self.root): p.read_bytes()
                  for p in (self.root / 'knowledge').rglob('*') if p.is_file()}
        result = self.cli(config, 'secret : synthetic', '-v')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b'ABORT', result.stderr)
        self.assertIn(b'regex_deny', result.stdout)
        after = {p.relative_to(self.root): p.read_bytes()
                 for p in (self.root / 'knowledge').rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_reference_finding_is_reported_without_abort(self):
        result = self.cli(self.config, 'review knowledge/missing.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'reference_check:', result.stdout)
        self.assertIn(b'knowledge/missing.md', result.stdout)
        self.assertNotIn(b'ABORT', result.stderr)

    def test_regex_report_mode_records_finding_and_still_returns_success(self):
        config = copy.deepcopy(self.config)
        config['guardrails']['regex_deny'] = {'patterns': [r'secret\s*:'], 'on_fail': 'report'}
        result = self.cli(config, 'secret : synthetic')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'regex_deny: patron matcheado', result.stdout)
        self.assertNotIn(b'ABORT', result.stderr)

    def test_invalid_slots_fail_closed_with_specific_diagnostics(self):
        cases = [({'id': 'task', 'source': 'runtime', 'priority': 1}, b'duplicado'),
                 ({'id': 'other', 'source': 'dynamic', 'provider': 'unknown', 'priority': 1},
                  b'provider invalido'),
                 ({'id': 'other', 'source': 'runtime', 'priority': True}, b'priority entera'),
                 ({'id': 'other', 'source': 'runtime', 'priority': 1, 'compaction': 'unknown'},
                  b'compaction invalida')]
        for slot, expected in cases:
            with self.subTest(slot=slot):
                config = copy.deepcopy(self.config)
                config['slots'].append(slot)
                result = self.cli(config, 'hello')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(expected, result.stderr)

    def test_invalid_contracts_fail_before_slot_reading(self):
        cases = [('max_tokens', True, b'budget.max_tokens'),
                 ('output_reserve', -1, b'budget.output_reserve'),
                 ('chars_per_token', 0, b'budget.chars_per_token')]
        for key, value, expected in cases:
            with self.subTest(key=key):
                config = copy.deepcopy(self.config)
                config['budget'][key] = value
                config['slots'][1]['path'] = 'knowledge/absent.md'
                result = self.cli(config, 'hello')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertNotIn(b'ERROR I/O', result.stderr)

    def test_real_cli_invalid_pattern_and_missing_file_have_distinct_exits(self):
        invalid = copy.deepcopy(self.config)
        invalid['guardrails']['regex_deny'] = {'patterns': ['['], 'on_fail': 'abort'}
        result = self.cli(invalid, 'hello')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b'patron invalido', result.stderr)
        missing = copy.deepcopy(self.config)
        missing['slots'][1]['path'] = 'knowledge/absent.md'
        result = self.cli(missing, 'hello')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b'slot document', result.stderr)

    def test_chars_per_token_and_minimum_are_applied_to_real_content(self):
        config = {'budget': {'max_tokens': 20, 'output_reserve': 0, 'chars_per_token': 2},
                  'slots': [{'id': 'document', 'source': 'static', 'priority': 0,
                             'path': 'knowledge/static.md', 'min_tokens': 21}]}
        omitted = assembler.assemble(config, 't', str(self.root))
        self.assertEqual(omitted['slots'][0]['status'], 'omitted')
        config['slots'][0]['min_tokens'] = 0
        included = assembler.assemble(config, 't', str(self.root))
        self.assertEqual(included['slots'][0]['status'], 'included')
        self.assertEqual(included['slots'][0]['tokens'], 16)
        self.assertEqual(included['used'], 16)


if __name__ == '__main__':
    unittest.main()
