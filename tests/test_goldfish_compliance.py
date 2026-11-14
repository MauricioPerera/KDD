"""Drive the real compliance gate and its CI evidence steps on a Git fixture."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from tests.test_fixture_preparation import configure_git


ROOT = Path(__file__).resolve().parents[1]
INPUT = 'requirements.txt'
METADATA = 'installed/widget-1.0.dist-info/METADATA'
FINDINGS = 'compliance/scan/findings.json'
MANIFEST = 'compliance/scan/scan-manifest.json'

SCAN_PROGRAM = """
import importlib.metadata
import json
from pathlib import Path

expected = Path('requirements.txt').read_text(encoding='utf-8').strip()
observed = {}
for dependency in importlib.metadata.distributions(path=['installed']):
    identity = dependency.metadata['Name'] + '==' + dependency.version
    observed[identity] = dependency.metadata['License']
assert set(observed) == {expected} and observed[expected] == 'MIT', observed
print(json.dumps(dict(documentType='kdd-compliance.findings', schemaVersion='1.0',
                      scanId='project-scan', projectLicense='MIT', findings=[])))
"""


class ComplianceEvidence(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-license-')
        self.addCleanup(area.cleanup)
        self.repo = Path(area.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        configure_git(self.repo, {'user.name': 'License fixture',
                                  'user.email': 'license@example.invalid',
                                  'core.autocrlf': 'false'}, ephemeral=True)
        (self.repo / INPUT).write_bytes(b'widget==1.0\n')
        metadata = self.repo / METADATA
        metadata.parent.mkdir(parents=True)
        metadata.write_bytes(b'Metadata-Version: 2.1\nName: widget\nVersion: 1.0\nLicense: MIT\n')
        self.scanned = self.commit('Lock the dependency inputs')
        self.findings = dict(documentType='kdd-compliance.findings', schemaVersion='1.0',
                             scanId='project-scan', projectLicense='MIT', findings=[])

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], timeout=30)

    def write_json(self, path, data):
        dest = self.repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(json.dumps(data).encode('utf-8') + b'\n')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD').decode().strip()

    def record(self):
        scan = subprocess.check_output([sys.executable, '-I', '-c', SCAN_PROGRAM],
                                       cwd=self.repo, encoding='utf-8', timeout=30)
        self.assertEqual(json.loads(scan), self.findings)
        self.write_json(FINDINGS, self.findings)
        digest = lambda path: hashlib.sha256((self.repo / path).read_bytes()).hexdigest()
        return dict(schema_version=1, source_ref=self.scanned,
                    tool=dict(name='Python importlib.metadata probe', version=sys.version.split()[0]),
                    inputs={name: digest(name) for name in (INPUT, METADATA)},
                    findings_sha256=digest(FINDINGS))

    def review(self):
        self.write_json(MANIFEST, self.record())
        return self.commit('Review the preserved scan and its dependency inputs')

    def run_script(self, script, *args, **settings):
        env = dict(os.environ, PYTHONUTF8='1')
        for key in ('KDD_COMPLIANCE_APPROVED_REF', 'KDD_APPROVED_BASELINE_REF',
                    'GITHUB_SHA', 'GITHUB_STEP_SUMMARY'):
            env.pop(key, None)
        env.update(settings)
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *args],
                              cwd=self.repo, env=env, capture_output=True,
                              encoding='utf-8', timeout=30)

    def layers(self, phase, approved='', required=True, **settings):
        validated = self.run_script('validate_compliance_findings.py', 'compliance/scan')
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        return self.run_script('optional_evidence.py', phase, '--layers', 'compliance',
                               KDD_COMPLIANCE_SCAN_DIR='compliance/scan',
                               KDD_REQUIRED_EVIDENCE='compliance' if required else '',
                               KDD_COMPLIANCE_OUTCOME='success',
                               KDD_COMPLIANCE_APPROVED_REF=approved, **settings)

    def rejected(self, approved='', **settings):
        for phase in ('check', 'summary'):
            with self.subTest(phase=phase):
                result = self.layers(phase, approved, **settings)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('FAIL [compliance]', result.stdout)

    def test_required_empty_findings_without_reviewed_manifest_fail(self):
        self.write_json(FINDINGS, self.findings)
        self.rejected(self.commit('Record only the unproven findings'))

    def test_optional_legacy_findings_are_reported_as_skip(self):
        self.write_json(FINDINGS, self.findings)
        self.commit('Record optional findings without an attestation')
        result = self.layers('summary', required=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SKIP [compliance]', result.stdout)

    def test_reviewed_empty_findings_pass_for_unchanged_inputs(self):
        approved = self.review()
        (self.repo / 'README.md').write_text('An unrelated change.', encoding='utf-8')
        head = self.commit('Change only project documentation')
        for phase, status in (('check', 'PRESENT'), ('summary', 'PASS')):
            with self.subTest(phase=phase):
                result = self.layers(phase, GITHUB_SHA=head, KDD_APPROVED_BASELINE_REF=approved)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(status + ' [compliance]', result.stdout)

    def test_candidate_cannot_attest_its_own_report_against_older_approval(self):
        self.review()
        self.rejected(self.scanned)

    def test_commit_cannot_be_its_own_approval_without_external_reference(self):
        self.review()
        self.rejected()

    def test_findings_blob_must_match_the_approved_blob(self):
        approved = self.review()
        self.findings['scanId'] = 'renamed-with-same-valid-shape'
        self.write_json(FINDINGS, self.findings)
        self.commit('Substitute the reviewed report')
        self.rejected(approved)

    def test_candidate_and_checkout_must_preserve_the_reviewed_manifest(self):
        approved = self.review()
        data = json.loads((self.repo / MANIFEST).read_text(encoding='utf-8'))
        data['tool']['version'] = 'unreviewed-version'
        self.write_json(MANIFEST, data)
        self.rejected(approved)
        self.commit('Change only the reviewed attestation')
        self.rejected(approved)

    def test_report_hash_must_match_even_in_reviewed_manifest(self):
        data = self.record()
        data['findings_sha256'] = '0' * 64
        self.write_json(MANIFEST, data)
        self.rejected(self.commit('Review a manifest with the wrong report hash'))

    def test_missing_findings_array_cannot_claim_an_empty_scan(self):
        data = self.record()
        incomplete = {key: value for key, value in self.findings.items() if key != 'findings'}
        self.write_json(FINDINGS, incomplete)
        data['findings_sha256'] = hashlib.sha256((self.repo / FINDINGS).read_bytes()).hexdigest()
        self.write_json(MANIFEST, data)
        self.rejected(self.commit('Review a report without the required findings array'))

    def test_scan_sha_must_contain_the_reviewed_input_bytes(self):
        data = self.record()
        (self.repo / INPUT).write_bytes(b'widget==2.0\n')
        data['inputs'][INPUT] = hashlib.sha256(b'widget==2.0\n').hexdigest()
        self.write_json(MANIFEST, data)
        self.rejected(self.commit('Review current bytes that were absent at scan time'))

    def test_unrelated_approval_with_identical_tree_does_not_certify_candidate(self):
        approved = self.review()
        tree = self.git('rev-parse', approved + '^{tree}').decode().strip()
        sibling = self.git('commit-tree', tree, '-p', self.scanned, '-m', 'Sibling review').decode().strip()
        self.rejected(sibling)

    def test_scan_on_sibling_branch_does_not_certify_review(self):
        data = self.record()
        tree = self.git('rev-parse', self.scanned + '^{tree}').decode().strip()
        sibling = self.git('commit-tree', tree, '-m', 'Unrelated scan').decode().strip()
        data['source_ref'] = sibling
        self.write_json(MANIFEST, data)
        self.rejected(self.commit('Review a manifest from an unrelated scan'))

    def test_changed_or_dirty_dependency_input_invalidates_provenance(self):
        approved = self.review()
        (self.repo / INPUT).write_bytes(b'other==1.0\n')
        self.rejected(approved)
        self.commit('Change dependency graph')
        self.rejected(approved)

    def test_wrong_checkout_sha_cannot_claim_current_ci(self):
        approved = self.review()
        self.rejected(approved, GITHUB_SHA=self.scanned)

    def test_manifest_with_duplicate_keys_is_rejected_even_if_reviewed(self):
        data = self.record()
        (self.repo / MANIFEST).write_bytes(
            (json.dumps(data)[:-1] + ', "inputs": ' + json.dumps(data['inputs']) + '}').encode('utf-8'))
        self.rejected(self.commit('Commit a manifest with ambiguous inputs'))

    def test_same_bytes_with_nonregular_git_mode_are_rejected(self):
        approved = self.review()
        oid = self.git('rev-parse', 'HEAD:' + INPUT).decode().strip()
        self.git('update-index', '--cacheinfo', '120000,' + oid + ',' + INPUT)
        self.git('commit', '-qm', 'Record identical bytes with a link mode')
        self.assertTrue((self.repo / INPUT).is_file())
        self.assertFalse((self.repo / INPUT).is_symlink())
        self.rejected(approved)

    def test_only_reviewed_text_inputs_admit_checkout_crlf(self):
        data = self.record()
        data['text_inputs'] = [INPUT]
        self.write_json(MANIFEST, data)
        approved = self.commit('Review which checkout inputs are text')
        (self.repo / INPUT).write_bytes(b'widget==1.0\r\n')
        for phase, status in (('check', 'PRESENT'), ('summary', 'PASS')):
            with self.subTest(phase=phase):
                result = self.layers(phase, approved)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(status + ' [compliance]', result.stdout)
        metadata = self.repo / METADATA
        metadata.write_bytes(metadata.read_bytes().replace(b'\n', b'\r\n'))
        self.rejected(approved)

    def test_composite_routes_its_external_approval_to_both_phases(self):
        action = (ROOT / '.github/actions/validate-contracts/action.yml').read_text(encoding='utf-8')
        self.assertIn('  compliance-approved-ref:', action)
        wiring = 'KDD_COMPLIANCE_APPROVED_REF: ${{ inputs.compliance-approved-ref }}'
        approved = self.review()
        for phase in ('check', 'summary'):
            with self.subTest(phase=phase):
                marker = f'/optional_evidence.py" {phase} '
                step_prefix = action[:action.index(marker)].rsplit('    - name:', 1)[1]
                env_block = step_prefix.split('      env:\n', 1)[1].split('      run:', 1)[0]
                self.assertIn('        ' + wiring, env_block.splitlines())
                if phase == 'summary':
                    self.assertIn('        KDD_COMPLIANCE_OUTCOME: ${{ steps.compliance_scan.outcome }}',
                                  env_block.splitlines())
                line = next(line for line in action.splitlines() if marker in line)
                command = shlex.split(line.removeprefix('      run: '))
                self.assertEqual(command[:2], ['python', '$KDD_TOOLING_ROOT/scripts/optional_evidence.py'])
                result = self.run_script('optional_evidence.py', *command[2:],
                                         KDD_COMPLIANCE_APPROVED_REF=approved,
                                         KDD_COMPLIANCE_SCAN_DIR='compliance/scan',
                                         KDD_REQUIRED_EVIDENCE='compliance',
                                         KDD_COMPLIANCE_OUTCOME='success')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
