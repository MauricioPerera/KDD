"""Frozen schema oracle and real, shared Git fixture for traceability."""
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

SPEC = """---
type: 'Concept'
title: 'Value product'
description: 'Return a validated integer value for the caller.'
tags: ['product', 'requirements']
---

# Value product

## Requisitos

- [REQ-001] Return seven and reject invalid input.

## Contexto

The contract supplies executable acceptance criteria.
"""
PLAN = {'schema_version': 1, 'spec': 'knowledge/product-spec.md', 'bindings': [
    {'requirement': 'REQ-001', 'contract': 'knowledge/contracts/value.md', 'tasks': ['TASK-001']}]}
ORACLE = """import unittest
from src.value import value

class ValueTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(value(7), 7)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            value(True)
"""
IMPLEMENTATION = """def value(item):
    if type(item) is not int:
        raise ValueError('integer required')
    return item
"""
NEW_MODULES = ['traceability.py', 'traceability_model.py', 'traceability_git.py']
TASK_MODULES = ['task_model.py', 'task_git.py', 'task_evidence.py', 'validate_tasks.py', 'validate_contracts.py']
SCRIPT_FILES = [*NEW_MODULES, *TASK_MODULES, 'tasks.py', 'process_tree.py', 'verify_quality.py']


def dump(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n'


def isolated_env():
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    return env


def command(root, args, input=None):
    return subprocess.run(args, cwd=root, env=isolated_env(), input=input,
                          capture_output=True, text=True, encoding='utf-8', timeout=120)


def git(root, *args, input=None):
    p = command(root, ['git', *args], input)
    if p.returncode:
        raise AssertionError('Git fixture failed: ' + repr(args) + '\n' + p.stderr)
    return p.stdout.strip()


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def commit(root, message):
    git(root, 'add', '-A')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def task_command(root, operation, *args):
    p = command(root, [sys.executable, 'scripts/tasks.py', operation, 'TASK-001', *args])
    if p.returncode:
        raise AssertionError('Canonical task fixture failed: ' + p.stdout + p.stderr)
    return p


def prepare_project(root):
    root.mkdir()
    git(root, 'init', '-q', '-b', 'main')
    for name, value in [('user.name', 'Traceability integration'), ('user.email', 'trace@example.invalid'),
                        ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
        git(root, 'config', name, value)
    for name in SCRIPT_FILES:
        write(root, 'scripts/' + name, (ROOT / 'scripts' / name).read_text(encoding='utf-8'))
    write(root, 'src/value.py', "def value(item):\n    raise NotImplementedError('fixture red phase')\n")
    write(root, 'tests/__init__.py', '')
    write(root, 'tests/test_value.py', ORACLE)
    write(root, 'knowledge/product-spec.md', SPEC)
    write(root, 'quality/traceability.json', dump(PLAN))
    seal = hashlib.sha256(ORACLE.encode()).hexdigest()
    contract = """---
type: 'Task Contract'
title: 'Validate an integer value'
description: 'Return valid integers and reject booleans before returning a result.'
tags: ['value', 'product']
task: value
intent: 'Return the input integer under the declared constraint.'
target: src/value.py
signature: 'def value(item):'
test_command: 'python -m unittest tests/test_value.py'
budget:
  cyclomatic_max: 3
  nesting_max: 2
tests: tests/test_value.py
tests_sha256: '%s'
touch_only: ['src/value.py']
deps_allowed: ['stdlib']
forbids: ['network']
---

## Intent
Implement the [product requirement](../product-spec.md).
## Interface
Return an integer; reject booleans with ValueError.
## Invariants
Preserve the input value and reject invalid input.
## Examples
- 7 returns 7.
- True is rejected.
## Do / Don't
Do validate type; do not coerce bool.
## Tests
The sealed two-case oracle tests both behaviors.
## Constraints
Only change the declared target.
PARAR y reportar si the approved oracle cannot execute.
""" % seal
    write(root, 'knowledge/contracts/value.md', contract)
    write(root, 'knowledge/index.md', "---\ntype: 'Concept'\ntitle: 'Index'\ndescription: 'Project knowledge index.'\ntags: ['index']\n---\n\n# Index\n\n- [Product](product-spec.md)\n- [Contract](contracts/value.md)\n")
    protected = ['knowledge/product-spec.md', 'quality/traceability.json', 'knowledge/contracts/value.md',
                 'tests/__init__.py', 'tests/test_value.py', *['scripts/' + n for n in SCRIPT_FILES]]
    policy = dict(protected=protected, implementation=['src/value.py'],
                  pm=['knowledge/index.md', 'knowledge/tasks/TASK-001.md'],
                  required_kinds=['functional', 'adversarial', 'traceability'],
                  generated_task_evidence=[{'task_id': 'TASK-001', 'contract': 'knowledge/contracts/value.md'}],
                  checks=[
                      dict(name='product-functional', kind='functional', argv=['python', '-m', 'unittest', 'tests.test_value.ValueTests.test_valid'], timeout=30),
                      dict(name='product-adversarial', kind='adversarial', argv=['python', '-m', 'unittest', 'tests.test_value.ValueTests.test_invalid'], timeout=30),
                      dict(name='requirements-traceability', kind='traceability', argv=['python', 'scripts/traceability.py', '--repo-root', '.', '--ref', 'HEAD', '--manifest', 'quality/traceability.json', '--require-verified'], timeout=90)])
    write(root, 'quality/product.json', dump(policy))
    approved = commit(root, 'contract, requirements and product oracle baseline')
    red = command(root, [sys.executable, '-m', 'unittest', 'tests/test_value.py'])
    if red.returncode == 0 or 'NotImplementedError' not in red.stderr:
        raise AssertionError('Fixture oracle must reject the product stub before implementation')
    task_command(root, 'create', '--title', 'Value task', '--description', 'Close the value requirement',
                 '--contract', 'knowledge/contracts/value.md')
    task_command(root, 'ready', '--approved-ref', approved)
    task_command(root, 'start', '--assignee', 'fixture-developer')
    git(root, 'switch', '-q', 'task/TASK-001')
    write(root, 'src/value.py', IMPLEMENTATION)
    tip = commit(root, 'implement the approved value contract')
    git(root, 'switch', '-q', 'main')
    git(root, 'merge', '--no-ff', '-qm', 'integrate original implementation', 'task/TASK-001')
    tested = git(root, 'rev-parse', 'HEAD')
    task_command(root, 'finish')
    closed = git(root, 'rev-parse', 'HEAD')
    return dict(approved=approved, tip=tip, tested=tested, closed=closed)


class RepositoryFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temp = tempfile.TemporaryDirectory(prefix='kdd trace base ')
        cls.addClassCleanup(cls.base_temp.cleanup)
        cls.base = Path(cls.base_temp.name) / 'project'
        cls.refs = prepare_project(cls.base)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd trace case ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        git(Path(self.temp.name), 'clone', '-q', '--shared', str(self.base), str(self.root))
        for key, value in [('user.name', 'Trace case'), ('user.email', 'trace@example.invalid'),
                           ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            git(self.root, 'config', key, value)

    def cli(self, *args, cwd=None):
        return command(cwd or self.root, [sys.executable, str(self.root / 'scripts/traceability.py'),
                                         '--repo-root', str(self.root), *args])

    def json_result(self, process):
        try:
            return json.loads(process.stdout)
        except ValueError:
            self.fail('CLI must return structured JSON: ' + process.stdout + process.stderr)

    def plan(self):
        return json.loads((self.root / 'quality/traceability.json').read_text(encoding='utf-8'))

    def save_plan(self, plan, message='change declared requirement bindings'):
        write(self.root, 'quality/traceability.json', dump(plan))
        return commit(self.root, message)


class TraceabilityModelTests(unittest.TestCase):
    def parse(self, spec=SPEC, plan=None, raw=None):
        try:
            return importlib.import_module('traceability_model').parse_plan(spec, raw if raw is not None else dump(PLAN if plan is None else plan))
        except NotImplementedError as error:
            self.fail('Schema interface is not implemented: ' + str(error))

    def invalid(self, spec=SPEC, plan=None, raw=None):
        with self.assertRaisesRegex(ValueError, 'TRACE_(SCHEMA|SPEC)'):
            self.parse(spec, plan, raw)

    def test_valid_unicode_plan_preserves_inputs_and_has_fingerprint(self):
        plan = copy.deepcopy(PLAN)
        before = copy.deepcopy(plan)
        result = self.parse(SPEC.replace('Return seven', 'Devolver siete: \u00f1'), plan)
        self.assertEqual(result['spec'], plan['spec'])
        self.assertEqual(result['requirements'][0]['id'], 'REQ-001')
        self.assertIn('\u00f1', result['requirements'][0]['text'])
        self.assertRegex(result['requirements'][0]['fingerprint'], '^[0-9a-f]{64}$')
        self.assertEqual(plan, before)

    def test_fingerprint_is_invariant_to_json_order(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'][0]['tasks'] += ['TASK-002']
        a = self.parse(plan=plan)
        plan['bindings'][0]['tasks'].reverse()
        b = self.parse(raw=json.dumps(plan, sort_keys=False))
        self.assertEqual(a, b)

    def test_text_change_changes_own_fingerprint(self):
        a = self.parse()['requirements'][0]['fingerprint']
        b = self.parse(SPEC.replace('Return seven', 'Return eight'))['requirements'][0]['fingerprint']
        self.assertNotEqual(a, b)

    def test_binding_change_changes_own_fingerprint(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'][0]['tasks'] += ['TASK-002']
        self.assertNotEqual(self.parse()['requirements'][0]['fingerprint'], self.parse(plan=plan)['requirements'][0]['fingerprint'])

    def test_adding_an_unrelated_requirement_preserves_old_fingerprint(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'].append(dict(requirement='REQ-002', contract='knowledge/contracts/value.md', tasks=[]))
        spec = SPEC.replace('## Contexto', '- [REQ-002] A different future outcome.\n\n## Contexto')
        self.assertEqual(self.parse()['requirements'][0]['fingerprint'], self.parse(spec, plan)['requirements'][0]['fingerprint'])

    def test_duplicate_requirement_is_rejected(self):
        self.invalid(SPEC.replace('## Contexto', '- [REQ-001] Duplicate.\n\n## Contexto'))

    def test_invalid_or_empty_requirement_is_rejected(self):
        for line in ['- [REQ-1] Short ID.', '- [REQ-001] ', '- [REQ-X] Invalid.', '- no identifier']:
            with self.subTest(line=line):
                self.invalid(SPEC.replace('- [REQ-001] Return seven and reject invalid input.', line))

    def test_code_fence_cannot_forge_requirements(self):
        self.invalid('---\ntype: Concept\ntitle: Demo\ndescription: Example.\ntags: [demo]\n---\n\n```text\n' + SPEC + '\n```\n')

    def test_requirement_like_example_outside_section_is_ignored(self):
        result = self.parse(SPEC + '\n```text\n- [REQ-999] Not a requirement.\n```\n')
        self.assertEqual([r['id'] for r in result['requirements']], ['REQ-001'])

    def test_missing_or_duplicate_section_is_rejected(self):
        self.invalid(SPEC.replace('## Requisitos', '## Notes'))
        self.invalid(SPEC + '\n## Requisitos\n- [REQ-002] Duplicate section.\n')

    def test_binding_without_requirement_is_rejected(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'][0]['requirement'] = 'REQ-999'
        self.invalid(plan=plan)

    def test_requirement_without_binding_is_rejected(self):
        self.invalid(SPEC.replace('## Contexto', '- [REQ-002] Unlinked.\n\n## Contexto'))

    def test_duplicate_requirement_contract_pair_is_rejected(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'].append(copy.deepcopy(plan['bindings'][0]))
        self.invalid(plan=plan)

    def test_one_task_cannot_name_two_contracts(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'].append(dict(requirement='REQ-001', contract='knowledge/contracts/other.md', tasks=['TASK-001']))
        self.invalid(plan=plan)

    def test_one_task_can_support_two_requirements_of_the_same_contract(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'].append(dict(requirement='REQ-002', contract=PLAN['bindings'][0]['contract'], tasks=['TASK-001']))
        spec = SPEC.replace('## Contexto', '- [REQ-002] Related behavior.\n\n## Contexto')
        self.assertEqual(len(self.parse(spec, plan)['requirements']), 2)

    def test_pending_empty_task_list_is_valid(self):
        plan = copy.deepcopy(PLAN)
        plan['bindings'][0]['tasks'] = []
        self.assertEqual(self.parse(plan=plan)['requirements'][0]['bindings'][0]['tasks'], [])

    def test_invalid_task_assignments_are_rejected(self):
        for tasks in [['TASK-1'], ['TASK-001', 'TASK-001'], ['../TASK-001'], 'TASK-001', [True]]:
            with self.subTest(tasks=tasks):
                plan = copy.deepcopy(PLAN)
                plan['bindings'][0]['tasks'] = tasks
                self.invalid(plan=plan)

    def test_unknown_and_manual_evidence_fields_are_rejected(self):
        for key in ['verified', 'complete', 'passed']:
            with self.subTest(key=key):
                plan = copy.deepcopy(PLAN)
                plan['bindings'][0][key] = True
                self.invalid(plan=plan)
        plan = copy.deepcopy(PLAN)
        plan['extra'] = 'unrecognized'
        self.invalid(plan=plan)

    def test_duplicate_json_keys_are_rejected_at_every_level(self):
        self.invalid(raw=dump(PLAN).replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        self.invalid(raw=dump(PLAN).replace('"requirement": "REQ-001"', '"requirement": "REQ-001", "requirement": "REQ-001"'))

    def test_empty_or_wrong_manifest_types_are_rejected(self):
        for raw in ['[]', '{}', 'null', '{broken', '{"schema_version":true,"spec":"knowledge/a.md","bindings":[]}']:
            with self.subTest(raw=raw):
                self.invalid(raw=raw)
        for value in [True, 2, '1']:
            plan = copy.deepcopy(PLAN)
            plan['schema_version'] = value
            self.invalid(plan=plan)

    def test_unsafe_paths_are_rejected(self):
        for value in ['/tmp/spec.md', '../spec.md', 'knowledge/../spec.md', 'knowledge/./spec.md',
                      'C:/spec.md', 'knowledge\\spec.md', 'knowledge/*.md', 'knowledge/spec.md\n', 'knowledge//spec.md']:
            with self.subTest(path=value):
                plan = copy.deepcopy(PLAN)
                plan['spec'] = value
                self.invalid(plan=plan)
        for value in ['src/value.md', 'knowledge/contracts/nested/value.md', 'knowledge/contracts/../value.md']:
            plan = copy.deepcopy(PLAN)
            plan['bindings'][0]['contract'] = value
            self.invalid(plan=plan)

    def test_spec_requires_concept_frontmatter(self):
        self.invalid(SPEC.replace("type: 'Concept'", "type: 'Task'"))
        self.invalid(SPEC.split('---', 2)[-1])


if __name__ == '__main__':
    unittest.main()
