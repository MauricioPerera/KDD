"""Build an isolated project for HTTP tests of Board's acceptance closure."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.test_generated_task_evidence import TaskProject


PRIMARY = 'tests/test_feature1.py'
POLICY_ORACLE = 'tests/test_finish_policy.py'
PROBE = 'tests/board_finish_probe.py'
POLICY = 'acceptance.json'
PYTHON_COMMAND = 'python' if shutil.which('python') else 'python3'
OBLIGATIONS = ('signature', 'dependencies', 'budget', 'forbids', 'invariants')
PROBE_SOURCE = '''import json
import os
from pathlib import Path
import subprocess
import time


def observe(kind):
    head = subprocess.check_output(
        ['git', '--no-replace-objects', 'rev-parse', 'HEAD'], encoding='ascii', timeout=10).strip()
    area = Path(os.environ['KDD_BOARD_FINISH_PROBES'])
    with (area / 'runs.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'kind': kind, 'head': head}) + '\\n')
    cutoff = time.monotonic() + 32
    while not (area / 'release').exists():
        if time.monotonic() >= cutoff:
            raise AssertionError('HTTP test did not release the real oracle')
        time.sleep(0.03)
    return (area / 'fail-policy').exists()
'''
PRIMARY_SOURCE = '''import unittest

from src.feature1 import f1
from tests.board_finish_probe import observe


class FixtureOracle(unittest.TestCase):
    def test_preserves_the_feature(self):
        observe('primary')
        self.assertEqual(f1(3), 3)
'''
POLICY_SOURCE = '''import unittest

from src.feature1 import f1
from tests.board_finish_probe import observe


class FixturePolicy(unittest.TestCase):
    def test_policy_check_can_fail_after_the_primary_oracle(self):
        failing = observe('policy')
        self.assertFalse(failing, 'the dependent policy check was rejected')
        with self.assertRaises(ValueError):
            f1(-1)
'''


def put_policy(project, contract, second_task):
    checks = [
        {'obligation': name, 'tests': POLICY_ORACLE, 'test_runner': 'python-unittest',
         'test_command': f'{PYTHON_COMMAND} -m unittest {POLICY_ORACLE}', 'timeout': 45}
        for name in OBLIGATIONS
    ]
    pm = ['knowledge/tasks/TASK-001.md']
    if second_task:
        pm.append('knowledge/tasks/TASK-002.md')
    policy = {'schema_version': 1, 'implementation': ['src/feature1.py'], 'pm': pm,
              'contracts': [{'path': contract, 'checks': checks}]}
    project.write(POLICY, json.dumps(policy) + '\n')


def prepare(root, legacy, second_task):
    project = TaskProject(root)
    for name in ('verify_acceptance.py', 'validation_runtime.py', 'board_test_evidence.py'):
        shutil.copyfile(ROOT / 'scripts' / name, project.root / 'scripts' / name)
    project.write(PRIMARY, PRIMARY_SOURCE)
    project.write(POLICY_ORACLE, POLICY_SOURCE)
    project.write(PROBE, PROBE_SOURCE)
    path = project.contract(1)
    metadata = {'test_runner': 'python-unittest', 'test_timeout': 45,
                'oracle_files': repr([PRIMARY, POLICY_ORACLE, PROBE, 'tests/__init__.py', 'src/__init__.py'])}
    if not legacy:
        put_policy(project, path, second_task)
        metadata['acceptance_policy'] = POLICY
    content = project.contract_text(1, PRIMARY_SOURCE).replace(
        "'python -m unittest ", f"'{PYTHON_COMMAND} -m unittest ", 1)
    marker = '\n---\n## Intent'
    assert content.count(marker) == 1
    content = content.replace(marker, '\n' + '\n'.join(f'{key}: {value}' for key, value in metadata.items()) + marker)
    project.write(path, content)
    project.ref = project.commit('Simulation of an already reviewed fixture contract and policy')
    project.create(1)
    project.act('start', 1, '--assignee', 'fixture worker')
    if second_task:
        project.act('create', 2, '--title', 'Second task', '--description',
                    'Another acceptance request for the same repository', '--contract', path)
        project.act('ready', 2, '--approved-ref', project.ref)
        project.act('start', 2, '--assignee', 'fixture worker')
    project.implement(1)
    return {'root': str(project.root), 'approved_ref': project.ref,
            'tested_commit': project.git('rev-parse', 'HEAD')}


if __name__ == '__main__':
    print(json.dumps(prepare(Path(sys.argv[1]), sys.argv[2] == 'legacy', sys.argv[3] == 'two')))
