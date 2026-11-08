"""Run sealed HTTP/fresh-process Board restart scenarios from Python contracts."""
import hashlib
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'tools/kdd-board'
NODE_ORACLE_SHA256 = '32dd7a6a60791d18991d081a5158d9595e01c11c1a88d99f6128d17028485f78'
PROJECT_FIXTURE_SHA256 = 'e454cd0e28768a7b36267dedb9f0e4d906760fca8bbb3e203c16cf7c4714a2ee'


class BoardSecretRestartTests(unittest.TestCase):
    def setUp(self):
        if not (BOARD / 'node_modules/zod/package.json').is_file():
            if not (ROOT / 'src/hello.py').is_file():
                self.skipTest('initialized Python-only copy; Board dependencies are absent')
            self.fail('Board dependencies must be installed in the template')
        self.assertTrue((BOARD / 'src/server.ts').is_file())
        for name, expected in [('secret-restart.test.ts', NODE_ORACLE_SHA256),
                               ('project-fixture.ts', PROJECT_FIXTURE_SHA256)]:
            raw = (BOARD / 'tests' / name).read_text(encoding='utf-8').encode('utf-8')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected, name)

    def scenario(self, name):
        result = subprocess.run(['node', '--test', '--test-reporter=tap',
            '--test-name-pattern', '^secret restart ' + name + '$', 'tests/secret-restart.test.ts'],
            cwd=BOARD, env=dict(os.environ, PYTHONUTF8='1'), capture_output=True,
            encoding='utf-8', timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('KDD_BOARD_RESTART_PHASE ', output)
        self.assertIn('# pass 1', output)
        self.assertIn('# fail 0', output)

    def test_fulfilled_secret_survives_a_fresh_process(self):
        self.scenario('preserves a fulfilled requirement and blind metadata')

    def test_removed_credential_reopens_human_requirement(self):
        self.scenario('invalidates a credential removed between processes')

    def test_identified_legacy_vault_survives_restart_and_migration(self):
        self.scenario('preserves identified legacy dotenv and isolated migration')


if __name__ == '__main__':
    unittest.main()
