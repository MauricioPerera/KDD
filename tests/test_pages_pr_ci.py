"""Native PR build policy and real fresh-process package integration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = 'Install pinned Pages publisher for PR'
BUILD = 'Build and validate Pages for PR'
CONDITION = "${{ github.event_name == 'pull_request' && !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD' }}"
COMMAND = 'python site/build.py --output "$RUNNER_TEMP/kdd-pages-pr-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT-$RUNNER_OS" --ci-run-url "$CI_RUN_URL"'


def step(text, name):
    marker = '      - name: ' + name + '\n'
    if marker not in text:
        raise AssertionError('Missing required PR Pages step: ' + name)
    return text.split(marker, 1)[1].split('\n      - ', 1)[0]


class PagesPrWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')

    def test_steps_are_required_for_native_pr_in_both_existing_validate_jobs(self):
        validate = self.text.split('\n  validate:\n', 1)[1].split('\n  board:\n', 1)[0]
        self.assertIn('os: [ubuntu-latest, windows-latest]', validate)
        for name in (INSTALL, BUILD):
            body = step(validate, name)
            self.assertIn('        if: ' + CONDITION, body)
            self.assertIn('        shell: bash', body)
            self.assertNotIn('hashFiles', body)
            self.assertLess(validate.index('- name: ' + name), validate.index("- name: Run each contract's test_command"))
            self.assertGreater(validate.index('- name: ' + name), validate.index('node-version:'))
        self.assertLess(validate.index('- name: ' + INSTALL), validate.index('- name: ' + BUILD))

    def test_publisher_install_uses_the_exact_lockfile_without_scripts(self):
        body = step(self.text, INSTALL)
        self.assertIn('        run: npm ci --prefix site --ignore-scripts --no-audit --no-fund', body)
        self.assertNotIn('npm install', body)
        package = json.loads((ROOT / 'site/package.json').read_text(encoding='utf-8'))
        self.assertEqual(package['dependencies']['@rckflr/llms-skills'], '0.4.1')
        self.assertTrue((ROOT / 'site/package-lock.json').is_file())

    def test_build_runs_real_cli_with_fresh_external_output_and_current_run_url(self):
        body = step(self.text, BUILD)
        self.assertIn('        run: ' + COMMAND, body)
        self.assertIn('CI_RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}', body)
        for forbidden in ('||', 'continue-on-error', 'exit 0', 'echo python', 'rm -', 'Remove-Item'):
            self.assertNotIn(forbidden, body)

    def test_pr_build_has_read_only_permissions_and_no_publication_actions(self):
        permissions = self.text.split('permissions:\n', 1)[1].split('\non:', 1)[0]
        self.assertIn('contents: read', permissions)
        self.assertIn('actions: read', permissions)
        self.assertNotIn('write', permissions)
        validate = self.text.split('\n  validate:\n', 1)[1].split('\n  board:\n', 1)[0]
        self.assertNotIn('\n    permissions:', validate)
        self.assertNotIn('\n    environment:', validate)
        self.assertNotIn('pull_request_target:', self.text)
        for name in (INSTALL, BUILD):
            body = step(validate, name)
            for forbidden in ('secrets.', 'pages: write', 'id-token: write', 'upload-pages', 'deploy-pages', 'configure-pages', 'environment:'):
                self.assertNotIn(forbidden, body)

    def test_deployment_stays_separate_and_rebuilds_successful_main_sha(self):
        step(self.text, BUILD)
        deploy = (ROOT / '.github/workflows/deploy-pages.yml').read_text(encoding='utf-8')
        for required in ('workflow_run:', 'workflows: [validate-contracts]',
                         "github.event.workflow_run.conclusion == 'success'",
                         "github.event.workflow_run.event == 'push'",
                         "github.event.workflow_run.head_branch == 'main'",
                         'ref: ${{ github.event.workflow_run.head_sha }}',
                         'run: python site/build.py'):
            self.assertIn(required, deploy)
        self.assertNotIn('pull_request_target:', deploy)
        # Main may read raw CI inventories, while rebuilding its own bundle.
        # A candidate HTML artifact from a PR is still never deployed.
        for title, platform in (('Ubuntu', 'ubuntu-latest'), ('Windows', 'windows-latest')):
            download = step(deploy, 'Download ' + title + ' CI inventory')
            self.assertIn('name: kdd-ci-inventory-${{ github.event.workflow_run.id }}-${{ github.event.workflow_run.run_attempt }}-' + platform, download)
            self.assertIn('run-id: ${{ github.event.workflow_run.id }}', download)
            self.assertNotIn('kdd-pages-pr', download)
            self.assertNotIn('merge-multiple:', download)


PROBE = '''import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
assert sys.flags.isolated
assert str(root / "scripts") not in sys.path
sys.path.insert(0,str(root if sys.argv[2]=="package" else root/"scripts"))
if sys.argv[2]=="package":
    from scripts import mcp_gate_dispatch as gate
else:
    import mcp_gate_dispatch as gate
result=gate.run_gate("lint_ascii", {"dir":"src"}, str(root))
print(json.dumps({"package":gate.__package__, "gates":len(gate.LEVEL1_GATES),
                  "profile_module":gate.resolve_profile.__module__,
                  "process_module":gate.run_process.__module__, "result":result}))
'''


class PackageImportIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='kdd Pages paquete \u00f1 ')
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name)
        self.repo = self.area / 'project with spaces'
        (self.repo / 'scripts').mkdir(parents=True)
        (self.repo / 'src').mkdir()
        for name in ('mcp_gate_dispatch.py', 'execution_profile.py', 'process_tree.py', 'lint_ascii.py'):
            shutil.copyfile(ROOT / 'scripts' / name, self.repo / 'scripts' / name)
        (self.repo / 'src/feature.py').write_text("print('healthy')\n", encoding='utf-8')
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        self.env.pop('PYTHONPATH', None)

    def probe(self, mode='package', cwd=None):
        result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', PROBE,
                                 str(self.repo), mode], cwd=cwd or self.repo,
                                env=self.env, capture_output=True, text=True,
                                encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['gates'], 19)
        return data

    def test_fresh_package_import_executes_real_gate_and_transitive_helpers(self):
        data = self.probe()
        self.assertEqual(data['package'], 'scripts')
        self.assertEqual(data['profile_module'], 'scripts.execution_profile')
        self.assertEqual(data['process_module'], 'scripts.process_tree')
        self.assertEqual(data['result']['exit_code'], 0, data)
        self.assertIn('0 error(es) en 1 archivo(s)', data['result']['stdout'])

    def test_legacy_script_import_keeps_real_cli_gate_compatible(self):
        data = self.probe('script')
        self.assertEqual(data['package'], '')
        self.assertEqual(data['profile_module'], 'execution_profile')
        self.assertEqual(data['process_module'], 'process_tree')
        self.assertEqual(data['result']['exit_code'], 0, data)
        self.assertIn('0 error(es) en 1 archivo(s)', data['result']['stdout'])

    def test_package_import_preserves_actual_gate_failure(self):
        (self.repo / 'src/feature.py').write_text("print('contrase\u00f1a')\n", encoding='utf-8')
        data = self.probe()
        self.assertEqual(data['result']['exit_code'], 1, data)
        self.assertIn('1 error(es) en 1 archivo(s)', data['result']['stdout'])

    def test_package_import_does_not_depend_on_the_working_directory(self):
        other = self.area / 'unrelated cwd'
        other.mkdir()
        data = self.probe(cwd=other)
        self.assertEqual(data['profile_module'], 'scripts.execution_profile')
        self.assertEqual(data['result']['exit_code'], 0, data)
        self.assertIn('0 error(es) en 1 archivo(s)', data['result']['stdout'])


if __name__ == '__main__':
    unittest.main()
