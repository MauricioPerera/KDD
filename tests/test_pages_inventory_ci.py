"""Workflow provenance boundaries; behavioral integration lives next door."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UPLOAD='cf430e030ddbb5b0abf93d22962f4752f3646cd9'
DOWNLOAD='9000827ccba6bdab643e8b6fd33ac0654aef8333'
CONDITION="${{ github.event_name == 'push' && github.ref == 'refs/heads/main' && !inputs.reusable_execution && github.repository == 'MauricioPerera/KDD' }}"


def step(text,name):
    marker='      - name: '+name+'\n'
    if marker not in text: raise AssertionError('Missing required inventory step: '+name)
    return text.split(marker,1)[1].split('\n      - ',1)[0]


class PagesInventoryWorkflow(unittest.TestCase):
    def setUp(self):
        self.ci=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.pages=(ROOT/'.github/workflows/deploy-pages.yml').read_text(encoding='utf-8')

    def test_export_is_native_main_only_after_both_unchanged_suites(self):
        export=step(self.ci,'Export Pages CI inventory')
        upload=step(self.ci,'Upload Pages CI inventory')
        for block in (export,upload):
            self.assertIn('        if: '+CONDITION,block)
        self.assertGreater(self.ci.index('- name: Export Pages CI inventory'),self.ci.index('- name: Run unit tests (2/2)'))
        for required in ('python site/ci_inventory.py export','--reports-dir "$RUNNER_TEMP/kdd-suite-reports"',
                         '--output "$RUNNER_TEMP/kdd-pages-ci-inventory/inventory.json"',
                         '--run-id "$GITHUB_RUN_ID"','--run-attempt "$GITHUB_RUN_ATTEMPT"',
                         '--head-sha "$GITHUB_SHA"','--platform "${{ matrix.os }}"',
                         '--trusted-runtime-ref "$KDD_TRUSTED_RUNTIME_REF"'):
            self.assertIn(required,export)

    def test_upload_is_pinned_and_contains_only_the_small_manifest(self):
        upload=step(self.ci,'Upload Pages CI inventory')
        self.assertIn('uses: actions/upload-artifact@'+UPLOAD,upload)
        for required in ('name: kdd-ci-inventory-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.os }}',
                         'path: ${{ runner.temp }}/kdd-pages-ci-inventory/inventory.json',
                         'if-no-files-found: error','overwrite: false','retention-days: 7'):
            self.assertIn(required,upload)
        for forbidden in ('kdd-pages-pr','include-hidden-files: true','continue-on-error','if: always()'):
            self.assertNotIn(forbidden,upload)

    def test_downloads_bind_both_platforms_to_exact_trigger_run_and_attempt(self):
        for platform,title in [('ubuntu-latest','Ubuntu'),('windows-latest','Windows')]:
            block=step(self.pages,'Download '+title+' CI inventory')
            for required in ('uses: actions/download-artifact@'+DOWNLOAD,
                             'name: kdd-ci-inventory-${{ github.event.workflow_run.id }}-${{ github.event.workflow_run.run_attempt }}-'+platform,
                             'run-id: ${{ github.event.workflow_run.id }}','repository: ${{ github.repository }}',
                             'github-token: ${{ github.token }}','digest-mismatch: error',
                             'path: ${{ runner.temp }}/kdd-ci-inventory/'+platform):
                self.assertIn(required,block)
            for forbidden in ('pattern:', 'merge-multiple:', 'run-id: latest','continue-on-error'):
                self.assertNotIn(forbidden,block)
            self.assertLess(self.pages.index('- name: Download '+title),self.pages.index('- name: Build and validate public bundle'))

    def test_full_discovery_dependencies_are_installed_before_build(self):
        install=step(self.pages,'Install pinned discovery parsers')
        self.assertIn('python -m pip install --only-binary=:all: -r requirements-change-audit.txt',install)
        self.assertLess(self.pages.index('- name: Install pinned discovery parsers'),self.pages.index('- name: Build and validate public bundle'))
        build=step(self.pages,'Build and validate public bundle')
        for required in ('--ci-inventory-dir "$RUNNER_TEMP/kdd-ci-inventory"',
                         '--ci-run-attempt "$CI_RUN_ATTEMPT"','--ci-trusted-runtime-ref "$KDD_TRUSTED_RUNTIME_REF"',
                         'CI_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt }}',
                         'KDD_TRUSTED_RUNTIME_REF: ${{ vars.KDD_TRUSTED_RUNTIME_REF }}',
                         'CI_RUN_URL: ${{ github.event.workflow_run.html_url }}'):
            self.assertIn(required,build)

    def test_deployment_gate_and_least_permissions_are_preserved(self):
        step(self.pages,'Download Ubuntu CI inventory')
        permissions=self.pages.split('\n    permissions:\n',1)[1].split('\n    environment:',1)[0]
        self.assertEqual(set(line.strip() for line in permissions.splitlines() if line.strip()),
                         {'contents: read','actions: read','pages: write','id-token: write'})
        for required in ("github.event.workflow_run.conclusion == 'success'",
                         "github.event.workflow_run.event == 'push'",
                         "github.event.workflow_run.head_branch == 'main'",
                         'ref: ${{ github.event.workflow_run.head_sha }}','persist-credentials: false'):
            self.assertIn(required,self.pages)
        self.assertNotIn('pull_request_target:',self.pages)
        self.assertNotIn('continue-on-error:',self.pages)
        self.assertNotIn('\n    permissions:',self.ci.split('\n  validate:\n',1)[1].split('\n  board:\n',1)[0])

    def test_dual_os_two_passes_and_current_pr_preview_are_preserved(self):
        step(self.ci,'Export Pages CI inventory')
        self.assertEqual(self.ci.count('os: [ubuntu-latest, windows-latest]'),2)
        command='run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'
        self.assertEqual(self.ci.count(command),2)
        jobs=self.ci.split('\njobs:\n',1)[1]
        self.assertEqual(set(line.strip() for line in jobs.splitlines() if line.startswith('  ') and not line.startswith('   ') and line.endswith(':')),{'validate:','board:'})
        preview=step(self.ci,'Build and validate Pages for PR')
        self.assertIn("github.event_name == 'pull_request'",preview)
        self.assertNotIn('--ci-inventory-dir',preview)
        self.assertNotIn('pages: write',self.ci)


if __name__=='__main__':
    unittest.main()
