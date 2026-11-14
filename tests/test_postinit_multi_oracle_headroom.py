"""Exercise task_git through the CLI and the real post-init launcher."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import test_git_task_multi_oracle as fixture


ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path('tools/ci/postinit-module-order.json')
MODULE = 'test_git_task_multi_oracle'
ORDER_DIGEST = '28d017f0517a3af9c77720650dbe501e7a840f99d9eb3131466a69e95a39c107'
INSERTIONS = {
    MODULE: 2,
    'test_adoption_trusted_pr': 12,
    'test_task_oracle_execution_proof': 14,
    'test_adopt_project': 20,
    'test_adoption_python_preparation': 21,
    'test_adoption_quality_reference': 22,
    'test_trusted_pr_event_binding': 42,
    'test_composite_quality_checkout': 49,
    'test_adoption_validator_pin': 60,
}


def raw_inventory_commands(trace):
    rows = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    by_environment = {row['sid'] for row in rows
                      if row.get('event') == 'def_param'
                      and row.get('param') == 'GIT_NO_REPLACE_OBJECTS'
                      and row.get('value') == '1'}
    commands = []
    for row in rows:
        if row.get('event') != 'start':
            continue
        args = row['argv'][1:]
        raw = '--no-replace-objects' in args or row['sid'] in by_environment
        if 'ls-tree' in args and (raw or fixture.BINARY in args):
            commands.append((args[args.index('ls-tree'):], raw))
        elif 'cat-file' in args and raw:
            commands.append((args[args.index('cat-file'):], raw))
    return commands


def traced_operation(project, operation, *args):
    trace = project.root.parent / (operation + '-trace.jsonl')
    original = project.env
    project.env = dict(original, GIT_TRACE2_EVENT=str(trace),
                       GIT_TRACE2_ENV_VARS='GIT_NO_REPLACE_OBJECTS')
    project.env.pop('GIT_NO_REPLACE_OBJECTS', None)
    try:
        result = project.act(operation, 1, *args, check=False)
    finally:
        project.env = original
    return result, raw_inventory_commands(trace)


class InventoryBatch(unittest.TestCase):
    def project(self):
        helper = fixture.GitTaskMultiOracle()
        self.addCleanup(helper.doCleanups)
        return helper, helper.project()

    def test_ready_enumerates_both_revisions_and_reads_blobs_once(self):
        helper, project = self.project()
        project.write('src/feature1.py', project.implementation(1))
        advanced = project.commit('Advance the product after independent oracle approval')
        self.assertNotEqual(advanced, project.ref)
        helper.backlog(project)
        candidate = project.git('rev-parse', 'HEAD')
        result, observed = traced_operation(project, 'ready', '--approved-ref', project.ref)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(project.act('show', 1)['approved_ref'], project.ref)
        self.assertTrue(all(raw for _, raw in observed), observed)
        commands = [args for args, _ in observed]
        self.assertEqual([args[0] for args in commands], ['ls-tree', 'ls-tree', 'cat-file'], commands)
        self.assertIn(project.ref, commands[0])
        self.assertIn(candidate, commands[1])
        self.assertIn(fixture.BINARY, commands[0])
        self.assertIn(fixture.BINARY, commands[1])
        self.assertIn('--batch', commands[2])

    def test_reads_each_oid_once_even_with_a_text_equivalent_candidate_blob(self):
        helper, project = self.project()
        path = project.root / fixture.SUPPORT
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        project.commit('Use CRLF only in the candidate helper')
        helper.backlog(project)
        candidate = project.git('rev-parse', 'HEAD')
        names = (project.contract(1), fixture.PRIMARY, fixture.SECONDARY, fixture.SUPPORT,
                 fixture.BINARY, 'tests/__init__.py')
        approved = {project.git('rev-parse', project.ref + ':' + name) for name in names}
        current = {project.git('rev-parse', candidate + ':' + name) for name in names}
        self.assertNotEqual(approved, current)
        self.assertTrue(approved & current)
        project.env.pop('GIT_NO_REPLACE_OBJECTS', None)
        code = (
            'import json, os, subprocess, sys\n'
            'from pathlib import Path\n'
            'sys.path.insert(0, sys.argv[1])\n'
            'import task_git\n'
            'run, batches = subprocess.run, []\n'
            'def observe(argv, *args, **options):\n'
            '    env = options.get("env") or os.environ\n'
            '    raw = "--no-replace-objects" in argv or env.get("GIT_NO_REPLACE_OBJECTS") == "1"\n'
            '    if raw and "cat-file" in argv and "--batch" in argv:\n'
            '        batches.append(options["input"].decode("utf-8").splitlines())\n'
            '    return run(argv, *args, **options)\n'
            'subprocess.run = observe\n'
            'task_git.mutate(Path.cwd(), "ready", "TASK-001", {"approved_ref": sys.argv[2]})\n'
            'print(json.dumps(batches))\n'
        )
        result = project.command([sys.executable, '-I', '-c', code,
                                  str(project.root / 'scripts'), project.ref], check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(project.act('show', 1)['status'], 'ready')
        batches = json.loads(result.stdout)
        self.assertEqual(len(batches), 1, batches)
        self.assertCountEqual(batches[0], approved | current)

    def test_same_blob_in_a_symlink_is_rejected_in_either_revision(self):
        for invalid in ('approved', 'candidate'):
            with self.subTest(invalid=invalid):
                helper, project = self.project()
                project.git('config', 'core.symlinks', 'false')
                name = fixture.SECONDARY
                oid = project.git('rev-parse', 'HEAD:' + name)
                project.git('update-index', '--cacheinfo', f'120000,{oid},{name}')
                project.git('checkout-index', '-f', '--', name)
                project.git('commit', '-qm', 'Same contents with a symlink Git mode')
                self.assertEqual(project.git('rev-parse', 'HEAD:' + name), oid)
                if invalid == 'approved':
                    project.ref = project.git('rev-parse', 'HEAD')
                    project.git('update-index', '--cacheinfo', f'100644,{oid},{name}')
                    project.git('checkout-index', '-f', '--', name)
                    project.git('commit', '-qm', 'Restore only the regular Git mode')
                self.assertEqual(project.git('status', '--porcelain'), '')
                helper.backlog(project)
                helper.reject(project, 'ready', '--approved-ref', project.ref, pattern='TASK_PATH')

    def test_inventory_reads_the_original_binary_despite_a_replacement_blob(self):
        helper, project = self.project()
        original = project.git('rev-parse', 'HEAD:' + fixture.BINARY)
        different = project.root.parent / 'replacement.bin'
        different.write_bytes(b'left\nright\n')
        replacement = project.git('hash-object', '-w', '--no-filters', str(different))
        self.assertNotEqual(original, replacement)
        project.env.pop('GIT_NO_REPLACE_OBJECTS', None)
        project.git('replace', original, replacement)
        self.assertEqual(project.git('cat-file', '-s', original), str(different.stat().st_size))
        self.assertNotEqual(project.git('--no-replace-objects', 'cat-file', '-s', original),
                            str(different.stat().st_size))
        helper.ready(project)
        self.assertEqual((project.root / fixture.BINARY).read_bytes(), b'left\r\nright\r\n')
        self.assertEqual(project.act('show', 1)['approved_ref'], project.ref)


    def test_missing_inventory_path_is_a_path_error(self):
        helper, project = self.project()
        project.git('rm', '--', fixture.SUPPORT)
        project.commit('Remove an unselected approved helper')
        helper.backlog(project)
        helper.reject(project, 'ready', '--approved-ref', project.ref, pattern='TASK_PATH')

    def test_duplicate_tree_entries_cannot_approve_the_first_blob(self):
        _, project = self.project()
        name = 'root-oracle.bin'
        (project.root / name).write_bytes(b'inventoried\0bytes')
        project.commit('Commit a regular root inventory blob')
        oid = project.git('rev-parse', 'HEAD:' + name)
        tree = project.git('rev-parse', 'HEAD^{tree}')
        options = dict(cwd=project.root, env=project.env, timeout=30)
        contents = subprocess.check_output(['git', 'cat-file', 'tree', tree], **options)
        entry = ('100644 ' + name + '\0').encode() + bytes.fromhex(oid)
        self.assertEqual(contents.count(entry), 1)
        tree = subprocess.check_output(['git', 'hash-object', '--literally', '-w', '-t', 'tree', '--stdin'],
                                       input=contents.replace(entry, entry + entry, 1), **options)
        malformed = project.git('commit-tree', tree.decode().strip(), '-m', 'Duplicate inventory entry')
        matches = project.git('ls-tree', malformed, '--', name).splitlines()
        self.assertEqual(len(matches), 2)
        code = ('import sys\nfrom pathlib import Path\n'
                'sys.path.insert(0, sys.argv[1])\nimport task_git\n'
                'task_git._oracle_artifacts(Path.cwd(), sys.argv[2], [sys.argv[3]])\n')
        result = project.command([sys.executable, '-I', '-c', code,
                                  str(ROOT / 'scripts'), malformed, name], check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_PATH', result.stderr)

    def test_finish_rereads_a_committed_blob_removed_by_the_real_runner(self):
        secondary = fixture.SECONDARY_TEST + (
            '\n    def test_remove_committed_blob(self):\n'
            '        import os, subprocess\n'
            '        from pathlib import Path\n'
            '        oid = subprocess.check_output(["git", "rev-parse", "HEAD:tests/fixture.bin"], text=True).strip()\n'
            '        Path(".git", "objects", oid[:2], oid[2:]).replace(os.environ["KDD_ORACLE_MOVE_TO"])\n'
        )
        helper = fixture.GitTaskMultiOracle()
        self.addCleanup(helper.doCleanups)
        project = helper.project(secondary=secondary)
        helper.integrated(project)
        destination = project.root.parent / 'removed-object'
        project.env['KDD_ORACLE_MOVE_TO'] = str(destination)
        before = project.git('rev-parse', 'HEAD')
        branches = project.git('show-ref', '--heads')
        result, observed = traced_operation(project, 'finish')
        self.assertTrue(destination.is_file(), result.stdout + result.stderr)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('TASK_GIT', result.stderr)
        self.assertEqual(project.git('rev-parse', 'HEAD'), before)
        self.assertEqual(project.git('show-ref', '--heads'), branches)
        self.assertEqual(list(project.root.glob('docs/task-evidence/*.json')), [])
        self.assertTrue(all(raw for _, raw in observed), observed)
        commands = [args[0] for args, _ in observed]
        self.assertEqual(commands, ['ls-tree', 'ls-tree', 'cat-file'] * 3, observed)


class MultiOraclePriority(unittest.TestCase):
    def test_inserts_only_the_measured_modules_in_their_proposed_positions(self):
        order = json.loads((ROOT / PROFILE).read_bytes())
        for name, position in INSERTIONS.items():
            with self.subTest(module=name):
                self.assertEqual(order[position - 1], name)
                self.assertEqual(order.count(name), 1)
        previous = [name for name in order if name not in INSERTIONS]
        self.assertEqual(hashlib.sha256(('\n'.join(previous) + '\n').encode()).hexdigest(),
                         ORDER_DIGEST)

    def test_native_launcher_preserves_inventory_workers_and_unprioritized_cases(self):
        names = ['test_aaa_unprioritized', MODULE, 'test_task_committed_artifacts', 'test_adopt_project']
        with tempfile.TemporaryDirectory(prefix='kdd-postinit-multi-order-') as temp:
            root = Path(temp)
            scripts = root / 'scripts'
            scripts.mkdir()
            for name in ('init_post_apply_suite.py', 'run_test_suite.py', 'process_tree.py'):
                shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
            target = root / PROFILE
            target.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / PROFILE, target)
            tests = root / 'tests'
            tests.mkdir()
            source = ('import unittest\nfrom pathlib import Path\n'
                      'class Example(unittest.TestCase):\n'
                      '    def test_observed(self):\n'
                      '        Path(__name__ + ".ran").write_text("ran", encoding="utf-8")\n')
            for name in names:
                (tests / (name + '.py')).write_text(source, encoding='utf-8')
            report = root / 'suite.json'
            command = [sys.executable, str(scripts / 'init_post_apply_suite.py'),
                       '--repo-root', str(root), '--report-json', str(report)]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    encoding='utf-8', timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            observed = json.loads(report.read_bytes())
            expected = [name + '.Example.test_observed' for name in sorted(names)]
            self.assertEqual(observed['expected_ids'], expected)
            self.assertEqual(observed['executed_ids'], expected)
            self.assertEqual(observed['skipped'], [])
            self.assertEqual(observed['fixture_omitted_ids'], [])
            for name in names:
                self.assertEqual((root / (name + '.ran')).read_text(), 'ran')
            order = [row['module'] for row in observed['modules']]
            if os.name == 'nt':
                self.assertEqual(observed['workers'], 10)
                self.assertEqual(observed['scheduling']['modules'], order)
                self.assertEqual(order, ['test_task_committed_artifacts', MODULE,
                                         'test_adopt_project', 'test_aaa_unprioritized'])
                self.assertEqual(observed['scheduling']['profile_sha256'],
                                 hashlib.sha256(target.read_bytes()).hexdigest())
            else:
                self.assertEqual(observed['workers'], 4)
                self.assertNotIn('scheduling', observed)
                self.assertEqual(order, sorted(names))


if __name__ == '__main__':
    unittest.main()
