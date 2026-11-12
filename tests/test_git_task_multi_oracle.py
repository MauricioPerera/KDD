"""Exercise task_git through the CLI and verify_quality from the approved commit."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from tests.test_generated_task_evidence import TaskProject


PRIMARY = 'tests/test_feature1.py'
SECONDARY = 'tests/test_secondary.py'
SUPPORT = 'tests/oracle_support.py'
BINARY = 'tests/fixture.bin'
INVENTORY_HELPER = 'scripts/oracle_inventory.py'
PYTHON = 'python -m unittest'
SECONDARY_TEST = """import unittest
from tests.oracle_support import fixture

class Secondary(unittest.TestCase):
    def test_fixture(self):
        self.assertEqual(fixture(), b'left\\r\\nright\\r\\n')
"""
SUPPORT_SOURCE = """from pathlib import Path

def fixture():
    return Path(__file__).with_name('fixture.bin').read_bytes()
"""
NODE_FILES = ('tests/primary.mjs', 'tests/second case.mjs')
NODE_TEST = "import {test} from 'node:test';\nimport assert from 'node:assert/strict';\n"
ROW = {'executed': 1, 'skipped': 0, 'ok': True}


class GitTaskMultiOracle(unittest.TestCase):
    def project(self, *, command=None, runner='python-unittest', inventory=True,
                secondary=SECONDARY_TEST, unprotected=()):
        area = tempfile.TemporaryDirectory(prefix='kdd-task-oracles-')
        self.addCleanup(area.cleanup)
        project = TaskProject(Path(area.name) / 'product')
        project.write(SUPPORT, SUPPORT_SOURCE)
        (project.root / BINARY).write_bytes(b'left\r\nright\r\n')
        project.write('.gitattributes', BINARY + ' -text\n')
        project.write(SECONDARY, secondary)
        primary = PRIMARY
        oracles = [PRIMARY, SECONDARY, SUPPORT, BINARY, 'tests/__init__.py']
        if command and command.startswith('node '):
            primary, second = NODE_FILES
            project.write(primary, NODE_TEST + "test('first', () => assert.equal(4, 4));\n")
            project.write(second, NODE_TEST + "test('second', () => assert.equal(2, 2));\n")
            oracles = list(NODE_FILES)
        if command is None:
            command = PYTHON + ' ' + PRIMARY + ' tests.test_secondary'
        contract = (project.root / project.contract(1)).read_text(encoding='utf-8')
        contract = contract.replace(PYTHON + ' ' + PRIMARY, command, 1)
        if primary != PRIMARY:
            content = (project.root / primary).read_bytes()
            contract = contract.replace('tests: ' + PRIMARY, 'tests: ' + primary, 1)
            contract = contract.replace(hashlib.sha256(project.oracle(1).encode()).hexdigest(),
                                        hashlib.sha256(content).hexdigest(), 1)
        fields = ''
        if runner:
            fields += 'test_runner: ' + runner + '\n'
        if inventory:
            files = oracles if inventory is True else inventory
            fields += 'oracle_files: ' + json.dumps(files) + '\n'
        contract = contract.replace('budget:\n', fields + 'budget:\n', 1)
        project.write(project.contract(1), contract)
        policy = project.policy()
        policy['protected'] = sorted((set(policy['protected']) | set(oracles) | {INVENTORY_HELPER})
                                     - set(unprotected))
        project.write('quality/product.json', json.dumps(policy, indent=2) + '\n')
        project.ref = project.commit('Simulated independent approval of the inventory')
        return project

    def backlog(self, project):
        project.act('create', 1, '--title', 'Feature', '--description', 'Multi-file product oracle',
                    '--contract', project.contract(1))

    def ready(self, project):
        self.backlog(project)
        result = project.act('ready', 1, '--approved-ref', project.ref, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def integrated(self, project):
        self.ready(project)
        project.act('start', 1, '--assignee', 'fixture worker')
        project.implement(1)

    def finish(self, project):
        result = project.act('finish', 1, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        task = json.loads(result.stdout)['task']
        self.assertEqual(task['status'], 'done')
        self.assertEqual(task['verified_ref'], project.git('rev-parse', 'HEAD^'))
        return task, json.loads((project.root / task['evidence']).read_text(encoding='utf-8'))

    def reject(self, project, operation, *options, pattern):
        before = project.snapshot()
        evidence = tuple(sorted(project.root.glob('docs/task-evidence/*.json')))
        result = project.act(operation, 1, *options, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertRegex(result.stderr, pattern)
        self.assertEqual(project.snapshot(), before)
        self.assertEqual(tuple(sorted(project.root.glob('docs/task-evidence/*.json'))), evidence)
        return result

    def audit(self, project, revision):
        return project.command([sys.executable, 'scripts/validate_tasks.py', '--repo-root',
                                str(project.root), '--head-ref', revision], check=False)

    def test_python_close_records_only_the_two_selected_modules(self):
        project = self.project()
        self.integrated(project)
        task, report = self.finish(project)
        self.assertEqual(report['schema_version'], 2)
        self.assertEqual(report['oracle_results'], {PRIMARY: dict(ROW, executed=2), SECONDARY: ROW})
        self.assertEqual(report['passed_tests'], 3)
        self.assertEqual(report['approved_ref'], project.ref)
        self.assertEqual(report['tested_commit'], task['verified_ref'])
        project.write(SECONDARY, 'raise RuntimeError("audit must read Git without executing the oracle")\n')
        audit = self.audit(project, 'HEAD')
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)

    def test_single_file_keeps_legacy_runner_inference_with_a_declared_inventory(self):
        project = self.project(command=PYTHON + ' ' + PRIMARY, runner=None, inventory=[PRIMARY])
        self.integrated(project)
        _, report = self.finish(project)
        self.assertEqual(report['oracle_results'], {PRIMARY: dict(ROW, executed=2)})

    def test_node_close_records_both_files_with_explicit_tap(self):
        project = self.project(runner='node-test',
            command='node --test --test-reporter=tap tests/primary.mjs "tests/second case.mjs"')
        self.integrated(project)
        _, report = self.finish(project)
        self.assertEqual(report['runner'], 'node')
        self.assertEqual(report['oracle_results'], dict.fromkeys(NODE_FILES, ROW))
        self.assertEqual(report['passed_tests'], 2)

    def test_ready_rejects_ambiguous_or_unapproved_selection(self):
        for command, runner, inventory in (
            (PYTHON + ' ' + PRIMARY + ' tests.test_secondary', 'python-unittest', False),
            (PYTHON + ' ' + PRIMARY + ' tests.test_secondary', None, True),
            (PYTHON + ' ' + PRIMARY + ' tests.test_secondary', 'node-test', True),
            (PYTHON + ' ' + PRIMARY + ' tests.test_feature1', 'python-unittest', True),
            (PYTHON + ' ' + PRIMARY + ' tests.test_outside', 'python-unittest', True),
            (PYTHON + ' tests.test_secondary', 'python-unittest', True),
            (PYTHON + ' ' + PRIMARY + ' tests/../tests/test_secondary.py', 'python-unittest', True),
            (PYTHON + ' ' + PRIMARY + ' -v tests.test_secondary', 'python-unittest', True),
        ):
            with self.subTest(command=command, runner=runner, inventory=inventory):
                project = self.project(command=command, runner=runner, inventory=inventory)
                project.write('tests/test_outside.py', SECONDARY_TEST)
                project.ref = project.commit('An existing test outside the approved inventory')
                self.backlog(project)
                self.reject(project, 'ready', '--approved-ref', project.ref,
                            pattern=r'TASK_RUNNER')
                self.assertEqual(project.act('show', 1)['status'], 'backlog')

    def test_ready_rejects_a_nonprimary_git_symlink(self):
        project = self.project()
        project.git('config', 'core.symlinks', 'false')
        oid = project.git('rev-parse', 'HEAD:' + SECONDARY)
        project.git('update-index', '--cacheinfo', '120000,' + oid + ',' + SECONDARY)
        project.git('checkout-index', '-f', '--', SECONDARY)
        project.git('commit', '-qm', 'Replace the second test with a Git symlink')
        self.assertEqual(project.git('status', '--porcelain'), '')
        self.backlog(project)
        self.reject(project, 'ready', '--approved-ref', project.ref, pattern=r'TASK_PATH')

    def test_start_rejects_drift_in_an_unselected_helper(self):
        project = self.project()
        self.ready(project)
        project.write(SUPPORT, SUPPORT_SOURCE + '\n# unapproved helper change\n')
        project.commit('Modify a helper outside the reviewed oracle')
        self.reject(project, 'start', '--assignee', 'fixture worker', pattern=r'TASK_APPROVAL')
        self.assertEqual(project.act('show', 1)['status'], 'ready')

    def test_ready_compares_binary_helpers_using_approved_attributes(self):
        project = self.project()
        (project.root / BINARY).write_bytes(b'left\nright\n')
        project.write('.gitattributes', BINARY + ' text\n')
        project.commit('Change only line endings and candidate attributes')
        self.backlog(project)
        self.reject(project, 'ready', '--approved-ref', project.ref, pattern=r'TASK_APPROVAL')

    def test_finish_rejects_checkout_drift_hidden_from_status(self):
        project = self.project()
        self.integrated(project)
        project.git('update-index', '--assume-unchanged', SUPPORT)
        project.write(SUPPORT, SUPPORT_SOURCE + '\nPath("oracle-ran").touch()\n')
        self.assertEqual(project.git('status', '--porcelain'), '')
        self.reject(project, 'finish', pattern=r'TASK_(APPROVAL|DIRTY)')
        self.assertFalse((project.root / 'oracle-ran').exists())
        self.assertEqual(project.act('show', 1)['status'], 'in_progress')

    def test_finish_rechecks_inventory_after_the_real_runner(self):
        secondary = SECONDARY_TEST + (
            '\n    def test_checkout_edit(self):\n'
            '        import subprocess\n'
            '        from pathlib import Path\n'
            '        subprocess.run(["git", "update-index", "--assume-unchanged", '
            '"tests/oracle_support.py"], check=True)\n'
            '        with Path("tests/oracle_support.py").open("a", encoding="utf-8") as target:\n'
            '            target.write("\\n# changed during oracle execution\\n")\n'
        )
        project = self.project(secondary=secondary)
        self.integrated(project)
        self.reject(project, 'finish', pattern=r'TASK_(APPROVAL|DIRTY)')
        self.assertIn('changed during oracle execution',
                      (project.root / SUPPORT).read_text(encoding='utf-8'))
        self.assertEqual(project.act('show', 1)['status'], 'in_progress')

    def test_finish_rejects_secondary_with_no_pass_skip_or_failure(self):
        sources = (
            '# no unittest cases\n',
            'import unittest\nraise unittest.SkipTest("second module omitted")\n',
            'import unittest\nclass Broken(unittest.TestCase):\n'
            '    def test_failure(self): self.fail("second module failed")\n',
        )
        for secondary in sources:
            with self.subTest(secondary=secondary):
                project = self.project(secondary=secondary)
                self.integrated(project)
                self.reject(project, 'finish', pattern=r'TASK_TESTS')
                self.assertEqual(project.act('show', 1)['status'], 'in_progress')

    def test_committed_audit_rejects_incomplete_extra_duplicate_or_legacy_receipts(self):
        project = self.project()
        self.integrated(project)
        task, report = self.finish(project)
        original = project.git('rev-parse', 'HEAD')
        node_path = 'knowledge/tasks/TASK-001.md'
        node = (project.root / node_path).read_text(encoding='utf-8')
        rows = report['oracle_results']
        mutations = (
            dict(report, oracle_results={PRIMARY: rows[PRIMARY]}),
            dict(report, oracle_results=dict(rows, extra=ROW)),
            dict(report, passed_tests=1),
            dict(report, oracle_results=dict(rows) | {SECONDARY: dict(ROW, skipped=1)}),
            dict({key: value for key, value in report.items() if key != 'oracle_results'}, schema_version=1),
        )
        payloads = [json.dumps(item) for item in mutations]
        duplicate = json.dumps(SECONDARY) + ': ' + json.dumps(rows[SECONDARY])
        payloads.append(json.dumps(report).replace('"oracle_results": {', '"oracle_results": {' + duplicate + ', ', 1))
        for index, payload in enumerate(payloads):
            with self.subTest(case=index):
                project.git('switch', '-qc', f'forged-{index}', original)
                payload += '\n'
                project.write(task['evidence'], payload)
                updated = node.replace(task['evidence_sha256'], hashlib.sha256(payload.encode()).hexdigest())
                project.write(node_path, updated)
                revision = project.commit('Forge a receipt and recompute its outer seal')
                audit = self.audit(project, revision)
                self.assertNotEqual(audit.returncode, 0, audit.stdout)
                self.assertRegex(audit.stdout + audit.stderr, r'TASK_EVIDENCE|duplicate')

    def test_quality_uses_frozen_inventory_with_equivalent_approvals(self):
        project = self.project()
        helper = (project.root / INVENTORY_HELPER).read_text(encoding='utf-8')
        helper += (
            '\nimport hashlib, json, os\n'
            'from pathlib import Path\n'
            'if os.environ.get("KDD_TEST_ORACLE_INVENTORY_PROBE"):\n'
            '    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()\n'
            '    with open(os.environ["KDD_TEST_ORACLE_INVENTORY_PROBE"], "a", encoding="utf-8") as probe:\n'
            '        probe.write(json.dumps({"path": __file__, "sha256": digest}) + "\\n")\n'
        )
        project.write(INVENTORY_HELPER, helper)
        policy = json.loads((project.root / 'quality/product.json').read_text(encoding='utf-8'))
        for check, module in zip(policy['checks'], ('tests.test_feature1', 'tests.test_secondary')):
            check['argv'] = [sys.executable, '-m', 'unittest', module]
        project.write('quality/product.json', json.dumps(policy, indent=2) + '\n')
        quality_ref = project.commit('Review two checks and the inventory module')
        target = 'src/feature1.py'
        source = (project.root / target).read_text(encoding='utf-8')
        project.write(target, source + '\n# different tree, same inventory\n')
        project.ref = project.commit('Independent approval of the same inventory')
        self.assertNotEqual(project.git('rev-parse', project.ref + '^{tree}'),
                            project.git('rev-parse', quality_ref + '^{tree}'))
        self.integrated(project)
        _, report = self.finish(project)
        self.assertNotEqual(report['approved_ref'], quality_ref)
        project.ref = quality_ref
        probe = project.root.parent / 'inventory-imports.txt'
        helper_path = project.root / INVENTORY_HELPER
        approved_bytes = helper_path.read_bytes()
        checkout_bytes = approved_bytes.replace(b'\n', b'\r\n')
        self.assertNotEqual(approved_bytes, checkout_bytes)
        helper_path.write_bytes(checkout_bytes)
        project.env['KDD_TEST_ORACLE_INVENTORY_PROBE'] = str(probe)
        result = project.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        runs = [line for line in result.stdout.splitlines() if line.startswith('RUN ')]
        self.assertCountEqual(runs, [f'RUN {iteration}/2 {kind} [{kind}]'
                                     for iteration in (1, 2) for kind in ('functional', 'adversarial')])
        self.assertTrue(probe.is_file(), 'the frozen audit must import the approved inventory helper')
        imports = [json.loads(line) for line in probe.read_text(encoding='utf-8').splitlines()]
        self.assertTrue(imports)
        for item in imports:
            self.assertFalse(Path(item['path']).resolve().is_relative_to(project.root.resolve()), item)
            self.assertEqual(item['sha256'], hashlib.sha256(approved_bytes).hexdigest(), item)
        (project.root / BINARY).write_bytes(b'left\nright\n')
        result = project.quality()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(BINARY, result.stderr + result.stdout)
        self.assertNotIn('RUN ', result.stdout)

    def test_quality_rejects_a_different_task_approval_even_after_helper_restoration(self):
        project = self.project()
        quality_ref = project.ref
        project.write(SUPPORT, SUPPORT_SOURCE + '\n# approved for the task only\n')
        project.ref = project.commit('Independent task approval with a different helper')
        self.integrated(project)
        self.finish(project)
        project.write(SUPPORT, SUPPORT_SOURCE)
        project.commit('Restore helper to the bytes approved by the quality policy')
        project.ref = quality_ref
        before = project.snapshot()
        result = project.quality()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(SUPPORT, result.stderr + result.stdout)
        self.assertNotIn('RUN ', result.stdout)
        self.assertEqual(project.snapshot(), before)

    def test_quality_rejects_an_unprotected_oracle_or_inventory_helper_before_checks(self):
        for missing in (SECONDARY, SUPPORT, INVENTORY_HELPER):
            with self.subTest(missing=missing):
                project = self.project(unprotected=(missing,))
                project.write('src/feature1.py', project.implementation(1))
                project.ref = project.commit('Working product under incomplete synthetic policy')
                before = project.snapshot()
                result = project.quality()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(missing, result.stderr + result.stdout)
                self.assertNotIn('RUN ', result.stdout)
                self.assertEqual(project.snapshot(), before)
