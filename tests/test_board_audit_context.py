"""Run the independent HTTP, Git and UI recovery regressions for Board."""
import hashlib
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'tools' / 'kdd-board'
ORACLE = BOARD / 'tests' / 'audit-board-context.test.ts'
ORACLE_SHA256 = '6c89277229c05cf3c56b1946f7111c24a1069717b6fab0c5dd7200239e5f542a'


class BoardAuditContext(unittest.TestCase):
    def test_real_board_regressions(self):
        if not (BOARD / 'node_modules' / 'zod' / 'package.json').is_file():
            if not (ROOT / 'src' / 'hello.py').is_file():
                self.skipTest('initialized Python-only copy; Board dependencies are absent')
            self.fail('Board runtime dependencies must be installed in the template')
        self.assertTrue((BOARD / 'src' / 'server.ts').is_file())
        self.assertTrue((BOARD / 'public' / 'app.js').is_file())
        self.assertEqual(hashlib.sha256(ORACLE.read_text(encoding='utf-8').encode('utf-8')).hexdigest(), ORACLE_SHA256)
        result = subprocess.run(['node', '--test', '--test-reporter=tap', 'tests/audit-board-context.test.ts'],
                                cwd=BOARD, env={**os.environ, 'PYTHONUTF8': '1'},
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('# pass 9', result.stdout)
        self.assertIn('# fail 0', result.stdout)
