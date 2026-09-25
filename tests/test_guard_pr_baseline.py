"""Regression tests for the base-branch PR guard."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import guard_pr_baseline as guard  # noqa: E402


class TestTrustedPrBaseline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous = Path.cwd()
        os.chdir(self.root)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.write('knowledge/contracts/task.md',
                   "---\ntype: 'Task Contract'\ntests: 'tests/task.py'\n---\n")
        self.write('tests/task.py', 'assert True\n')
        self.base = self.commit()

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', *args], stderr=subprocess.PIPE)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD').decode().strip()

    def test_identical_candidate_passes(self):
        self.assertEqual(guard.check(self.base, self.base, self.base), [])

    def test_unapproved_oracle_change_fails(self):
        self.write('tests/task.py', 'assert False\n')
        candidate = self.commit()
        self.assertTrue(any('oracle differs' in item
                            for item in guard.check(self.base, candidate, self.base)))

    def test_unapproved_contract_change_fails(self):
        self.write('knowledge/contracts/task.md',
                   "---\ntype: 'Task Contract'\ntests: 'tests/task.py'\n"
                   "intent: changed\n---\n")
        candidate = self.commit()
        self.assertTrue(any('contract differs' in item
                            for item in guard.check(self.base, candidate, self.base)))

    def test_self_modification_fails_even_with_approved_candidate(self):
        self.write('.github/workflows/trusted-pr-gate.yml', 'on: []\n')
        candidate = self.commit()
        self.assertTrue(any('trusted gate file changed' in item
                            for item in guard.check(self.base, candidate, candidate)))

    def test_validator_modification_fails(self):
        self.write('scripts/validate_baseline.py', 'raise SystemExit(0)\n')
        candidate = self.commit()
        self.assertTrue(any('trusted gate file changed' in item
                            for item in guard.check(self.base, candidate, self.base)))


if __name__ == '__main__':
    unittest.main()
