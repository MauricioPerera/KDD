"""Exercise approval selection and acceptance together on real Git commits."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests import test_contract_acceptance


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/validate.yml'


def step(name):
    source = WORKFLOW.read_text(encoding='utf-8')
    block = source.split(f'      - name: {name}\n', 1)[1].split('\n      - ', 1)[0]
    header, body = block.split('        run: |\n', 1)
    return header, textwrap.dedent(body)


class AcceptanceBaselineRoutingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_contract_acceptance.AcceptanceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.temporary = tempfile.TemporaryDirectory(prefix='kdd-acceptance-routing-')
        self.addCleanup(self.temporary.cleanup)
        self.scratch = Path(self.temporary.name)
        self.root = self.fixture.root
        self.previous = self.fixture.ref
        verifier = self.root / 'scripts/verify_acceptance.py'
        verifier.parent.mkdir()
        shutil.copyfile(ROOT / 'scripts/verify_acceptance.py', verifier)
        self.fixture.freeze()
        self.approved = self.fixture.ref

    def run_block(self, code, env):
        return subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=self.root,
                              env=env, capture_output=True, text=True, encoding='utf-8',
                              timeout=90)

    def acceptance(self, *, explicit=False, legacy=''):
        tree = self.fixture.git('rev-parse', 'HEAD^{tree}')
        registry = {'schema_version': 1, 'trees': {tree: {'baseline_ref': self.approved}}}
        env_file = self.scratch / 'github.env'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'),
                   RUNNER_TEMP=str(self.scratch), GITHUB_ENV=str(env_file),
                   KDD_REQUIRED_EVIDENCE='', KDD_QUALITY_POLICY='quality.json',
                   KDD_APPROVAL_REGISTRY='' if explicit else json.dumps(registry),
                   KDD_EXPLICIT_APPROVED_BASELINE_REF=self.approved if explicit else '',
                   KDD_EXPLICIT_QUALITY_APPROVED_REF='', KDD_ACCEPTANCE_POLICY='acceptance.json',
                   KDD_ACCEPTANCE_REQUIRED='false')
        env.pop('KDD_ACCEPTANCE_APPROVED_REF', None)
        selector = self.run_block(step('Select approved references')[1], env)
        self.assertEqual(selector.returncode, 0, selector.stdout + selector.stderr)
        self.assertEqual(json.loads(selector.stdout)['baseline_ref'], self.approved)
        env.update(line.split('=', 1) for line in env_file.read_text(encoding='utf-8').splitlines())
        self.assertEqual(env['KDD_APPROVED_BASELINE_REF'], self.approved)
        header, body = step('Verify required contract acceptance')
        # Model the historical step-level override after the GITHUB_ENV update.
        if '          KDD_ACCEPTANCE_APPROVED_REF:' in header:
            env['KDD_ACCEPTANCE_APPROVED_REF'] = self.approved if explicit else legacy
        return self.run_block(body, env)

    def matrix(self):
        return json.loads((self.scratch / 'kdd-acceptance.json').read_text(encoding='utf-8'))

    def test_registry_only_rejects_deleted_approved_policy(self):
        self.fixture.git('rm', 'acceptance.json')
        self.fixture.git('-c', 'user.name=Acceptance Test', '-c', 'user.email=test@example.invalid',
                         'commit', '-qm', 'remove approved acceptance policy')
        result = self.acceptance()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        matrix = self.matrix()
        self.assertEqual(matrix['approved_ref'], self.approved)
        self.assertEqual(matrix['state'], 'structure_invalid')
        self.assertIn('Protected file missing or symlink: acceptance.json', matrix['error'])

    def test_stale_global_reference_does_not_replace_registry_selection(self):
        result = self.acceptance(legacy=self.previous)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        matrix = self.matrix()
        self.assertEqual(matrix['approved_ref'], self.approved)
        self.assertEqual(matrix['state'], 'acceptance_approved')

    def test_explicit_reusable_reference_also_reaches_the_matrix(self):
        result = self.acceptance(explicit=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        matrix = self.matrix()
        self.assertEqual(matrix['approved_ref'], self.approved)
        self.assertEqual(matrix['state'], 'acceptance_approved')


if __name__ == '__main__':
    unittest.main()
