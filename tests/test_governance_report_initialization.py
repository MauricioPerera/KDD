"""Exact optional KDD closure report cleanup; all work occurs in owned copies."""
from pathlib import Path
import unittest

from tests import test_governance_initialization as fixtures
from scripts import init_project

REPORT='docs/reports/CONTRACT-34-REPORT.md'

@unittest.skipUnless(fixtures.TEMPLATE_PRESENT,'template artifacts absent after initialization')
class GovernanceReportInitialization(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.GovernanceInitializationTests()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.root=self.f.root

    def initialize(self,apply):
        return init_project.init_project(str(self.root),apply,None,'ExampleCo/Shop')

    def report(self):
        path=self.root/REPORT
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'Synthetic future KDD closure report\n')
        return path

    def test_optional_present_report_is_planned_once_without_writes(self):
        self.report();before=self.f.snapshot()
        result=self.initialize(False)
        self.assertEqual(result['removed'].count(REPORT),1)
        self.assertFalse(result['applied'])
        self.assertEqual(self.f.snapshot(),before)

    def test_present_report_is_removed_with_its_kdd_spec(self):
        path=self.report()
        result=self.initialize(True)
        self.assertTrue(result['applied'])
        self.assertFalse(path.exists(),'a report without its spec is an orphan')
        self.assertFalse((self.root/fixtures.GOVERNANCE).exists())
        self.assertEqual(result['removed'].count(REPORT),1)

    def test_absent_future_report_is_optional_and_does_not_block_initialization(self):
        self.assertFalse((self.root/REPORT).exists())
        result=self.initialize(True)
        self.assertTrue(result['applied'])
        self.assertNotIn(REPORT,result['removed'])

    def test_another_project_report_is_never_discovered_as_cleanup_permission(self):
        self.report()
        foreign=self.root/'docs/reports/CONTRACT-35-REPORT.md'
        foreign.write_bytes(b'Own project evidence\n')
        self.initialize(True)
        self.assertEqual(foreign.read_bytes(),b'Own project evidence\n')
        self.assertFalse((self.root/REPORT).exists())

    def test_missing_required_manifest_entry_preserves_optional_report_and_all_files(self):
        self.report()
        (self.root/fixtures.initializer.MANIFEST[0]).unlink()
        before=self.f.snapshot()
        with self.assertRaisesRegex(ValueError,'manifiesto incompleto'):
            self.initialize(True)
        self.assertEqual(self.f.snapshot(),before)

    def test_non_regular_known_report_blocks_before_any_deletion(self):
        path=self.root/REPORT;path.parent.mkdir(parents=True,exist_ok=True);path.mkdir()
        before=self.f.snapshot()
        with self.assertRaises(ValueError):
            self.initialize(True)
        self.assertEqual(self.f.snapshot(),before)
        self.assertTrue(path.is_dir())

if __name__=='__main__':unittest.main()
