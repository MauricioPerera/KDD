"""Exercise context guardrails and safe reports through the real CLI."""

import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'assemble_context.py'
PATTERN = r'(?i)api[_-]?key\s*[=:]\s*\S'
SYNTHETIC = 'api_key=synthetic123'


def assemble_cli(root, contract, task, *, verbose=False, filename='context.json'):
    (root / filename).write_text(json.dumps(contract), encoding='utf-8')
    argv = [sys.executable, str(SCRIPT), filename, task]
    if verbose:
        argv.append('--verbose')
    return subprocess.run(argv, cwd=root, capture_output=True, encoding='utf-8', timeout=20)


def read_manifest(run):
    manifest, = [json.loads(line.removeprefix('CONTEXT_MANIFEST '))
                 for line in run.stdout.splitlines() if line.startswith('CONTEXT_MANIFEST ')]
    return manifest


class TaskGuardrailTests(unittest.TestCase):
    def run_assembler(self, task, *, cap, on_fail='abort', source=None,
                      patterns=(PATTERN,), verbose=False, required_path=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ('x' * 160) if source is None else source.ljust(160)
            (root / 'intro.md').write_text(source, encoding='utf-8')
            contract = {
                'budget': {'max_tokens': 40 + cap, 'output_reserve': 0},
                'slots': [
                    {'id': 'intro', 'source': 'static', 'path': 'intro.md',
                     'priority': 0},
                    {'id': 'user_task', 'source': 'runtime',
                     'priority': 10, 'compaction': 'truncate'},
                ],
                'guardrails': {'regex_deny': {'patterns': list(patterns), 'on_fail': on_fail}},
            }
            if required_path:
                contract['slots'].append({
                    'id': 'required_source', 'source': 'static', 'path': required_path,
                    'priority': 20, 'required': True,
                })
                contract['guardrails']['reference_check'] = {'on_fail': 'report'}
            run = assemble_cli(root, contract, task, verbose=verbose)
        sources = read_manifest(run)['sources']
        return run, next(row['status'] for row in sources if row['slot'] == 'user_task')

    def assert_abort(self, run):
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertIn('ABORT: regex_deny:', run.stderr)
        self.assertNotIn(SYNTHETIC, run.stderr)

    def test_truncated_task_still_aborts(self):
        run, status = self.run_assembler('review ' * 5 + SYNTHETIC, cap=8)
        self.assertEqual(status, 'truncated')
        self.assert_abort(run)

    def test_omitted_task_still_aborts(self):
        run, status = self.run_assembler(SYNTHETIC, cap=0)
        self.assertEqual(status, 'omitted')
        self.assert_abort(run)

    def test_report_mode_flags_omitted_task(self):
        run, status = self.run_assembler(SYNTHETIC, cap=0, on_fail='report')
        self.assertEqual(status, 'omitted')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('guardrails: findings', run.stdout)
        self.assertIn('regex_deny: patron matcheado:', run.stdout)
        self.assertNotIn('ABORT', run.stderr)

    def test_omitted_clean_task_is_allowed(self):
        run, status = self.run_assembler('documentar cambios', cap=0)
        self.assertEqual(status, 'omitted')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('guardrails: ok', run.stdout)

    def test_delivered_file_still_aborts(self):
        run, _ = self.run_assembler('documentar cambios', cap=0, source=SYNTHETIC)
        self.assert_abort(run)

    def test_delivered_match_keeps_precedence_over_original_task(self):
        run, status = self.run_assembler(
            SYNTHETIC, cap=0, source='blocked delivered marker',
            patterns=(PATTERN, 'blocked delivered marker'),
        )
        self.assertEqual(status, 'omitted')
        self.assert_abort(run)
        self.assertIn('patron matcheado: #2', run.stderr)
        self.assertNotIn('patron matcheado: #1', run.stderr)
        self.assertNotIn('blocked delivered marker', run.stderr)
        self.assertNotIn('api[_-]?key', run.stderr)

    def test_both_inputs_matching_report_one_finding(self):
        run, status = self.run_assembler(
            SYNTHETIC, cap=0, source=SYNTHETIC, on_fail='report',
        )
        self.assertEqual(status, 'omitted')
        self.assertEqual(run.returncode, 0, run.stderr)
        findings = [line for line in run.stdout.splitlines()
                    if line.strip().startswith('- regex_deny: patron matcheado:')]
        self.assertEqual(len(findings), 1, run.stdout)

    def test_regex_cannot_join_context_and_original_task(self):
        run, status = self.run_assembler(
            SYNTHETIC, cap=0, patterns=(r'x\s+api[_-]?key=',),
        )
        self.assertEqual(status, 'omitted')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('guardrails: ok', run.stdout)


    def assert_safe_output(self, run, rejected):
        self.assertNotIn(rejected, run.stdout)
        self.assertNotIn(rejected, run.stderr)
        self.assertNotIn('--- context ---', run.stdout)

    def test_blocked_task_content_is_absent_in_both_cli_modes(self):
        for verbose in (False, True):
            with self.subTest(verbose=verbose):
                run, status = self.run_assembler(SYNTHETIC, cap=12, verbose=verbose)
                self.assertEqual(status, 'full')
                self.assert_abort(run)
                self.assert_safe_output(run, SYNTHETIC)

    def test_truncated_and_omitted_task_content_is_absent(self):
        cases = ((SYNTHETIC, 0, 'omitted'),
                 ('review ' * 5 + SYNTHETIC, 8, 'truncated'))
        for task, cap, expected in cases:
            with self.subTest(status=expected):
                run, status = self.run_assembler(task, cap=cap, verbose=True)
                self.assertEqual(status, expected)
                self.assert_abort(run)
                self.assert_safe_output(run, SYNTHETIC)

    def test_blocked_source_is_absent_from_verbose_context(self):
        run, _ = self.run_assembler('documentar cambios', cap=8, source=SYNTHETIC,
                                    verbose=True)
        self.assert_abort(run)
        self.assert_safe_output(run, SYNTHETIC)
        self.assertNotIn('documentar cambios', run.stdout)

    def test_report_mode_flags_match_without_showing_task_or_context(self):
        for verbose in (False, True):
            with self.subTest(verbose=verbose):
                run, status = self.run_assembler(SYNTHETIC, cap=12, on_fail='report',
                                                 verbose=verbose)
                self.assertEqual(status, 'full')
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn('guardrails: findings', run.stdout)
                self.assertIn('patron matcheado: #1', run.stdout)
                self.assertEqual(run.stderr, '')
                self.assert_safe_output(run, SYNTHETIC)

    def test_prefix_match_also_hides_unmatched_value(self):
        run, _ = self.run_assembler(SYNTHETIC, cap=12, patterns=('api_key=',), verbose=True)
        self.assert_abort(run)
        self.assert_safe_output(run, SYNTHETIC.split('=', 1)[1])

    def test_literal_and_reference_diagnostics_do_not_reprint_denied_text(self):
        rejected = 'knowledge/synthetic-do-not-print.md'
        run, _ = self.run_assembler(rejected, cap=15, patterns=(re.escape(rejected),),
                                    required_path=rejected, verbose=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertIn('reference_check:', run.stdout)
        regex_lines = [line.strip() for line in run.stdout.splitlines()
                       if line.strip().startswith('- regex_deny:')]
        self.assertEqual(regex_lines, ['- regex_deny: patron matcheado: #1'])
        self.assertEqual(run.stderr.splitlines(), ['ABORT: CONTEXT_REQUIRED'])
        self.assert_safe_output(run, rejected)
        self.assert_safe_output(run, re.escape(rejected))
        self.assert_safe_output(run, repr(re.escape(rejected)))
        manifest = read_manifest(run)
        by_slot = {row['slot']: row for row in manifest['sources']}
        self.assertIsNone(by_slot['required_source']['path'])
        self.assertNotIn('error', by_slot['required_source'])
        self.assertIn('budget: max_tokens=55 output_reserve=0 available=55', run.stdout)
        delivered = 'x' * 160
        start = len('### slot: intro\n')
        self.assertEqual(by_slot['intro']['delivered_span'], [start, start + len(delivered)])
        self.assertEqual(by_slot['intro']['delivered_sha256'],
                         hashlib.sha256(delivered.encode('utf-8')).hexdigest())

    def test_clean_verbose_keeps_task_and_full_context(self):
        task = 'documentar cambios'
        run, status = self.run_assembler(task, cap=12, verbose=True)
        self.assertEqual(status, 'full')
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('task: ' + task, run.stdout)
        self.assertIn('--- context ---', run.stdout)
        self.assertIn('### slot: user_task\n' + task, run.stdout)
        self.assertEqual(run.stderr, '')


    def test_dynamic_node_labels_and_contract_path_are_private_when_denied(self):
        cut = 'cut-private-canary'
        omitted = 'omitted-private-canary'
        filename = 'contract-private-canary.json'
        task = cut + ' ' + omitted
        contract = {
            'budget': {'max_tokens': 12, 'output_reserve': 0},
            'slots': [{'id': 'nodes', 'priority': 0, 'source': 'dynamic',
                       'provider': 'okf_nodes', 'compaction': 'truncate'}],
            'guardrails': {'regex_deny': {'patterns': [cut], 'on_fail': 'abort'}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge = root / 'knowledge'
            knowledge.mkdir()
            for name in (cut, omitted):
                (knowledge / (name + '.md')).write_text('x' * 160, encoding='utf-8')
            denied = [assemble_cli(root, contract, task, verbose=verbose, filename=filename)
                      for verbose in (False, True)]
            contract['guardrails'] = {}
            control = assemble_cli(root, contract, task, verbose=True, filename=filename)

        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertIn('selected=[{},{}]'.format(cut, omitted), control.stdout)
        self.assertIn('cut=' + cut, control.stdout)
        self.assertIn('omitted=[' + omitted + ']', control.stdout)
        expected_manifest = read_manifest(control)
        self.assertEqual([row['status'] for row in expected_manifest['sources']],
                         ['truncated', 'omitted'])
        for row in expected_manifest['sources']:
            row['path'] = None
        for run in denied:
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertIn('ABORT: regex_deny: patron matcheado: #1', run.stderr)
            for private in (cut, omitted, filename):
                self.assert_safe_output(run, private)
            self.assertEqual(read_manifest(run), expected_manifest)
