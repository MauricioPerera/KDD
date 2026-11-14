"""CLI guardrail coverage when the task competes for context space."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'assemble_context.py'
PATTERN = r'(?i)api[_-]?key\s*[=:]\s*\S'
SYNTHETIC = 'api_key=synthetic123'


class TaskGuardrailTests(unittest.TestCase):
    def run_assembler(self, task, *, cap, on_fail='abort', source=None, patterns=(PATTERN,)):
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
            (root / 'context.json').write_text(json.dumps(contract), encoding='utf-8')
            run = subprocess.run(
                [sys.executable, str(SCRIPT), 'context.json', task],
                cwd=root, capture_output=True, encoding='utf-8', timeout=20,
            )
        reports = [line.split('CONTEXT_MANIFEST ', 1)[1]
                   for line in run.stdout.splitlines() if line.startswith('CONTEXT_MANIFEST ')]
        self.assertEqual(len(reports), 1, (run.returncode, run.stderr))
        sources = json.loads(reports[0])['sources']
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
        self.assertIn('blocked delivered marker', run.stderr)
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
