"""Additive telemetry wiring must retain the existing validation pipeline."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/validate.yml'
UPLOAD = 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'


class TimingWorkflow(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
        self.job = self.workflow['jobs']['validate']
        self.steps = self.job['steps']

    def named(self, name):
        matches = [s for s in self.steps if s.get('name') == name]
        self.assertEqual(len(matches), 1, 'Expected exactly one ' + name)
        return matches[0]

    def condition(self, step):
        text = step['if'].strip()
        if text.startswith('${{') and text.endswith('}}'):
            text = text[3:-2]
        return ''.join(text.split())

    def test_projection_is_native_only_always_and_follows_existing_suites(self):
        step = self.named('Export CI timing diagnostics')
        self.assertEqual(step['id'], 'ci-timings')
        self.assertEqual(step['shell'], 'bash')
        self.assertEqual(self.condition(step), ''.join((
            "always() && !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD'").split()))
        self.assertGreater(self.steps.index(step), self.steps.index(self.named('Run unit tests (2/2)')))
        command = step['run']
        for fragment in ('python -I scripts/ci_timings.py export', '--repo-root .',
                         '--commands-dir "$RUNNER_TEMP/kdd-command-reports"',
                         '--suites-dir "$RUNNER_TEMP/kdd-suite-reports"',
                         '--output "$RUNNER_TEMP/kdd-ci-timings/timings.json"',
                         '--run-id "$GITHUB_RUN_ID"', '--run-attempt "$GITHUB_RUN_ATTEMPT"',
                         '--head-sha "$GITHUB_SHA"', '--trusted-runtime-ref "$KDD_TRUSTED_RUNTIME_REF"',
                         '--platform "${{ matrix.os }}"'):
            self.assertIn(fragment, command)
        self.assertNotIn('continue-on-error', step)

    def test_upload_is_pinned_and_exposes_only_the_projected_file(self):
        step = self.named('Upload CI timing diagnostics')
        self.assertLess(self.steps.index(self.named('Export CI timing diagnostics')), self.steps.index(step))
        self.assertEqual(step['uses'].split(' #')[0], UPLOAD)
        self.assertEqual(self.condition(step), ''.join((
            "always() && !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD' "
            "&& steps.ci-timings.outcome == 'success'").split()))
        options = step['with']
        self.assertEqual(options['path'], '${{ runner.temp }}/kdd-ci-timings/timings.json')
        self.assertEqual(options['name'],
            'kdd-timings-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.os }}')
        self.assertEqual(options['if-no-files-found'], 'error')
        self.assertEqual(options['retention-days'], 7)
        self.assertEqual(options['overwrite'], False)
        self.assertNotIn('continue-on-error', step)

    def test_validation_workers_matrix_and_both_passes_remain(self):
        self.assertEqual(self.job['strategy']['matrix']['os'], ['ubuntu-latest', 'windows-latest'])
        first, second = (self.named('Run unit tests (' + str(i) + '/2)') for i in (1, 2))
        self.assertEqual(first['run'], second['run'])
        self.assertEqual(self.steps.index(second), self.steps.index(first) + 1)
        self.assertEqual(first['run'].strip(),
            'python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . '
            '--start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" '
            '--report-dir "$RUNNER_TEMP/kdd-suite-reports"')
        self.assertIn('--workers "$KDD_SUITE_WORKERS"', first['run'])
        self.assertIn('COVERAGE_PROCESS_START', first['env'])
        self.assertNotIn('COVERAGE_PROCESS_START', second['env'])
        self.assertIn("'6'", self.job['env']['KDD_SUITE_WORKERS'])
        self.assertIn("'4'", self.job['env']['KDD_SUITE_WORKERS'])
        self.assertIn('--deduplicate --workers "$KDD_CONTRACT_WORKERS"',
                      self.named("Run each contract's test_command")['run'])
        for name in ('Select approved references', 'Check approved contract and oracle baseline',
                     'Run required MCP SDK protocol smoke', 'Report Python suite coverage',
                     'Verify Windows post-init partitions', 'Export Pages CI inventory'):
            self.named(name)


if __name__ == '__main__':
    unittest.main()
