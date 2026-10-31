"""Real-Git oracle for scope reconstructed independently of closure claims."""
from tests.test_task_finish_perimeter import PerimeterCase


class HistoricalPerimeterTests(PerimeterCase):
    def assert_history_rejected(self, path):
        self.marker.unlink(missing_ok=True)
        before = self.p.snapshot()
        for ranged in (False, True):
            result = self.audit(ranged)
            self.assertNotEqual(result.returncode, 0, 'historical validator accepted an out-of-scope closure')
            self.assertIn('TASK_PERIMETER', result.stdout + result.stderr)
            self.assertIn(path, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists(), 'historical audit executed candidate tests')
        self.assertEqual(self.p.snapshot(), before)

    def test_valid_historical_scope_is_recomputed_without_rewriting_legacy(self):
        self.integrate()
        self.legacy_close()
        self.marker.unlink(missing_ok=True)
        before = self.p.snapshot()
        self.assertEqual(self.audit().returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.p.snapshot(), before)

    def test_missing_receipt_never_skips_historical_scope(self):
        self.p.write('outside.txt', 'outside implementation\n')
        self.integrate()
        self.legacy_close()
        self.assert_history_rejected('outside.txt')

    def test_forged_clean_receipt_cannot_hide_an_outside_file(self):
        self.p.write('outside.txt', 'outside implementation\n')
        self.integrate()
        receipt = {'schema_version': 1, 'approved_ref': self.p.ref,
                   'branch_base': self.branch_base, 'branch_tip': self.tip,
                   'tested_commit': self.p.git('rev-parse', 'HEAD'), 'paths': []}
        self.legacy_close(receipt)
        self.assert_history_rejected('outside.txt')

    def test_reverted_scope_violation_is_reconstructed_from_commits(self):
        self.p.write('outside.txt', 'outside intermediate commit\n')
        self.p.commit('Synthetic outside intermediate change')
        (self.p.root / 'outside.txt').unlink()
        self.integrate()
        self.legacy_close()
        self.assert_history_rejected('outside.txt')

    def test_reverted_oracle_edit_is_still_a_scope_violation(self):
        original = (self.p.root / 'tests/test_feature1.py').read_bytes()
        self.p.write('tests/test_feature1.py', 'assert True\n')
        self.p.commit('Synthetic intermediate oracle replacement')
        (self.p.root / 'tests/test_feature1.py').write_bytes(original)
        self.integrate()
        self.legacy_close()
        self.assert_history_rejected('tests/test_feature1.py')

    def test_merge_only_outside_change_is_reconstructed(self):
        self.tip = self.p.commit('Synthetic allowed implementation')
        self.p.git('switch', '-q', 'main')
        self.p.git('merge', '--no-ff', '--no-commit', 'task/TASK-001')
        self.p.write('merge-only.txt', 'outside contribution at integration\n')
        self.p.commit('Synthetic merge-only scope violation')
        self.legacy_close()
        self.assert_history_rejected('merge-only.txt')

    def test_older_reported_tip_does_not_hide_the_integrated_extra_change(self):
        allowed_tip = self.p.commit('Synthetic first allowed implementation')
        self.p.write('outside.txt', 'later branch scope violation\n')
        self.integrate()
        self.legacy_close(reported_tip=allowed_tip)
        self.assert_history_rejected('outside.txt')

    def test_wrong_present_receipt_is_rejected_even_for_allowed_changes(self):
        self.integrate()
        self.legacy_close({'schema_version': 1, 'approved_ref': self.p.ref,
                           'branch_base': self.branch_base, 'branch_tip': self.tip,
                           'tested_commit': self.p.git('rev-parse', 'HEAD'),
                           'paths': ['auxiliary.txt']})
        self.assert_history_rejected('auxiliary.txt')

    def test_later_main_work_does_not_change_the_scope_of_a_valid_old_closure(self):
        self.integrate()
        self.legacy_close()
        self.p.write('later-task.txt', 'independent subsequent work\n')
        self.p.commit('Synthetic subsequent main work')
        self.assertEqual(self.audit().returncode, 0)

    def test_historical_audit_uses_git_objects_despite_dirty_checkout_permissions(self):
        self.integrate()
        self.legacy_close()
        self.marker.unlink(missing_ok=True)
        path = self.p.root / self.p.contract(1)
        path.write_text(path.read_text(encoding='utf-8').replace(
            "touch_only: ['src/feature1.py']", "touch_only: ['*']"), encoding='utf-8')
        before = self.p.snapshot()
        self.assertEqual(self.audit().returncode, 0)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.p.snapshot(), before)

    def test_historical_scope_does_not_require_a_live_task_branch(self):
        self.integrate()
        self.legacy_close()
        self.p.git('branch', '-D', 'task/TASK-001')
        self.assertEqual(self.audit().returncode, 0)


if __name__ == '__main__':
    import unittest
    unittest.main()
