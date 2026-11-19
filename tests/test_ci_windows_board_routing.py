"""Check the native Windows split against the real workflow and a Bash guard."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
NATIVE = (
    "github.repository == 'MauricioPerera/KDD' && !inputs.reusable_execution && "
    "github.workflow_ref == format('{0}/.github/workflows/validate.yml@{1}', github.repository, github.ref) "
    "&& (github.event_name == 'pull_request' || (github.event_name == 'push' && github.ref == 'refs/heads/main'))"
)
SUITE = "matrix.role != 'win_contracts'"
COMMAND = "matrix.role != 'win_suite'"
PARTIAL_TIMINGS = (
    "${{ matrix.role && format('kdd-timings-source-{0}-{1}-{2}', matrix.role, "
    "github.run_id, github.run_attempt) || format('kdd-timings-{0}-{1}-{2}', "
    "github.run_id, github.run_attempt, matrix.os) }}"
)


class WindowsBoardRouting(unittest.TestCase):
    def setUp(self):
        contents = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.workflow = yaml.safe_load(contents)
        self.jobs = self.workflow['jobs']
        self.validation = self.jobs['validate']
        self.board = self.jobs['board']

    def step(self, job, name):
        matches = [step for step in job['steps'] if step.get('name') == name]
        self.assertEqual(len(matches), 1, name)
        return matches[0]

    def join(self):
        self.assertIn('require_windows', self.jobs)
        return self.jobs['require_windows']

    def native_rows(self, matrix, key):
        self.assertIn(key, matrix)
        text = ' '.join(str(matrix[key]).split())
        start = "${{ fromJSON(" + NATIVE + " && '"
        end = "' || '[]') }}"
        self.assertTrue(text.startswith(start) and text.endswith(end), text)
        return json.loads(text[len(start):-len(end)])

    def test_native_matrix_removes_previous_windows_rows_and_reuses_both_slots(self):
        validate = self.validation['strategy']['matrix']
        board = self.board['strategy']['matrix']
        for rows in (validate, board):
            self.assertEqual(rows['os'], ['ubuntu-latest', 'windows-latest'])
            self.assertEqual(self.native_rows(rows, 'exclude'), [{'os': 'windows-latest'}])
        self.assertEqual(self.native_rows(validate, 'include'), [
            {'os': 'windows-latest', 'role': 'win_contracts'},
            {'os': 'windows-latest', 'role': 'win_suite'},
        ])
        self.assertNotIn('include', board)
        self.assertIs(self.validation['strategy']['fail-fast'], False)
        self.assertEqual(' '.join(self.validation['name'].split()), (
            "${{ matrix.role == 'win_contracts' && 'board (windows-latest)' "
            "|| matrix.role == 'win_suite' && 'Windows validation work' || format('validate ({0})', matrix.os) }}"
        ))

    def test_commands_suites_coverage_and_postinit_have_separate_roles(self):
        native = "!inputs.reusable_execution && github.repository == 'MauricioPerera/KDD'"
        pages = "github.event_name == 'push' && github.ref == 'refs/heads/main' && " + native
        cases = {
            "Run each contract's test_command": COMMAND,
            'Report init command duration': COMMAND + ' && always() && ' + native,
            'Run unit tests (1/2)': SUITE,
            'Run unit tests (2/2)': SUITE,
            'Prepare Python suite coverage': SUITE + ' && ' + native,
            'Report Python suite coverage': SUITE + ' && ' + native,
            'Upload Python suite coverage': SUITE + ' && ' + native,
            'Export Pages CI inventory': SUITE + ' && ' + pages,
            'Upload Pages CI inventory': SUITE + ' && ' + pages,
            'Verify Windows post-init partitions': SUITE + " && matrix.os == 'windows-latest' && " + NATIVE,
        }
        for name, guard in cases.items():
            with self.subTest(name=name):
                step = self.step(self.validation, name)
                condition = ' '.join(step.get('if', '').split())
                self.assertEqual(condition, '${{ ' + guard + ' }}')
                self.assertNotIn('continue-on-error', step)

    def test_existing_windows_board_checks_execute_in_the_contract_role(self):
        for name, command in [('Run Windows Board typecheck', 'npm run typecheck'),
                              ('Run Windows Board tests', 'npm test')]:
            with self.subTest(name=name):
                step = self.step(self.validation, name)
                self.assertEqual(step.get('if'), "${{ matrix.role == 'win_contracts' }}")
                self.assertEqual(step['run'], command)
                self.assertEqual(step['working-directory'], 'tools/kdd-board')
        self.assertNotIn('continue-on-error', self.validation)

    def test_receipt_outputs_are_bound_to_one_upload_and_one_producer_role(self):
        receipt = self.step(self.validation, 'Upload Windows validation receipt')
        self.assertEqual(receipt['id'], 'windows-receipt')
        self.assertEqual(receipt['if'], "${{ matrix.role == 'win_contracts' || matrix.role == 'win_suite' }}")
        self.assertEqual(receipt['with']['path'], '${{ runner.temp }}/kdd-windows-receipts/receipt.json')
        self.assertEqual(receipt['uses'].split()[0],
                         'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9')
        self.assertIn('matrix.role', receipt['with']['name'])
        self.assertIn('github.run_attempt', receipt['with']['name'])
        self.assertEqual(receipt['with']['if-no-files-found'], 'error')
        self.assertIs(receipt['with']['overwrite'], False)
        outputs = self.validation['outputs']
        for role, label in [('win_contracts', 'contract'), ('win_suite', 'suite')]:
            for suffix in ('id', 'digest'):
                with self.subTest(role=role, suffix=suffix):
                    expected = ("${{ matrix.role == '" + role + "' && steps.windows-receipt.outputs.artifact-"
                                + suffix + " || '' }}")
                    self.assertEqual(' '.join(outputs[f'win_{label}_{suffix}'].split()), expected)

    def test_required_check_joins_after_producers_and_keeps_attempt_diagnostics(self):
        join = self.join()
        self.assertEqual(join['needs'], ['validate'])
        self.assertEqual(join['runs-on'], 'ubuntu-latest')
        self.assertEqual(' '.join(join['if'].split()), '${{ always() && ' + NATIVE + ' }}')
        self.assertEqual(' '.join(join['name'].split()), (
            '${{ ' + NATIVE + " && 'validate (windows-latest)' || 'Windows native verification (inactive)' }}"
        ))
        self.assertNotIn('continue-on-error', join)
        self.assertEqual(self.workflow['permissions'], {'contents': 'read', 'actions': 'read'})
        guard = self.step(join, 'Check Windows validation producers')
        download = self.step(join, 'Download Windows validation artifacts')
        verify = self.step(join, 'Verify Windows validation receipts')
        self.assertLess(join['steps'].index(guard), join['steps'].index(download))
        self.assertLess(join['steps'].index(download), join['steps'].index(verify))
        self.assertEqual(download['uses'].split()[0],
                         'actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333')
        self.assertEqual(download['with']['artifact-ids'], (
            '${{ needs.validate.outputs.win_contract_id }},${{ needs.validate.outputs.win_suite_id }}'
        ))
        self.assertIs(download['with']['skip-decompress'], True)
        self.assertEqual(download['with']['digest-mismatch'], 'error')
        self.assertRegex(verify['env']['KDD_WINDOWS_JOIN_DRIVER_SHA256'], r'^[0-9a-f]{64}$')
        self.assertIn('scripts/ci_windows_join.py', verify['run'])
        for arg in ('--repo-root', '--runtime-bundle', '--identity', '--producers', '--contracts', '--suites'):
            self.assertIn(arg, verify['run'])
        self.assertNotIn('continue-on-error', verify)
        partial = self.step(self.validation, 'Upload CI timing diagnostics')
        self.assertEqual(' '.join(partial['with']['name'].split()), PARTIAL_TIMINGS)
        joined = self.step(join, 'Upload joined Windows timing diagnostics')
        self.assertEqual(joined['with']['name'],
                         'kdd-timings-${{ github.run_id }}-${{ github.run_attempt }}-windows-latest')
        self.assertIs(joined['with']['overwrite'], False)

    def test_real_bash_guard_fails_when_a_producer_did_not_supply_valid_outputs(self):
        step = self.step(self.join(), 'Check Windows validation producers')
        self.assertEqual(step['shell'], 'bash')
        self.assertEqual(step['env'], {
            'VALIDATION_STATE': '${{ needs.validate.result }}',
            'CONTRACTS_ID': '${{ needs.validate.outputs.win_contract_id }}',
            'CONTRACTS_DIGEST': '${{ needs.validate.outputs.win_contract_digest }}',
            'SUITES_ID': '${{ needs.validate.outputs.win_suite_id }}',
            'SUITES_DIGEST': '${{ needs.validate.outputs.win_suite_digest }}',
        })
        bash = shutil.which('bash')
        if os.name == 'nt':
            git = Path(shutil.which('git') or 'git.exe').resolve()
            paths = (parent / 'bin/bash.exe' for parent in git.parents)
            bash = next((str(path) for path in paths if path.is_file()), bash)
        self.assertTrue(bash, 'The workflow requires Bash')
        good = dict(VALIDATION_STATE='success', CONTRACTS_ID='11', CONTRACTS_DIGEST='a' * 64,
                    SUITES_ID='12', SUITES_DIGEST='b' * 64)
        bad = [
            {'VALIDATION_STATE': 'failure'}, {'VALIDATION_STATE': 'skipped'},
            {'VALIDATION_STATE': 'cancelled'}, {'CONTRACTS_ID': ''}, {'SUITES_ID': ''},
            {'CONTRACTS_DIGEST': ''}, {'SUITES_DIGEST': ''}, {'SUITES_ID': '11'},
        ]
        for changes in [{}, *bad]:
            with self.subTest(changes=changes):
                result = subprocess.run([bash, '--noprofile', '--norc', '-e', '-o', 'pipefail',
                                         '-c', step['run']], cwd=ROOT, env=dict(os.environ, **(good | changes)),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, not changes, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
