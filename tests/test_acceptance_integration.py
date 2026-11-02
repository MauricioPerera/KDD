"""Acceptance is explicit and cannot be silently downgraded to legacy gates."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_profile


class AcceptanceProfile(unittest.TestCase):
    def test_requires_policy_and_approved_sha(self):
        for kwargs in ({}, {'approved_ref': 'a' * 40},
                       {'acceptance_policy': 'acceptance.json'},
                       {'approved_ref': 'HEAD', 'acceptance_policy': 'acceptance.json'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_profile.build_profile('acceptance', **kwargs)

    def test_profile_invokes_matrix_and_preserves_exit(self):
        profile = run_profile.build_profile('acceptance', approved_ref='a' * 40,
                                            acceptance_policy='acceptance.json')
        self.assertEqual(profile[0][0], 'acceptance')
        self.assertIn('scripts/verify_acceptance.py', profile[0][1])
        self.assertIn('acceptance.json', profile[0][1])
        result = run_profile.run_profile('acceptance', '.', approved_ref='a' * 40,
                                         acceptance_policy='acceptance.json', runner=lambda *_: 1)
        self.assertFalse(result['ok'])
        self.assertEqual(result['failed_at'], 'acceptance')

    def test_policy_option_cannot_be_ignored_by_legacy_profile(self):
        with self.assertRaises(ValueError):
            run_profile.build_profile('minimal', acceptance_policy='acceptance.json')


if __name__ == '__main__':
    unittest.main()
