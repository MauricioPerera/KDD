"""Check the native Windows split against the real workflow and a Bash guard."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
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
    "${{ matrix.role != 'full' && format('kdd-timings-source-{0}-{1}-{2}', matrix.role, "
    "github.run_id, github.run_attempt) || format('kdd-timings-{0}-{1}-{2}', "
    "github.run_id, github.run_attempt, matrix.os) }}"
)
TRUSTED_COMMAND = 'python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py"'
SUITE_COMMAND = (TRUSTED_COMMAND + ' suite --repo-root . --start-directory tests --pattern "test_*.py"'
                 ' --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"')
CONTRACT_COMMAND = (TRUSTED_COMMAND + ' commands --repo-root . --contracts-dir "$KDD_CONTRACTS_DIR"'
                    ' --timeout 600 --deduplicate --workers "$KDD_CONTRACT_WORKERS"'
                    ' --report-dir "$RUNNER_TEMP/kdd-command-reports"'
                    ' --exclusive-commands-json "$KDD_EXCLUSIVE_CONTRACT_COMMANDS"')
NATIVE_REPO = "!inputs.reusable_execution && github.repository == 'MauricioPerera/KDD'"


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

    def windows(self):
        self.assertIn('validate_windows', self.jobs)
        return self.jobs['validate_windows']

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
        self.assertEqual(validate['role'], ['full'])
        self.assertNotIn('include', validate)
        self.assertNotIn('include', board)
        self.assertEqual(self.validation.get('name'), 'validate (${{ matrix.os }})')
        self.assertIs(self.validation['strategy']['fail-fast'], False)
        self.assertIs(self.windows()['strategy']['fail-fast'], False)
        self.assertEqual(self.windows()['strategy']['matrix'], {
            'os': ['windows-latest'], 'role': ['win_contracts', 'win_suite'],
        })
        self.assertEqual(self.windows()['runs-on'], '${{ matrix.os }}')
        self.assertEqual(' '.join(self.windows()['if'].split()), '${{ ' + NATIVE + ' }}')
        self.assertEqual(' '.join(self.windows()['name'].split()), (
            '${{ ' + NATIVE + " && (matrix.role == 'win_contracts' && 'board (windows-latest)' "
            "|| 'Windows validation work') || 'Windows validation inactive' }}"
        ))
        self.assertIs(self.validation['steps'], self.windows()['steps'])
        self.assertIs(self.validation['env'], self.windows()['env'])

    def test_commands_suites_coverage_and_postinit_have_separate_roles(self):
        pages = "github.event_name == 'push' && github.ref == 'refs/heads/main' && " + NATIVE_REPO
        preview = "github.event_name == 'pull_request' && " + NATIVE_REPO
        cases = {
            "Run each contract's test_command": COMMAND,
            'Report init command duration': COMMAND + ' && always() && ' + NATIVE_REPO,
            'Run unit tests (1/2)': SUITE,
            'Run unit tests (2/2)': SUITE,
            'Prepare Python suite coverage': SUITE + ' && ' + NATIVE_REPO,
            'Report Python suite coverage': SUITE + ' && ' + NATIVE_REPO,
            'Upload Python suite coverage': SUITE + ' && ' + NATIVE_REPO,
            'Install pinned Pages publisher for PR': SUITE + ' && ' + preview,
            'Build and validate Pages for PR': SUITE + ' && ' + preview,
            'Export Pages CI inventory': SUITE + ' && ' + pages,
            'Upload Pages CI inventory': SUITE + ' && ' + pages,
            'Approve project quality (when configured)': SUITE,
            'Verify required contract acceptance': SUITE,
            'Upload acceptance matrix': "always() && " + SUITE + " && steps.acceptance.outcome != 'skipped'",
            'Summarize acceptance state': 'always() && ' + SUITE,
            'Verify Windows post-init partitions': SUITE + " && matrix.os == 'windows-latest' && " + NATIVE,
        }
        for name, guard in cases.items():
            with self.subTest(name=name):
                step = self.step(self.validation, name)
                condition = ' '.join(step.get('if', '').split())
                self.assertEqual(condition, '${{ ' + guard + ' }}')
                self.assertNotIn('continue-on-error', step)

    def test_expensive_steps_retain_the_actual_commands_and_workers(self):
        command = self.step(self.validation, "Run each contract's test_command")
        self.assertEqual(command['run'], CONTRACT_COMMAND)
        for number in (1, 2):
            suite = self.step(self.validation, f'Run unit tests ({number}/2)')
            self.assertEqual(suite['run'], SUITE_COMMAND)
            self.assertEqual(suite['env']['KDD_SKIP_INIT_POST_APPLY_SUITE'], '1')
            self.assertEqual('COVERAGE_PROCESS_START' in suite['env'], number == 1)
        for name, invocation in [('Prepare Python suite coverage', 'prepare'),
                                 ('Report Python suite coverage', 'report')]:
            with self.subTest(name=name):
                body = self.step(self.validation, name)['run']
                self.assertRegex(body, r'(?m)^python scripts/ci_coverage\.py ' + invocation + r' --repo-root \. --output ')
        env = self.validation['env']
        self.assertIn("matrix.os == 'windows-latest' && '6' || '4'", env['KDD_SUITE_WORKERS'])
        self.assertIn("github.repository == 'MauricioPerera/KDD' && '4'", env['KDD_CONTRACT_WORKERS'])
        self.assertIn('python -m unittest tests/test_init_project.py', env['KDD_EXCLUSIVE_CONTRACT_COMMANDS'])
        upload = self.step(self.validation, 'Upload acceptance matrix')
        self.assertEqual(upload['with']['name'], 'acceptance-${{ matrix.os }}')

    def test_existing_windows_board_checks_execute_in_the_contract_role(self):
        for name, command in [('Run Windows Board typecheck', 'npm run typecheck'),
                              ('Run Windows Board tests', 'npm test')]:
            with self.subTest(name=name):
                step = self.step(self.validation, name)
                self.assertEqual(step.get('if'), "${{ matrix.role == 'win_contracts' }}")
                self.assertEqual(step['run'], command)
                self.assertEqual(step['working-directory'], 'tools/kdd-board')
                self.assertNotIn('continue-on-error', step)
        self.assertNotIn('continue-on-error', self.validation)
        self.assertNotIn('continue-on-error', self.windows())

    def test_receipt_outputs_are_bound_to_one_upload_and_one_producer_role(self):
        receipt = self.step(self.validation, 'Upload Windows validation receipt')
        self.assertEqual(receipt['id'], 'windows-receipt')
        self.assertEqual(receipt['if'], "${{ matrix.role == 'win_contracts' || matrix.role == 'win_suite' }}")
        self.assertEqual(receipt['with']['path'], '${{ runner.temp }}/kdd-windows-receipts/receipt.json')
        self.assertEqual(receipt['uses'].split()[0],
                         'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9')
        self.assertEqual(receipt['with']['name'],
                         'kdd-validation-receipt-${{ matrix.role }}-${{ github.run_id }}-${{ github.run_attempt }}')
        self.assertEqual(receipt['with']['if-no-files-found'], 'error')
        self.assertIs(receipt['with']['overwrite'], False)
        self.assertNotIn('continue-on-error', receipt)
        self.assertNotIn('outputs', self.validation)
        outputs = self.windows()['outputs']
        for role, label in [('win_contracts', 'contract'), ('win_suite', 'suite')]:
            for suffix in ('id', 'digest'):
                with self.subTest(role=role, suffix=suffix):
                    expected = ("${{ matrix.role == '" + role + "' && steps.windows-receipt.outputs.artifact-"
                                + suffix + " || '' }}")
                    self.assertEqual(' '.join(outputs[f'win_{label}_{suffix}'].split()), expected)

    def test_independent_discovery_and_first_pass_coverage_are_bound_to_suite_outputs(self):
        inventory = self.step(self.validation, 'Compute independent Windows suite inventory')
        self.assertEqual(inventory['id'], 'windows-suite-inventory')
        self.assertEqual(inventory['if'], "${{ matrix.role == 'win_suite' }}")
        self.assertNotIn('continue-on-error', inventory)
        self.assertIn('site/ci_inventory.py', inventory['run'])
        self.assertIn('discover', inventory['run'])
        self.assertIn('sha256', inventory['run'])
        self.assertLess(self.validation['steps'].index(inventory),
                        self.validation['steps'].index(self.step(self.validation, 'Run unit tests (1/2)')))
        coverage = self.step(self.validation, 'Upload Python suite coverage')
        self.assertEqual(coverage['id'], 'suite-coverage')
        for label, output in [('suite_inventory_sha256', 'windows-suite-inventory.outputs.sha256'),
                              ('coverage_id', 'suite-coverage.outputs.artifact-id'),
                              ('coverage_digest', 'suite-coverage.outputs.artifact-digest')]:
            self.assertEqual(' '.join(self.windows()['outputs']['win_' + label].split()),
                             "${{ matrix.role == 'win_suite' && steps." + output + " || '' }}")

    def test_required_check_joins_after_producers_and_keeps_attempt_diagnostics(self):
        join = self.join()
        self.assertEqual(join['needs'], ['validate_windows'])
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
        for step in (guard, download, verify):
            self.assertNotIn('if', step)
            self.assertNotIn('continue-on-error', step)
        self.assertLess(join['steps'].index(guard), join['steps'].index(download))
        self.assertLess(join['steps'].index(download), join['steps'].index(verify))
        self.assertEqual(download['uses'].split()[0],
                         'actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333')
        self.assertEqual(download['with']['artifact-ids'], (
            '${{ needs.validate_windows.outputs.win_contract_id }},${{ needs.validate_windows.outputs.win_suite_id }},'
            '${{ needs.validate_windows.outputs.win_coverage_id }}'
        ))
        self.assertIs(download['with']['skip-decompress'], True)
        self.assertIs(download['with'].get('merge-multiple'), True)
        self.assertEqual(download['with']['digest-mismatch'], 'error')
        self.assertRegex(verify['env']['KDD_WINDOWS_JOIN_DRIVER_SHA256'], r'^[0-9a-f]{64}$')
        self.assertEqual(verify['shell'], 'python -I {0}')
        self.assertEqual(download['with']['path'], '${{ runner.temp }}/kdd-windows-validation-artifacts')
        self.assertEqual(join['env']['KDD_TRUSTED_RUNTIME_REF'],
                         self.validation['env']['KDD_TRUSTED_RUNTIME_REF'])
        checkout = [step for step in join['steps'] if step.get('uses', '').startswith('actions/checkout@')]
        self.assertEqual(len(checkout), 1)
        self.assertEqual(checkout[0]['uses'], self.validation['steps'][0]['uses'])
        self.assertIs(checkout[0]['with']['persist-credentials'], False)
        self.assertEqual(checkout[0]['with']['ref'], '${{ github.sha }}')
        for forbidden in ('if', 'continue-on-error'):
            self.assertNotIn(forbidden, checkout[0])
        self.assertLess(join['steps'].index(guard), join['steps'].index(checkout[0]))
        self.assertLess(join['steps'].index(checkout[0]), join['steps'].index(verify))
        partial = self.step(self.validation, 'Upload CI timing diagnostics')
        self.assertEqual(' '.join(partial['with']['name'].split()), PARTIAL_TIMINGS)
        joined = self.step(join, 'Upload joined Windows timing diagnostics')
        self.assertEqual(joined['with']['name'],
                         'kdd-timings-${{ github.run_id }}-${{ github.run_attempt }}-windows-latest')
        self.assertIs(joined['with']['overwrite'], False)

    def test_real_join_wrapper_binds_committed_driver_digest_and_external_execution(self):
        join = self.join()
        wrapper = self.step(join, 'Verify Windows validation receipts')
        self.assertEqual(wrapper['shell'], 'python -I {0}')
        with tempfile.TemporaryDirectory(prefix='kdd windows driver ') as directory:
            outer = Path(directory).resolve()
            repo, temp = outer / 'checkout', outer / 'runner temp'
            driver = repo / 'scripts/ci_windows_join.py'
            driver.parent.mkdir(parents=True)
            temp.mkdir()
            marker = outer / 'verified.json'
            source = """\
import json, os, sys
from pathlib import Path
assert sys.flags.isolated
options = dict(zip(sys.argv[2::2], sys.argv[3::2]))
for name in ('--contracts', '--suites', '--coverage'):
    assert Path(options[name]).is_file(), name
identity = json.loads(Path(options['--identity']).read_text(encoding='utf-8'))
producers = json.loads(Path(options['--producers']).read_text(encoding='utf-8'))
Path(os.environ['KDD_TEST_MARKER']).write_text(json.dumps({
    'driver': __file__, 'args': sys.argv[1:], 'identity': identity, 'producers': producers,
}), encoding='utf-8')
"""
            driver.write_bytes(source.encode('ascii'))

            def git(*args):
                return subprocess.run(
                    ['git', '-c', 'core.autocrlf=false', '-c', 'commit.gpgsign=false',
                     '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args],
                    cwd=repo, check=True, capture_output=True, text=True, timeout=20,
                ).stdout.strip()

            git('init', '-q')
            git('add', '.')
            git('commit', '-q', '-m', 'reviewed driver')
            sha = git('rev-parse', 'HEAD')
            # A working copy cannot substitute for the reviewed Git object.
            driver.write_bytes(b'raise SystemExit("checkout canary executed")\n')
            receipt_dir = temp / 'kdd-windows-validation-artifacts'
            receipt_dir.mkdir()
            for name in ('kdd-validation-receipt-win_contracts-17-2',
                         'kdd-validation-receipt-win_suite-17-2', 'kdd-coverage-17-2-windows-latest'):
                (receipt_dir / (name + '.zip')).write_bytes(b'archive consumed by the probe driver')
            env = dict(
                os.environ, RUNNER_TEMP=str(temp), GITHUB_SHA=sha, GITHUB_REPOSITORY='MauricioPerera/KDD',
                GITHUB_WORKFLOW_REF='MauricioPerera/KDD/.github/workflows/validate.yml@refs/heads/main',
                GITHUB_RUN_ID='17', GITHUB_RUN_ATTEMPT='2', KDD_TRUSTED_RUNTIME_REF=sha,
                KDD_TRUSTED_BUNDLE=str(temp / 'runtime bundle'),
                VALIDATION_STATE='success', CONTRACTS_ID='11', SUITES_ID='12', COVERAGE_ID='13',
                CONTRACTS_DIGEST='a' * 64, SUITES_DIGEST='b' * 64, COVERAGE_DIGEST='c' * 64,
                KDD_SUITE_INVENTORY_SHA256='d' * 64, KDD_TEST_MARKER=str(marker),
            )
            driver_sha256 = hashlib.sha256(source.encode('ascii')).hexdigest()
            for valid, pin in [(False, '0' * 64), (True, driver_sha256)]:
                with self.subTest(valid=valid):
                    result = subprocess.run(
                        [sys.executable, '-I', '-c', wrapper['run']], cwd=repo,
                        env=dict(env, KDD_WINDOWS_JOIN_DRIVER_SHA256=pin),
                        capture_output=True, text=True, timeout=20,
                    )
                    self.assertEqual(result.returncode == 0, valid, result.stdout + result.stderr)
                    self.assertIs(marker.is_file(), valid)
            recorded = json.loads(marker.read_text(encoding='utf-8'))
            launched = Path(recorded['driver']).resolve()
            self.assertTrue(launched.is_relative_to(temp))
            self.assertFalse(launched.is_relative_to(repo))
            self.assertEqual(recorded['args'][0], 'verify')
            self.assertEqual(recorded['identity'], {
                'repository': 'MauricioPerera/KDD', 'workflow': '.github/workflows/validate.yml',
                'run_id': 17, 'run_attempt': 2, 'head_sha': sha, 'tree': git('rev-parse', 'HEAD^{tree}'),
                'runtime_ref': sha, 'platform': 'windows-latest',
            })
            self.assertEqual(recorded['producers'], {
                'contracts': {'id': 11, 'result': 'success', 'digest': 'a' * 64},
                'suites': {'id': 12, 'result': 'success', 'digest': 'b' * 64},
                'coverage': {'id': 13, 'result': 'success', 'digest': 'c' * 64},
            })
            for flag in ('--repo-root', '--runtime-bundle', '--identity', '--producers', '--suite-inventory-sha256',
                         '--coverage', '--contracts', '--suites'):
                self.assertIn(flag, recorded['args'])

    def test_real_bash_guard_fails_when_a_producer_did_not_supply_valid_outputs(self):
        step = self.step(self.join(), 'Check Windows validation producers')
        self.assertEqual(step['shell'], 'bash')
        env = self.join()['env']
        expected = {
            'VALIDATION_STATE': '${{ needs.validate_windows.result }}',
            'CONTRACTS_ID': '${{ needs.validate_windows.outputs.win_contract_id }}',
            'CONTRACTS_DIGEST': '${{ needs.validate_windows.outputs.win_contract_digest }}',
            'SUITES_ID': '${{ needs.validate_windows.outputs.win_suite_id }}',
            'SUITES_DIGEST': '${{ needs.validate_windows.outputs.win_suite_digest }}',
            'COVERAGE_ID': '${{ needs.validate_windows.outputs.win_coverage_id }}',
            'COVERAGE_DIGEST': '${{ needs.validate_windows.outputs.win_coverage_digest }}',
            'KDD_SUITE_INVENTORY_SHA256': '${{ needs.validate_windows.outputs.win_suite_inventory_sha256 }}',
        }
        self.assertEqual({key: env[key] for key in expected}, expected)
        bash = shutil.which('bash')
        if os.name == 'nt':
            git = Path(shutil.which('git') or 'git.exe').resolve()
            paths = (parent / 'bin/bash.exe' for parent in git.parents)
            bash = next((str(path) for path in paths if path.is_file()), bash)
        self.assertTrue(bash, 'The workflow requires Bash')
        good = dict(VALIDATION_STATE='success', CONTRACTS_ID='11', CONTRACTS_DIGEST='a' * 64,
                    SUITES_ID='12', SUITES_DIGEST='b' * 64, COVERAGE_ID='13',
                    COVERAGE_DIGEST='c' * 64, KDD_SUITE_INVENTORY_SHA256='d' * 64)
        bad = [
            {'VALIDATION_STATE': 'failure'}, {'VALIDATION_STATE': 'skipped'},
            {'VALIDATION_STATE': 'cancelled'}, {'CONTRACTS_ID': ''}, {'SUITES_ID': ''},
            {'CONTRACTS_DIGEST': ''}, {'SUITES_DIGEST': ''}, {'SUITES_ID': '11'},
            {'COVERAGE_ID': '12'}, {'COVERAGE_DIGEST': ''}, {'KDD_SUITE_INVENTORY_SHA256': ''},
            {'CONTRACTS_ID': '-1'}, {'SUITES_DIGEST': 'z' * 64},
        ]
        for changes in [{}, *bad]:
            with self.subTest(changes=changes):
                result = subprocess.run([bash, '--noprofile', '--norc', '-e', '-o', 'pipefail',
                                         '-c', step['run']], cwd=ROOT, env=dict(os.environ, **(good | changes)),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, not changes, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
