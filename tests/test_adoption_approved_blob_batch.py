"""Check the standalone adoption launcher's approved inventory with real Git."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'tools/kdd-adoption/validate.py'
FILES = {
    '.github/workflows/kdd-validate.yml': b'name: Example\n',
    '.kdd/validate.py': b'managed launcher\n',
    '.kdd/validator.lock': b'fixed pin\n',
    'lock data/quoted # file.txt': b'head\x00\xff\nlast\n',
}
LAST = tuple(FILES)[-1]
PROBE = r"""
import json
from pathlib import Path
import runpy
import subprocess
import sys

launcher, revision, mode, *paths = sys.argv[1:]
module = runpy.run_path(launcher)
check = module['check_approved_paths']
check.__globals__['ROOT'] = Path.cwd()
events = []
real_run = subprocess.run

def tamper(argv, **kwargs):
    result = real_run(argv, **kwargs)
    if '--batch' in argv and 'cat-file' in argv and not result.returncode:
        if mode == 'trailing':
            result.stdout += b'unexpected output\n'
        elif mode == 'wrong-oid':
            _, separator, remainder = result.stdout.partition(b' ')
            result.stdout = b'0' * 40 + separator + remainder
    return result

def observe(event, details):
    if event == 'subprocess.Popen':
        command = details[1]
        events.append(command.split() if isinstance(command, str) else command)

sys.addaudithook(observe)
if mode in ('trailing', 'wrong-oid'):
    subprocess.run = tamper
before = after = error = None
try:
    before = {path: data.hex() for path, data in check(revision, paths).items()}
    if mode == 'mutate':
        Path(paths[-1]).write_bytes(b'second pass changed the worktree')
        after = check(revision, paths)
except (ValueError, OSError) as exc:
    error = str(exc)
print(json.dumps(dict(before=before, after=after, error=error, git=events)))
"""


class AdoptionApprovedBlobBatch(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix='kdd-adoption-blobs-')
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name).resolve()
        self.git('init', '-q', '-b', 'main', '--template=')
        self.git('config', 'core.autocrlf', 'false')
        for path, data in FILES.items():
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        self.git('add', '-A')
        self.git('-c', 'user.name=KDD fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Review managed paths in fixture')
        self.ref = self.git('rev-parse', 'HEAD')

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.root,
                                       stderr=subprocess.PIPE, timeout=30).decode('utf-8').strip()

    def probe(self, mode='read'):
        stdout = subprocess.check_output(
            [sys.executable, '-I', '-X', 'utf8', '-B', '-c', PROBE, str(SOURCE),
             self.ref, mode, *FILES],
            cwd=self.root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=60)
        return json.loads(stdout)

    def test_four_paths_use_one_blob_command_and_preserve_bytes(self):
        for path, data in FILES.items():
            (self.root / path).write_bytes(data.replace(b'\n', b'\r\n'))
        receipt = self.probe()
        self.assertIsNone(receipt['error'])
        self.assertEqual(receipt['before'], {path: body.hex() for path, body in FILES.items()})
        commands = receipt['git']
        self.assertEqual(len(commands), 4, commands)
        [objects] = [argv for argv in commands if 'cat-file' in argv]
        self.assertIn('--batch', objects)
        self.assertIn('--no-replace-objects', objects)

    def test_each_observation_rechecks_checkout_bytes_hidden_from_status(self):
        self.git('update-index', '--assume-unchanged', '--', LAST)
        receipt = self.probe('mutate')
        self.assertEqual(receipt['before'][LAST], FILES[LAST].hex())
        self.assertIn(LAST, receipt['error'])
        self.assertIsNone(receipt['after'])
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_staged_only_blob_or_mode_is_rejected(self):
        target = self.root / LAST
        target.write_bytes(b'only the index will retain this change')
        self.git('add', '--', LAST)
        target.write_bytes(FILES[LAST])
        receipt = self.probe()
        self.assertIsNone(receipt['before'])
        self.assertIn(LAST, receipt['error'])

    def test_divergent_head_is_rejected_when_index_and_checkout_match_approval(self):
        (self.root / LAST).write_bytes(b'only the candidate will retain this change')
        self.git('add', '--', LAST)
        self.git('-c', 'user.name=KDD fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Change a managed object in HEAD')
        self.git('restore', '--source', self.ref, '--staged', '--worktree', '--', LAST)
        receipt = self.probe()
        self.assertIsNone(receipt['before'])
        self.assertIn(LAST, receipt['error'])

    def test_batch_output_with_wrong_identity_or_trailing_bytes_is_rejected(self):
        for mode in ('wrong-oid', 'trailing'):
            with self.subTest(mode=mode):
                receipt = self.probe(mode)
                self.assertIsNone(receipt['before'])
                self.assertTrue(receipt['error'])

    def test_replace_does_not_change_approved_bytes_or_hide_a_local_change(self):
        source = self.git('rev-parse', 'HEAD:' + LAST)
        target = self.root / LAST
        target.write_bytes(b'a replacement body\n')
        replacement = self.git('hash-object', '-w', '--', LAST)
        self.git('replace', source, replacement)
        self.assertEqual(self.git('cat-file', 'blob', source), 'a replacement body')
        target.write_bytes(FILES[LAST])
        self.assertIsNone(self.probe()['error'])
        target.write_bytes(b'a replacement body\n')
        receipt = self.probe()
        self.assertIsNone(receipt['before'])
        self.assertIn(LAST, receipt['error'])

    def test_missing_last_git_object_never_returns_a_partial_snapshot(self):
        oid = self.git('rev-parse', 'HEAD:' + LAST)
        loose = self.root / '.git' / 'objects' / oid[:2] / oid[2:]
        loose.chmod(0o600)
        loose.unlink()
        receipt = self.probe()
        self.assertIsNone(receipt['before'])
        self.assertTrue(receipt['error'])
        self.assertEqual((self.root / LAST).read_bytes(), FILES[LAST])


if __name__ == '__main__':
    unittest.main()
