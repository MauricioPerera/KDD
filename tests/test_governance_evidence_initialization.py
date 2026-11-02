"""Optional companion evidence34 cleanup in owned copies, without broad permissions."""
import unittest

from scripts import init_project
from tests import test_governance_initialization as fixtures

EVIDENCE='docs/reports/CONTRACT-34-EVIDENCE.json'
REPORT='docs/reports/CONTRACT-34-REPORT.md'

@unittest.skipUnless(fixtures.TEMPLATE_PRESENT,'template artifacts absent after initialization')
class GovernanceEvidenceInitialization(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.GovernanceInitializationTests()
        self.addCleanup(self.f.doCleanups);self.f.setUp();self.root=self.f.root

    def initialize(self,apply):
        return init_project.init_project(str(self.root),apply,None,'ExampleCo/Shop')

    def evidence(self):
        path=self.root/EVIDENCE;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'{"schema_version":1,"synthetic_future_evidence":true}\n')
        return path

    def test_present_companion_evidence_is_planned_once_without_writes(self):
        self.evidence();before=self.f.snapshot();result=self.initialize(False)
        self.assertEqual(result['removed'].count(EVIDENCE),1)
        self.assertEqual(self.f.snapshot(),before)
        self.assertFalse(result['applied'])

    def test_apply_removes_exact_evidence_with_report_and_spec(self):
        path=self.evidence();(self.root/REPORT).write_bytes(b'Synthetic future report\n')
        result=self.initialize(True)
        self.assertFalse(path.exists(),'new projects must not inherit upstream closure identity')
        self.assertFalse((self.root/REPORT).exists())
        self.assertFalse((self.root/fixtures.GOVERNANCE).exists())
        self.assertEqual(result['removed'].count(EVIDENCE),1)

    def test_absent_companion_evidence_does_not_become_a_required_manifest_entry(self):
        self.assertFalse((self.root/EVIDENCE).exists())
        result=self.initialize(True)
        self.assertTrue(result['applied']);self.assertNotIn(EVIDENCE,result['removed'])

    def test_foreign_project_evidence_is_never_a_discovered_cleanup_permission(self):
        self.evidence();foreign=self.root/'docs/reports/CONTRACT-35-EVIDENCE.json'
        foreign.write_bytes(b'{"own_project":true}\n')
        self.initialize(True)
        self.assertEqual(foreign.read_bytes(),b'{"own_project":true}\n')
        self.assertFalse((self.root/EVIDENCE).exists())

    def test_non_regular_companion_path_blocks_before_deletion(self):
        path=self.root/EVIDENCE;path.parent.mkdir(parents=True,exist_ok=True);path.mkdir()
        before=self.f.snapshot()
        with self.assertRaises(ValueError):self.initialize(True)
        self.assertEqual(self.f.snapshot(),before);self.assertTrue(path.is_dir())

    def test_missing_previous_manifest_entry_keeps_companion_evidence_unchanged(self):
        self.evidence();(self.root/fixtures.initializer.MANIFEST[0]).unlink()
        before=self.f.snapshot()
        with self.assertRaisesRegex(ValueError,'manifiesto incompleto'):self.initialize(True)
        self.assertEqual(self.f.snapshot(),before)

if __name__=='__main__':unittest.main()
