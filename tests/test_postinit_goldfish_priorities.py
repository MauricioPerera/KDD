"""Verify that the shipped Windows data reaches the real post-init launcher."""
import json
import os
import shutil
import unittest

from tests import test_ci_module_order as fixture


SLOW_TAIL = ('test_adoption_adversarial_oracles', 'test_git_task_multi_oracle',
             'test_adoption_oracle_pass_identity', 'test_adoption_bound_method_identity',
             'test_adoption_adversarial_review', 'test_adoption_trusted_pr')
PROMOTED = (*SLOW_TAIL, 'test_adoption_python_preparation', 'test_adopt_project',
            'test_goldfish_traceability', 'test_adoption_quality_reference',
            'test_task_oracle_execution_proof', 'test_plugin_odd_egm_review',
            'test_goldfish_compliance', 'test_quality_required_oracle_evidence',
            'test_trusted_pr_event_binding', 'test_adoption_adversarial_transport',
            'test_changed_python_budgets')
ORIGINAL = fixture.ROOT / 'tests/fixtures/pr194-original-module-order.json'
LEGACY_PRIORITY = 'test_task_committed_artifacts'


class PostInitGoldfishPriorities(unittest.TestCase):
    def test_shipped_profile_prioritizes_measured_late_modules(self):
        profile = json.loads((fixture.ROOT / fixture.PROFILE).read_text(encoding='utf-8'))
        original = json.loads(ORIGINAL.read_text(encoding='utf-8'))
        self.assertEqual(len(profile), len(set(profile)))
        self.assertEqual(len(original), 199)
        self.assertEqual([name for name in profile if name in original], original)
        self.assertEqual(set(SLOW_TAIL) & set(profile[:17]), set(SLOW_TAIL))
        self.assertEqual(tuple(name for name in profile[:60] if name in PROMOTED), PROMOTED)

    def test_real_launcher_preserves_every_case_and_uses_only_windows_order(self):
        lab = fixture.ModuleOrder()
        self.addCleanup(lab.doCleanups)
        lab.setUp()
        names = ('test_000_schedule_control', SLOW_TAIL[0], SLOW_TAIL[1], LEGACY_PRIORITY)
        root = lab.project('initialized copy without Git', names)
        lab.launcher_files(root)
        path = root / fixture.PROFILE
        path.parent.mkdir(parents=True)
        shutil.copyfile(fixture.ROOT / fixture.PROFILE, path)
        self.assertFalse((root / '.git').exists())
        first = lab.complete(*lab.invoke(root, launcher=True), names=names)
        second = lab.complete(*lab.invoke(root, launcher=True), names=names)
        self.assertEqual(first['executed_ids'], second['executed_ids'])
        for name in names:
            self.assertEqual((root / (name + '.ran')).read_text(encoding='utf-8'), 'ran\nran\n')
        if os.name == 'nt':
            self.assertEqual(first['workers'], 10)
            actual = first['scheduling']['modules']
            self.assertEqual(set(actual[:2]), set(SLOW_TAIL[:2]))
            self.assertEqual(actual[2:], [LEGACY_PRIORITY, names[0]])
        else:
            self.assertEqual(first['workers'], 4)
            self.assertNotIn('scheduling', first)
            self.assertEqual([module['module'] for module in first['modules']], sorted(names))


if __name__ == '__main__':
    unittest.main()
