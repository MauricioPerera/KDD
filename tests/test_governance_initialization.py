"""Real temporary-copy oracle for the exact KDD governance spec inventory."""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import init_project as initializer


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = 'specs/CONTRACT-34-kdd-governance-closure.md'
TEMPLATE_PRESENT = ((ROOT / GOVERNANCE).is_file()
                    and all((ROOT / name).is_file() for name in initializer.MANIFEST))


@unittest.skipUnless(TEMPLATE_PRESENT, 'template artifacts absent after initialization')
class GovernanceInitializationTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-governance-init-')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name) / 'project'
        names = set(initializer.MANIFEST) | set(initializer.REQUIRED_AFTER_DELETE) | {GOVERNANCE}
        for name in names:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def initialize(self, apply):
        return initializer.init_project(str(self.root), apply, None, 'ExampleCo/Shop')

    def test_dry_run_lists_exact_governance_spec_without_writes(self):
        before = self.snapshot()
        result = self.initialize(False)
        self.assertIn(GOVERNANCE, result['removed'])
        self.assertEqual(result['removed'].count(GOVERNANCE), 1)
        self.assertFalse(result['applied'])
        self.assertEqual(self.snapshot(), before)

    def test_apply_removes_governance_spec_and_keeps_foreign_spec_and_report(self):
        own = {'specs/CONTRACT-35-own-project.md': b'own project definition\n',
               'docs/reports/CONTRACT-35-REPORT.md': b'own project evidence\n'}
        for name, content in own.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        result = self.initialize(True)
        self.assertTrue(result['applied'])
        self.assertFalse((self.root / GOVERNANCE).exists())
        for name, content in own.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_missing_governance_spec_aborts_before_deleting_anything(self):
        (self.root / GOVERNANCE).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'manifiesto incompleto'):
            self.initialize(True)
        self.assertEqual(self.snapshot(), before)

    def test_foreign_spec_is_never_discovered_as_a_cleanup_permission(self):
        path = self.root / 'specs/CONTRACT-999-own.md'
        path.write_bytes(b'preserve this own spec\n')
        plan = self.initialize(False)
        self.assertNotIn('specs/CONTRACT-999-own.md', plan['removed'])
        self.initialize(True)
        self.assertEqual(path.read_bytes(), b'preserve this own spec\n')

    def test_missing_previous_manifest_entry_still_aborts_without_writes(self):
        (self.root / initializer.MANIFEST[0]).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'manifiesto incompleto'):
            self.initialize(True)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
