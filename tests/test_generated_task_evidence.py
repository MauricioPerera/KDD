"""Real task/evidence fixtures and adversarial approval tests.

All reviewer commits are simulated in temporary repositories. No helper in this
file approves, commits to, or modifies the real checkout.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TRUSTED_TASK_MODULES = ('validate_tasks.py', 'task_git.py', 'task_model.py',
                        'task_evidence.py', 'validate_contracts.py')


def isolated_env():
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                 'PYTHONPATH', 'GITHUB_STEP_SUMMARY', 'NODE_TEST_CONTEXT',
                 'KDD_BOARD_TOKEN'):
        env.pop(name, None)
    return env


class TaskProject:
    """A real fresh Git history, synthetic product, approved oracle and policy."""
    def __init__(self, root, count=1, initialize=True):
        self.root = Path(root)
        self.env = isolated_env()
        self.count = count
        self.ref = ''
        if initialize:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / 'scripts').mkdir(exist_ok=True)
            for source in (ROOT / 'scripts').glob('*.py'):
                shutil.copyfile(source, self.root / 'scripts' / source.name)
            self.write('.gitignore', '__pycache__/\n*.pyc\n.env.local\n.kdd-board/\n')
            self.write('knowledge/index.md', """---
type: 'Concept'
title: 'Own fixture'
description: 'Synthetic product context for integration tests.'
tags: ['fixture']
---
- [Contracts](contracts/)
- [Tasks](tasks/)
""")
            (self.root / 'knowledge/tasks').mkdir(parents=True, exist_ok=True)
            self.write('src/__init__.py', '')
            self.write('tests/__init__.py', '')
            for number in range(1, count + 1):
                self.write('src/feature%s.py' % number,
                           'def f%s(value):\n    raise NotImplementedError("red stub")\n' % number)
                oracle = self.oracle(number)
                self.write('tests/test_feature%s.py' % number, oracle)
                self.write(self.contract(number), self.contract_text(number, oracle))
            policy = self.policy()
            self.write('quality/product.json', json.dumps(policy, indent=2) + '\n')
            self.git('init', '-q', '-b', 'main')
            for name, value in [('user.name', 'Simulated fixture reviewer'),
                                ('user.email', 'fixture@example.invalid'),
                                ('maintenance.autoDetach', 'false'),
                                ('gc.autoDetach', 'false'),
                                ('core.autocrlf', 'false'), ('commit.gpgsign', 'false')]:
                self.git('config', name, value)
            self.ref = self.commit('Simulated reviewer baseline; temporary fixture only')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def command(self, argv, check=True, cwd=None, env=None, timeout=120):
        return subprocess.run(argv, cwd=cwd or self.root, env=env or self.env,
                              capture_output=True, text=True, encoding='utf-8',
                              errors='strict', timeout=timeout, check=check)

    def git(self, *args):
        return self.command(['git', '-C', str(self.root), *args]).stdout.strip()

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    @staticmethod
    def contract(number):
        return 'knowledge/contracts/feature%s.md' % number

    @staticmethod
    def implementation(number):
        if number == 1:
            return """def f1(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer required")
    return value
"""
        if number in (2, 3):
            return ('from src.feature1 import f1\n\ndef f%s(value):\n'
                    '    return f1(value) + %s\n') % (number, (number - 1) * 10)
        return ('from src.feature2 import f2\nfrom src.feature3 import f3\n\n'
                'def f4(value):\n    return f2(value) + f3(value)\n')

    @staticmethod
    def oracle(number):
        expected = {1: 3, 2: 13, 3: 23, 4: 36}[number]
        return """import unittest
from src.feature%s import f%s

class OwnProduct(unittest.TestCase):
    def test_value(self):
        self.assertEqual(f%s(3), %s)

    def test_invalid(self):
        for value in (-1, True, "3", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                f%s(value)

if __name__ == '__main__':
    unittest.main()
""" % (number, number, number, expected, number)

    @staticmethod
    def contract_text(number, oracle):
        return """---
type: 'Task Contract'
title: 'Own feature %s'
description: 'Synthetic contract for a real process integration fixture.'
tags: ['fixture']
task: own-feature-%s
intent: 'Implement own feature.'
target: src/feature%s.py
signature: 'def f%s(value):'
test_command: 'python -m unittest tests/test_feature%s.py'
budget:
  cyclomatic_max: 4
  nesting_max: 2
  lines_max: 40
  params_max: 1
tests: tests/test_feature%s.py
tests_sha256: '%s'
touch_only: ['src/feature%s.py']
deps_allowed: ['src']
forbids: ['network', 'llm']
---
## Intent
Use the own product model.
## Interface
A deterministic pure function.
## Invariants
Reject invalid values and compose prerequisites.
## Examples
- A valid value produces the expected result.
- A negative value raises ValueError.
## Do / Don't
- DO preserve the oracle.
## Tests
Run the sealed real unittest.
## Constraints
PARAR y reportar si falta el contrato.
""" % (number, number, number, number, number, number,
       hashlib.sha256(oracle.encode()).hexdigest(), number)

    def policy(self):
        protected = ['scripts/' + name for name in TRUSTED_TASK_MODULES]
        protected += ['scripts/verify_quality.py', 'src/__init__.py', 'tests/__init__.py']
        protected += [self.contract(n) for n in range(1, self.count + 1)]
        protected += ['tests/test_feature%s.py' % n for n in range(1, self.count + 1)]
        return {
            'protected': protected,
            'implementation': ['src/feature%s.py' % n for n in range(1, self.count + 1)],
            'pm': ['knowledge/tasks/TASK-%03d.md' % n for n in range(1, self.count + 1)],
            'generated_task_evidence': [{'task_id': 'TASK-%03d' % n, 'contract': self.contract(n)}
                                        for n in range(1, self.count + 1)],
            'required_kinds': ['functional', 'adversarial'],
            'checks': [{'name': kind, 'kind': kind,
                        'argv': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                        'timeout': 30} for kind in ('functional', 'adversarial')],
        }

    def act(self, operation, number, *args, check=True):
        result = self.command([sys.executable, 'scripts/tasks.py', '--repo-root',
                               str(self.root), operation, 'TASK-%03d' % number,
                               *args, '--json'], check=check)
        return json.loads(result.stdout) if check else result

    def create(self, number, dependencies=()):
        args = ['--title', 'Own task %s' % number, '--description', 'Own fixture feature',
                '--contract', self.contract(number)]
        for dep in dependencies:
            args += ['--depends-on', 'TASK-%03d' % dep]
        self.act('create', number, *args)
        self.act('ready', number, '--approved-ref', self.ref)

    def implement(self, number):
        self.git('switch', '-q', 'task/TASK-%03d' % number)
        self.write('src/feature%s.py' % number, self.implementation(number))
        tip = self.commit('implement feature %s' % number)
        self.git('switch', '-q', 'main')
        self.git('merge', '--no-ff', 'task/TASK-%03d' % number, '-qm', 'integrate feature')
        return tip

    def complete(self, number, dependencies=()):
        self.create(number, dependencies)
        self.act('start', number, '--assignee', 'fixture worker')
        tip = self.implement(number)
        result = self.act('finish', number)
        return tip, result

    def quality(self):
        # The deployed bootstrap does the same: runner comes from the reviewed commit.
        with tempfile.TemporaryDirectory(prefix='kdd-approved-runner-') as directory:
            runner = Path(directory) / 'verify_quality.py'
            data = self.command(['git', 'show', self.ref + ':scripts/verify_quality.py']).stdout
            runner.write_text(data, encoding='utf-8')
            return self.command([sys.executable, str(runner), '--repo-root', str(self.root),
                                 '--policy', 'quality/product.json', '--approved-ref', self.ref],
                                check=False, timeout=180)

    def snapshot(self):
        return {'head': self.git('rev-parse', 'HEAD'),
                'branches': self.git('show-ref', '--heads'),
                'status': self.git('status', '--porcelain'),
                'tree': self.git('write-tree')}


class GeneratedTaskEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='kdd-generated-evidence-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.area = Path(cls.tmp.name)
        cls.base = TaskProject(cls.area / 'base')
        cls.base.complete(1)
        cls.approved = cls.base.ref
        cls.report = cls.base.act('show', 1)['evidence']
        cls.base_head = cls.base.git('rev-parse', 'HEAD')

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.area)
        self.addCleanup(self.case.cleanup)
        target = Path(self.case.name) / 'project'
        self.base.command(['git', 'clone', '-q', '--shared', str(self.base.root), str(target)])
        self.project = TaskProject(target, initialize=False)
        self.project.ref = self.approved
        for name, value in [('user.name', 'Fixture editor'), ('user.email', 'fixture@example.invalid'),
                            ('core.autocrlf', 'false'), ('commit.gpgsign', 'false')]:
            self.project.git('config', name, value)

    def reject(self):
        result = self.project.quality()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('PASS quality:', result.stdout)
        return result

    def test_closed_task_passes_against_the_initial_approved_reference(self):
        before = self.project.snapshot()
        result = self.project.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS quality:', result.stdout)
        self.assertEqual(result.stdout.count('RUN '), 4)
        self.assertEqual(self.project.ref, self.approved)
        self.assertEqual(self.project.snapshot(), before)

    def test_orphan_and_unselected_evidence_are_not_a_directory_permission(self):
        for name in ('docs/task-evidence/TASK-999-' + 'a' * 40 + '.json',
                     'docs/task-evidence/execute.py'):
            with self.subTest(path=name):
                self.project.write(name, '{}')
                self.reject()
                (self.project.root / name).unlink()

    def test_uncommitted_artifact_and_node_changes_are_rejected(self):
        for name in (self.report, 'knowledge/tasks/TASK-001.md'):
            with self.subTest(path=name):
                path = self.project.root / name
                before = path.read_bytes()
                path.write_bytes(before + b'\n')
                self.reject()
                path.write_bytes(before)

    def test_index_tampering_cannot_hide_behind_restored_working_file(self):
        path = self.project.root / self.report
        before = path.read_bytes()
        path.write_bytes(before + b'\n')
        self.project.git('add', self.report)
        path.write_bytes(before)
        self.reject()

    def test_committed_report_tampering_is_rejected(self):
        path = self.project.root / self.report
        data = json.loads(path.read_text())
        data['passed_tests'] = 100000
        self.project.write(self.report, json.dumps(data))
        self.project.commit('tamper report')
        self.reject()

    def test_forged_output_and_resealed_node_cannot_bypass_history(self):
        p = self.project
        report = json.loads((p.root / self.report).read_text())
        report['stdout'] = 'fabricated'
        report['output_sha256'] = hashlib.sha256((report['stdout'] + report['stderr']).encode()).hexdigest()
        raw = json.dumps(report, sort_keys=True, indent=2) + '\n'
        p.write(self.report, raw)
        node = p.root / 'knowledge/tasks/TASK-001.md'
        old = node.read_text()
        old_report_hash = hashlib.sha256(p.command(['git', 'show', 'HEAD:' + self.report]).stdout.encode()).hexdigest()
        new_report_hash = hashlib.sha256(raw.encode()).hexdigest()
        self.assertIn(old_report_hash, old)
        p.write('knowledge/tasks/TASK-001.md', old.replace(old_report_hash, new_report_hash))
        p.commit('forge evidence with invalid done-to-done transition')
        self.reject()

    def test_protected_oracle_or_policy_changes_still_fail(self):
        for name in ('tests/test_feature1.py', 'quality/product.json'):
            path = self.project.root / name
            before = path.read_bytes()
            path.write_bytes(before + b'\n# unapproved')
            self.reject()
            path.write_bytes(before)

    def test_missing_protected_validator_is_configuration_error_not_untrusted_import(self):
        p = self.project
        policy = json.loads((p.root / 'quality/product.json').read_text())
        policy['protected'].remove('scripts/task_model.py')
        p.write('quality/product.json', json.dumps(policy))
        p.ref = p.commit('new simulated policy missing trusted helper')
        p.write('scripts/task_model.py', 'raise RuntimeError("UNTRUSTED_HELPER_EXECUTED")\n')
        result = self.reject()
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('UNTRUSTED_HELPER_EXECUTED', result.stderr)

    def test_invalid_generated_policy_schemas_are_rejected(self):
        p = self.project
        original = json.loads((p.root / 'quality/product.json').read_text())
        malformed = [[], ['TASK-001'], [{'task_id':'../escape','contract':p.contract(1)}],
                     [{'task_id':'TASK-001','contract':'../oracle.py'}],
                     original['generated_task_evidence'] * 2]
        for value in malformed:
            with self.subTest(policy=value):
                policy = dict(original, generated_task_evidence=value)
                p.write('quality/product.json', json.dumps(policy))
                p.ref = p.commit('simulated malformed policy')
                self.reject()

    def test_checks_cannot_alter_generated_artifacts_between_integrity_checks(self):
        p = self.project
        policy = json.loads((p.root / 'quality/product.json').read_text())
        policy['checks'][0]['argv'] = [sys.executable, '-c',
            "from pathlib import Path; p=Path(%r); p.write_bytes(p.read_bytes()+b'\\n')" % self.report]
        p.write('quality/product.json', json.dumps(policy))
        p.ref = p.commit('simulated reviewed check with forbidden side effect')
        self.reject()

    def test_legacy_policy_without_extension_retains_compatible_behavior(self):
        p = self.project
        policy = json.loads((p.root / 'quality/product.json').read_text())
        policy.pop('generated_task_evidence')
        p.write('quality/product.json', json.dumps(policy))
        p.ref = p.commit('simulated legacy policy with existing committed artifacts')
        p.write('src/feature1.py', p.implementation(1) + '\n# allowed implementation change\n')
        result = p.quality()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
