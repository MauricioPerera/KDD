"""Pages uses the same pinned discovery environment as the verified CI."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / '.github/workflows/deploy-pages.yml'
CI = ROOT / '.github/workflows/validate.yml'
COMMAND = 'python -m pip install --require-hashes --only-binary=:all: -r tools/context-v03/requirements.txt'


def named_step(text, name):
    marker = '      - name: ' + name + '\n'
    if marker not in text:
        return ''
    return text.split(marker, 1)[1].split('\n      - ', 1)[0]


class PagesContextDiscovery(unittest.TestCase):
    def test_deployment_installs_pinned_context_lock_before_public_build(self):
        text = PAGES.read_text(encoding='utf-8')
        install = named_step(text, 'Install pinned context compatibility dependencies')
        self.assertIn(COMMAND, install)
        self.assertNotIn('continue-on-error', install)
        self.assertNotIn('\n        if:', install)
        self.assertLess(text.index('- name: Install pinned context compatibility dependencies'),
                        text.index('- name: Build and validate public bundle'))

    def test_ci_installs_the_same_lock_before_pr_preview(self):
        text = CI.read_text(encoding='utf-8')
        install = named_step(text, 'Install pinned context compatibility dependencies')
        self.assertIn(COMMAND, install)
        self.assertLess(text.index('- name: Install pinned context compatibility dependencies'),
                        text.index('- name: Build and validate Pages for PR'))

    def test_real_discovery_fails_closed_when_site_packages_are_absent(self):
        result = subprocess.run([sys.executable, '-I', '-S', str(ROOT / 'site/ci_inventory.py'),
                                 'discover', '--repo-root', str(ROOT)], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PAGES_DISCOVERY', result.stderr)
        self.assertIn('test_context_v03', result.stderr)
        self.assertIn("No module named 'yaml'", result.stderr)
        self.assertEqual(result.stdout.strip(), '')

    def test_real_discovery_includes_context_oracle_with_dependencies(self):
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'site/ci_inventory.py'),
                                 'discover', '--repo-root', str(ROOT)], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        ids = json.loads(result.stdout)
        self.assertTrue(any(item.startswith('test_context_v03.') for item in ids))
        self.assertTrue(any(item.startswith('test_pages_context_discovery.') for item in ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(any('_FailedTest' in item for item in ids))


if __name__ == '__main__':
    unittest.main()