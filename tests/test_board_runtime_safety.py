"""Execute real Board integration oracles from KDD's Python contract runner."""
import os
import hashlib
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'tools' / 'kdd-board'
NODE_ORACLE_SHA256 = '9d1ad08f355a572306110b1147b20a1279ad35bbbecb11f2c328865b4f2e362a'


class BoardRuntimeSafety(unittest.TestCase):
    def setUp(self):
        if not (BOARD / 'node_modules' / 'zod' / 'package.json').is_file():
            if not (ROOT / 'src' / 'hello.py').is_file():
                self.skipTest('initialized Python-only copy; Board dependencies are absent')
            self.fail('Board runtime dependencies must be installed in the template')

    def run_case(self, pattern):
        for target in ('src/server.ts', 'public/git-board.js', 'public/app.js'):
            self.assertTrue((BOARD / target).is_file(), target)
        source = (BOARD / 'tests' / 'board-runtime-safety.test.ts').read_text(encoding='utf-8')
        self.assertEqual(hashlib.sha256(source.encode('utf-8')).hexdigest(), NODE_ORACLE_SHA256)
        result = subprocess.run(['node', '--test', '--test-reporter=tap', '--test-name-pattern', pattern,
                                 'tests/board-runtime-safety.test.ts'], cwd=BOARD,
                                env={**os.environ, 'PYTHONUTF8': '1'},
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('# fail 0', result.stdout)

    def test_vault_isolation_and_legacy(self):
        self.run_case('^vault ')

    def test_git_catalog_refresh(self):
        self.run_case('^live catalog ')

    def test_polling_error_and_recovery(self):
        self.run_case('^task polling ')
