"""Measure real task approval reads without weakening the sealed inventory."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import test_git_task_multi_oracle as fixture


CHECK = r"""
import json
import re
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd() / 'scripts'))
import task_git

approved, revision, contract, mode, receipt, *auxiliary_paths = sys.argv[1:]
real_run = subprocess.run
inventory_commands = []
diagnostic = {
    'old-git': b'fatal: bad cat-file format: %(objectmode)\n',
    'corrupt': b'fatal: corrupt object\n',
}.get(mode)

def reads_inventory(argv, payload):
    if not any(verb in argv for verb in ('ls-tree', 'cat-file', 'show')):
        return False
    if any(arg.rpartition(':')[2] in auxiliary_paths for arg in argv):
        return True
    if 'ls-tree' in argv:
        return False
    if 'cat-file' not in argv:
        return False
    if argv[argv.index('cat-file') + 1] == 'blob':
        return True
    if '--batch-check' in argv or any('%(objectmode)' in arg for arg in argv):
        return True
    requests = (payload or b'').splitlines()
    return any(path.encode() in (payload or b'') for path in auxiliary_paths) or (
        '--batch' in argv and bool(requests)
        and all(re.fullmatch(rb'[0-9a-f]{40}|[0-9a-f]{64}', row) for row in requests))

def probe_git(argv, **kwargs):
    reads_mode = any('%(objectmode)' in arg for arg in argv)
    is_snapshot = '--no-replace-objects' in argv
    if diagnostic and is_snapshot and reads_mode:
        return subprocess.CompletedProcess(argv, 128, b'', diagnostic)
    if reads_inventory(argv, kwargs.get('input')):
        inventory_commands.append(argv)
    result = real_run(argv, **kwargs)
    if mode == 'trailing' and is_snapshot and (reads_mode or '--batch' in argv):
        if result.returncode == 0:
            result.stdout += b'extra record data\n'
    return result

if mode == 'portable':
    task_git._read_metadata = lambda *args, **kwargs: False
with patch.object(subprocess, 'run', probe_git):
    try:
        result = task_git.contract_metadata(Path.cwd(),
            {'contract': contract, 'approved_ref': approved}, revision, committed_only=True)
    except (ValueError, task_git.TaskError) as exc:
        print(exc)
        raise SystemExit(1) from exc
    finally:
        Path(receipt).write_text(json.dumps(inventory_commands), encoding='utf-8')
print(json.dumps(result))
"""


class TaskOracleSnapshotBatch(unittest.TestCase):
    def setUp(self):
        builder = fixture.GitTaskMultiOracle()
        self.addCleanup(builder.doCleanups)
        self.project = builder.project()
        self.project.write('note.txt', 'Unrelated product note.\n')
        self.revision = self.project.commit('Advance the candidate without changing the inventory')
        self.assertNotEqual(self.revision, self.project.ref)

    def read(self, mode='native'):
        with tempfile.TemporaryDirectory(prefix='kdd-oracle-trace-') as area:
            trace = Path(area) / 'git.jsonl'
            matched = Path(area) / 'inventory.json'
            project = self.project
            result = project.command(
                [sys.executable, '-B', '-c', CHECK, project.ref, self.revision,
                 project.contract(1), mode, str(matched), fixture.BINARY,
                 fixture.SECONDARY, fixture.SUPPORT],
                check=False, env=dict(project.env, GIT_TRACE2_EVENT=str(trace)))
            self.assertTrue(trace.is_file(), result.stdout + result.stderr)
            launches = []
            for line in trace.read_text(encoding='utf-8').splitlines():
                event = json.loads(line)
                if event['event'] == 'start':
                    launches.append(event['argv'])
            inventory = json.loads(matched.read_text(encoding='utf-8'))
            self.assertLessEqual(len(inventory), len(launches))
            return result, launches, inventory

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(fixture.BINARY, json.loads(result.stdout)['oracle_files'])

    @staticmethod
    def is_mode_query(argv):
        return any(arg.startswith('--batch-command=') and '%(objectmode)' in arg for arg in argv)

    def assert_portable(self, launches, commands, probes):
        self.assertEqual(sum('ls-tree' in argv for argv in commands), 2, commands)
        self.assertEqual(sum('--batch' in argv for argv in commands), 1, commands)
        self.assertEqual(sum(self.is_mode_query(argv) for argv in commands), probes, commands)
        self.assertEqual(len(commands), 3 + probes, commands)
        self.assertTrue(all('--no-replace-objects' in argv for argv in commands))
        self.assertLessEqual(len(launches), 27 + probes)

    def test_two_revisions_share_one_mode_and_content_batch_if_supported(self):
        ref = self.project.ref + ':' + fixture.BINARY
        check = subprocess.run(
            ['git', 'cat-file', '--batch-command=%(objectmode)'],
            input=('info ' + ref + '\n').encode(), cwd=self.project.root,
            env=self.project.env, capture_output=True, timeout=30)
        result, launches, commands = self.read()
        self.assert_success(result)
        if check.returncode == 0:
            self.assertEqual(check.stdout, b'100644\n')
            self.assertEqual(len(commands), 1, commands)
            self.assertTrue(self.is_mode_query(commands[0]))
            self.assertIn('--no-replace-objects', commands[0])
            self.assertLessEqual(len(launches), 25)
        else:
            self.assert_portable(launches, commands, probes=1)

    def test_portable_route_still_batches_bodies_across_two_trees(self):
        result, launches, commands = self.read('portable')
        self.assert_success(result)
        self.assert_portable(launches, commands, probes=0)

    def test_old_git_objectmode_diagnostic_is_distinct_from_object_corruption(self):
        with self.subTest(error='unsupported format'):
            result, launches, commands = self.read('old-git')
            self.assert_success(result)
            self.assert_portable(launches, commands, probes=0)
        with self.subTest(error='corrupt object'):
            result, _, _ = self.read('corrupt')
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('corrupt object', result.stdout)
        with self.subTest(error='trailing data after real Git records'):
            result, _, _ = self.read('trailing')
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('unexpected', result.stdout)

    def test_candidate_index_mode_in_commit_cannot_hide_behind_equal_oid(self):
        project = self.project
        oid = project.git('rev-parse', 'HEAD:' + fixture.SECONDARY)
        project.git('update-index', '--cacheinfo', '120000,' + oid + ',' + fixture.SECONDARY)
        project.git('commit', '-qm', 'Publish a link mode with identical bytes')
        self.revision = project.git('rev-parse', 'HEAD')
        for mode in ('native', 'portable'):
            with self.subTest(mode=mode):
                result, _, _ = self.read(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('TASK_PATH', result.stdout)

    def test_git_replace_cannot_hide_changed_binary_inventory(self):
        project = self.project
        approved = project.git('rev-parse', 'HEAD:' + fixture.BINARY)
        (project.root / fixture.BINARY).write_bytes(b'left\nright\n')
        self.revision = project.commit('Change only the binary line endings')
        changed = project.git('rev-parse', 'HEAD:' + fixture.BINARY)
        project.git('replace', changed, approved)
        self.assertNotEqual(changed, approved)
        replaced = subprocess.check_output(
            ['git', 'show', 'HEAD:' + fixture.BINARY], cwd=project.root, env=project.env)
        self.assertEqual(replaced, b'left\r\nright\r\n')
        for mode in ('native', 'portable'):
            with self.subTest(mode=mode):
                result, _, _ = self.read(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('TASK_APPROVAL', result.stdout)

    def test_replacing_approved_contract_cannot_disable_inventory(self):
        project = self.project
        (project.root / fixture.BINARY).write_bytes(b'left\nright\n')
        self.revision = project.commit('Change bytes in the approved binary fixture')
        contract = project.contract(1)
        original = project.git('rev-parse', project.ref + ':' + contract)
        source = (project.root / contract).read_bytes()
        alternate = b'\n'.join(line for line in source.split(b'\n')
                               if not line.startswith(b'oracle_files: '))
        alternate = alternate.replace(b' tests.test_secondary', b'', 1)
        project.write('contract-replacement.txt', alternate.decode('utf-8'))
        replacement = project.git('hash-object', '-w', '--', 'contract-replacement.txt')
        (project.root / 'contract-replacement.txt').unlink()
        project.git('replace', original, replacement)
        overridden = project.git('show', project.ref + ':' + contract)
        self.assertNotIn('oracle_files:', overridden)
        for mode in ('native', 'portable'):
            with self.subTest(mode=mode):
                result, _, _ = self.read(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('TASK_APPROVAL', result.stdout)


if __name__ == '__main__':
    unittest.main()
