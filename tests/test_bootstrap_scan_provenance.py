"""Real initializer copies and optional evidence classification; no fabricated scans."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ('compliance', 'privacy', 'accessibility', 'dependency-eol',
          'observability', 'test-coverage')
spec = importlib.util.spec_from_file_location('pending_optional_evidence', ROOT / 'scripts/optional_evidence.py')
optional = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optional)


class EvidenceProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kdd-scan-provenance-')
        self.addCleanup(self.tmp.cleanup)
        self.area = Path(self.tmp.name)

    def evaluate(self, value, required=False):
        source = self.area / 'findings.json'
        source.write_text(json.dumps(value), encoding='utf-8')
        env = {'KDD_PRIVACY_SCAN_DIR': str(self.area), 'KDD_PRIVACY_OUTCOME': 'success'}
        return optional.evaluate_layers(['privacy'], {'privacy'} if required else set(),
                                        env, summary=True)[0]

    def test_optional_example_never_counts_as_pass(self):
        row = self.evaluate({'scanId': 'example_privacy', 'findings': []})
        self.assertEqual(row['status'], 'SKIP')
        self.assertIn('example', row['reason'].lower())

    def test_required_example_fails_even_with_successful_validator(self):
        self.assertEqual(self.evaluate({'scanId': 'example_privacy'}, True)['status'], 'FAIL')

    def test_own_report_preserves_existing_outcome_semantics(self):
        self.assertEqual(self.evaluate({'scanId': 'project-own-scan'})['status'], 'PASS')

    def test_invalid_json_cannot_be_accredited(self):
        (self.area / 'findings.json').write_text('{broken', encoding='utf-8')
        env = {'KDD_PRIVACY_SCAN_DIR': str(self.area), 'KDD_PRIVACY_OUTCOME': 'success'}
        row = optional.evaluate_layers(['privacy'], set(), env, summary=True)[0]
        self.assertEqual(row['status'], 'FAIL')


@unittest.skipUnless((ROOT / 'src/hello.py').is_file(),
                     'template-only initialization: already initialized project')
class BootstrapScanProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='kdd-scan-template-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.area = Path(cls.tmp.name)
        cls.template = cls.area / 'template'
        cls.template.mkdir()
        names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached',
                                         '--others', '--exclude-standard', '-z'],
                                        text=True, encoding='utf-8').split('\0')
        for name in filter(None, names):
            source, target = ROOT / name, cls.template / name
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.area)
        self.addCleanup(self.case.cleanup)
        self.root = Path(self.case.name) / 'project'
        shutil.copytree(self.template, self.root)

    def run_init(self, apply=False, entry='init'):
        if entry == 'bootstrap':
            argv = [sys.executable, str(ROOT / 'scripts/bootstrap_project.py'),
                    '--repo-dir', str(self.root), '--profile', 'minimal']
        else:
            argv = [sys.executable, str(ROOT / 'scripts/init_project.py'), '--repo-dir', str(self.root)]
        argv += ['--name', 'Own project', '--repository', 'Fixture/OwnProject']
        if apply:
            argv.append('--apply')
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                                env=dict(os.environ, PYTHONUTF8='1'), timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_dry_run_lists_examples_and_changes_nothing(self):
        before = self.snapshot()
        result = self.run_init()
        self.assertEqual(self.snapshot(), before)
        for layer in LAYERS:
            self.assertIn(layer + '/scan/findings.json', result.stdout)

    def test_apply_removes_known_examples_but_keeps_rules_and_validators(self):
        self.run_init(True)
        for layer in LAYERS:
            self.assertFalse((self.root / layer / 'scan/findings.json').exists(), layer)
            self.assertTrue((self.root / ('scripts/validate_' + layer.replace('-', '_') + '_findings.py')).is_file())
            self.assertTrue((self.root / ('examples/rules/' + layer + '-findings.rules.json')).is_file())

    def test_own_reports_at_the_same_paths_are_not_deleted(self):
        data = {'scanId': 'own-project-review', 'findings': []}
        for layer in LAYERS:
            (self.root / layer / 'scan/findings.json').write_text(json.dumps(data), encoding='utf-8')
        self.run_init(True)
        for layer in LAYERS:
            self.assertEqual(json.loads((self.root / layer / 'scan/findings.json').read_text()), data)

    def test_changed_sample_payload_is_not_deleted_by_prefix(self):
        path = self.root / 'privacy/scan/findings.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['findings'] = []
        path.write_text(json.dumps(data), encoding='utf-8')
        self.run_init(True)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)

    def test_bootstrap_entry_has_the_same_cleanup(self):
        self.run_init(True, 'bootstrap')
        self.assertTrue(all(not (self.root / p / 'scan/findings.json').exists() for p in LAYERS))

    def test_precondition_failure_keeps_examples_and_all_other_files(self):
        (self.root / 'README.md').unlink()
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/init_project.py'),
                                 '--repo-dir', str(self.root), '--apply', '--repository', 'Fixture/OwnProject'],
                                capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
