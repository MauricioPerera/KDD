"""Real Git integration and process accounting for approved baseline reads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import os, runpy, sys
from pathlib import Path
script, repo, ref, log = sys.argv[1:]
def audit(event, args):
    if event != 'subprocess.Popen': return
    executable = args[0]
    if executable is None:
        command = args[1]
        if isinstance(command, (list, tuple)):
            executable = command[0] if command else ''
        else:
            command = str(command).lstrip()
            executable = command[1:].split('"', 1)[0] if command.startswith('"') else command.split(' ', 1)[0]
    if os.path.basename(os.fspath(executable)).lower() in ('git', 'git.exe'):
        with open(log, 'a', encoding='utf-8') as out: out.write('git\n')
sys.addaudithook(audit)
sys.path.insert(0, str(Path(script).parent))
sys.argv = [script, '--all', '--repo-root', repo, '--approved-ref', ref]
runpy.run_path(script, run_name='__main__')
'''


class BaselineGitBatchTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd baseline batch ')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name) / 'project'
        self.root.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Baseline Test')
        self.git('config', 'user.email', 'baseline@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'gc.auto', '0')
        self.git('config', 'maintenance.auto', 'false')
        (self.root/'knowledge/contracts').mkdir(parents=True)
        (self.root/'tests').mkdir()
        for i in range(12):
            oracle = ('tests/shared.py' if i % 3 == 0 else
                      'tests/oracle 01.py' if i == 1 else 'tests/oracle-%02d.py' % i)
            (self.root/'knowledge/contracts'/('contract-%02d.md' % i)).write_text(
                "---\ntests: '%s'\n---\n" % oracle, encoding='utf-8')
            path = self.root/oracle
            if not path.exists():
                path.write_bytes(b'\x00binary oracle\r\nline\n' if i == 5 else
                                 b'# uniquely approved\n' if i == 1 else b'# approved\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'independent approved baseline')
        self.ref = self.git('rev-parse', 'HEAD')
        self.counter = Path(self.area.name)/'git-count.txt'

    def git(self, *args):
        p = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True,
            text=True, encoding='utf-8', timeout=30)
        if p.returncode:
            self.fail('git failed: ' + repr(args) + '\n' + p.stderr)
        return p.stdout.strip()

    def cli(self, ref=None):
        self.counter.unlink(missing_ok=True)
        result = subprocess.run([sys.executable, '-I', '-c', PROBE,
            str(ROOT/'scripts/validate_baseline.py'), str(self.root), ref or self.ref,
            str(self.counter)], capture_output=True, text=True, encoding='utf-8',
            env=dict(os.environ, PYTHONUTF8='1'), timeout=120)
        count = len(self.counter.read_text(encoding='utf-8').splitlines()) if self.counter.exists() else 0
        return result, count

    def test_all_uses_bounded_git_processes_and_is_read_only(self):
        before = (self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain=v1'),
                  self.git('show-ref'), (self.root/'.git/index').read_bytes())
        result, count = self.cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS:', result.stdout)
        self.assertLessEqual(count, 6, 'Git process count: %s' % count)
        after = (self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain=v1'),
                 self.git('show-ref'), (self.root/'.git/index').read_bytes())
        self.assertEqual(before, after)

    def test_modified_contract_and_binary_oracle_are_both_detected(self):
        contract = self.root/'knowledge/contracts/contract-05.md'
        oracle = self.root/'tests/oracle-05.py'
        contract.write_text(contract.read_text(encoding='utf-8') + '\nchanged\n', encoding='utf-8')
        oracle.write_bytes(b'\x00altered\r\nline\n')
        result, _ = self.cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('knowledge/contracts/contract-05.md: differs', result.stdout)
        self.assertIn('tests/oracle-05.py: differs', result.stdout)

    def test_added_and_deleted_contracts_are_detected(self):
        (self.root/'knowledge/contracts/contract-01.md').unlink()
        (self.root/'knowledge/contracts/new contract.md').write_text("---\ntests: 'tests/shared.py'\n---\n", encoding='utf-8')
        result, _ = self.cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('contract-01.md: approved contract missing', result.stdout)
        self.assertIn('new contract.md: not in approved reference', result.stdout)

    def test_missing_current_oracle_is_detected(self):
        (self.root/'tests/oracle 01.py').unlink()
        result, _ = self.cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('tests/oracle 01.py: approved artifact missing', result.stdout)

    def test_missing_approved_oracle_fails_without_partial_success(self):
        path = self.root/'knowledge/contracts/contract-01.md'
        path.write_text("---\ntests: 'tests/absent.py'\n---\n", encoding='utf-8')
        self.git('add', '-A'); self.git('commit', '-qm', 'invalid baseline')
        result, _ = self.cli(self.git('rev-parse', 'HEAD'))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('FAIL:', result.stdout)
        self.assertNotIn('PASS:', result.stdout)

    def test_missing_git_object_fails_without_partial_success(self):
        oid = self.git('rev-parse', 'HEAD:tests/oracle 01.py')
        obj = self.root/'.git'/'objects'/oid[:2]/oid[2:]
        self.assertTrue(obj.is_file(), str(obj))
        obj.chmod(0o600)
        obj.unlink()
        result, _ = self.cli()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('FAIL:', result.stdout)
        self.assertNotIn('PASS:', result.stdout)

    def test_escaping_oracle_in_approved_contract_fails_closed(self):
        path = self.root/'knowledge/contracts/contract-01.md'
        path.write_text("---\ntests: '../../outside.py'\n---\n", encoding='utf-8')
        self.git('add', '-A'); self.git('commit', '-qm', 'escaping baseline')
        result, _ = self.cli(self.git('rev-parse', 'HEAD'))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('escapes repository', result.stdout)
        self.assertNotIn('PASS:', result.stdout)

    def test_crlf_and_lf_are_equivalent(self):
        for path in (self.root/'knowledge/contracts/contract-01.md', self.root/'tests/oracle 01.py'):
            data = path.read_bytes()
            path.write_bytes(data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        result, _ = self.cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS:', result.stdout)

    def test_shared_oracle_changes_are_not_hidden(self):
        (self.root/'tests/shared.py').write_text('# tampered\n', encoding='utf-8')
        result, _ = self.cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('tests/shared.py: differs'), 4)

    def test_oracle_contents_are_never_executed(self):
        oracle = self.root/'tests/oracle 01.py'
        oracle.write_text("from pathlib import Path\nPath('executed').write_text('bad')\n", encoding='utf-8')
        self.git('add', '-A'); self.git('commit', '-qm', 'approved inert oracle')
        result, _ = self.cli(self.git('rev-parse', 'HEAD'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root/'executed').exists())

    def test_invalid_commit_cannot_return_partial_success(self):
        result, _ = self.cli('0' * 40)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('FAIL:', result.stdout)
        self.assertNotIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main()
