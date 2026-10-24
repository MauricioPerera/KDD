"""Reviewed official action commits; no network requests inside the oracle."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'actions/checkout': '3d3c42e5aac5ba805825da76410c181273ba90b1',  # v7.0.1
    'actions/setup-python': '6d4fd22b20465ccc0f7354476588e8df7c9ca0e0',  # v7.1.0
    'actions/setup-node': '949feb2413d6458794dcd2491c4babbbce0c15c1',  # v7.1.0
    'actions/configure-pages': '45bfe0192ca1faeb007ade9deae92b16b8254a0d',  # v6.0.0
    'actions/upload-pages-artifact': 'fc324d3547104276b827a68afc52ff2a11cc49c9',  # v5.0.0
    'actions/deploy-pages': '368f82528645a54fb793d4d04e342629a3f51346',  # v5.0.1
}


class ActionRuntime(unittest.TestCase):
    def test_every_official_setup_reference_is_a_reviewed_full_sha(self):
        files = list((ROOT / '.github/workflows').glob('*.yml'))
        files += list((ROOT / '.github/actions').rglob('action.yml'))
        found = set()
        for path in files:
            for repo, ref in re.findall(r'uses:\s*(actions/(?:checkout|setup-python|setup-node|configure-pages|upload-pages-artifact|deploy-pages))@([^\s#]+)',
                                        path.read_text(encoding='utf-8')):
                found.add(repo)
                self.assertEqual(ref, PINS[repo], str(path.relative_to(ROOT)))
        self.assertEqual(found, set(PINS))
        pages = (ROOT / '.github/workflows/deploy-pages.yml').read_text(encoding='utf-8')
        self.assertIn("node-version: '24'", pages)
        self.assertNotIn("node-version: '20'", pages)

    def test_dual_os_two_passes_baseline_and_permissions_are_preserved(self):
        text = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'), 2)
        command = 'run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'
        self.assertEqual(text.count(command), 2)
        for n in (1, 2):
            block = text.split('- name: Run unit tests (%s/2)' % n)[1].split('\n      - ')[0]
            self.assertIn(command, block)
            self.assertIn("KDD_SKIP_INIT_POST_APPLY_SUITE: '1'", block)
        for required in ('contents: read', 'actions: read', 'persist-credentials: false',
                         'fetch-depth: 0', 'Check approved contract and oracle baseline',
                         'Validate Git task snapshots and transitions',
                         '--timeout 600 --deduplicate', 'Run each contract'):
            self.assertIn(required, text)
        self.assertNotIn('continue-on-error:', text)
        self.assertNotIn('ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION', text)
        trusted = (ROOT / '.github/workflows/trusted-pr-gate.yml').read_text(encoding='utf-8')
        self.assertIn('pull_request_target:', trusted)
        self.assertIn('guard_pr_baseline.py', trusted)
        self.assertIn('persist-credentials: false', trusted)


if __name__ == '__main__':
    unittest.main()
