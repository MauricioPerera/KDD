"""Real reviewed counterexamples at product approval, in temporary Git repos."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from tests import test_mutation_control_evidence as support
from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('mutation_audit.py', 'audit_seals.py', 'validate_contracts.py', 'process_tree.py')
MUTANT = 'def accept(value):\n return value in (1, 2)\n'
CASE = 'tests.test_app.TestApp.test_value'


def sha(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


class QualityOracleReviews(unittest.TestCase):
    def setUp(self):
        self.root, self.contract, self.area = support.MutationControls.project(self)
        self.git('init', '-q', '-b', 'main')
        configure_git(self.root, {'user.name': 'Synthetic reviewer',
            'user.email': 'reviewer@example.invalid', 'core.autocrlf': 'false'}, ephemeral=True)
        for module in MODULES:
            path = self.root / 'scripts' / module
            path.parent.mkdir(exist_ok=True)
            shutil.copyfile(ROOT / 'scripts' / module, path)
        self.write('quality/mutants/accepts-two.py', MUTANT)
        self.write('.gitignore', '__pycache__/\n*.pyc\n')
        self.write('quality/checks.py', "from pathlib import Path\np=Path('checks.txt')\np.write_text((p.read_text() if p.exists() else '')+'check\\n')\n")
        self.entry = {'contract': 'knowledge/contracts/app.md',
            'risk': 'Reject acceptance of a non-one integer', 'structural': 'python-ast',
            'timeout': 5, 'mutants': [{'id': 'accepts-two',
            'source': 'quality/mutants/accepts-two.py', 'expected_tests': [CASE]}]}
        self.policy = {'protected': ['tests/test_app.py', 'tests/__init__.py',
            'knowledge/contracts/app.md', 'quality/mutants/accepts-two.py',
            'quality/checks.py'] + ['scripts/' + name for name in MODULES],
            'implementation': ['src/app.py'], 'pm': ['checks.txt'],
            'required_kinds': ['functional', 'adversarial'], 'checks': [
            {'name': 'functional', 'kind': 'functional',
             'argv': [sys.executable, 'quality/checks.py'], 'timeout': 5},
            {'name': 'adversarial', 'kind': 'adversarial',
             'argv': [sys.executable, 'quality/checks.py'], 'timeout': 5}],
            'oracle_reviews': [self.entry]}
        self.freeze()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
            stderr=subprocess.PIPE, text=True).strip()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def freeze(self):
        self.write('quality/product.json', json.dumps(self.policy, indent=2) + '\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'Synthetic independent approval before product checks')
        self.ref = self.git('rev-parse', 'HEAD')

    def oracle(self, source):
        self.write('tests/test_app.py', source)
        text = self.contract.read_text(encoding='utf-8')
        self.contract.write_text(text.replace(sha(support.STRONG), sha(source)), encoding='utf-8')

    def run_gate(self):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/verify_quality.py'),
            '--repo-root', str(self.root), '--policy', 'quality/product.json',
            '--approved-ref', self.ref], capture_output=True, text=True,
            encoding='utf-8', timeout=45)

    def rejected(self, code):
        before = self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(code, result.stdout + result.stderr,
            'the declared control must run, rather than fail on an unknown policy field')
        self.assertFalse((self.root / 'checks.txt').exists(), 'ordinary checks ran after a failed oracle precondition')
        self.assertEqual((self.git('rev-parse', 'HEAD'), self.git('status', '--porcelain')), before)
        return result

    def test_declared_counterexample_is_detected_twice_with_exact_evidence(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = [json.loads(line.removeprefix('ORACLE_REVIEW '))
            for line in result.stdout.splitlines() if line.startswith('ORACLE_REVIEW ')]
        self.assertEqual(len(reports), 2)
        for number, report in enumerate(reports, 1):
            self.assertEqual(report['iteration'], number)
            self.assertEqual(report['approved_ref'], self.ref)
            self.assertEqual(report['contract_sha256'], sha(self.contract.read_text(encoding='utf-8')))
            self.assertEqual(report['risk'], self.entry['risk'])
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(report['structural']['method'], 'python-ast')
            self.assertEqual(report['structural']['findings'], [])
            self.assertEqual([row['status'] for row in report['controls']], ['PASS', 'PASS'])
            mutant = report['mutants'][0]
            self.assertEqual(mutant['id'], 'accepts-two')
            self.assertEqual(mutant['source'], MUTANT)
            self.assertEqual(mutant['mutant_sha256'], sha(MUTANT))
            self.assertEqual(mutant['target_sha256'], sha(support.TARGET))
            self.assertEqual(mutant['oracle_sha256'], sha(support.STRONG))
            self.assertEqual(mutant['failed_tests'], [CASE])
            self.assertEqual(mutant['status'], 'DETECTED')
            self.assertIn('AssertionError', mutant['stderr'])
            self.assertEqual(mutant['output_sha256'], sha(mutant['stdout'] + mutant['stderr']))
        self.assertEqual((self.root / 'checks.txt').read_text().splitlines(), ['check'] * 4)

    def test_required_structural_absence_blocks_before_any_oracle_execution(self):
        marker = self.area / 'should-not-run.txt'
        oracle = (f'from pathlib import Path\nPath({str(marker)!r}).write_text("ran")\n'
            'import unittest\nfrom src.app import accept\nclass TestApp(unittest.TestCase):\n'
            ' def test_value(self):assert True\n')
        self.oracle(oracle)
        self.freeze()
        self.rejected('ORACLE_STRUCTURE')
        self.assertFalse(marker.exists())

    def test_required_unsupported_structure_is_not_reported_as_pass(self):
        self.entry['structural'] = 'typescript-ast'
        self.freeze()
        self.rejected('ORACLE_UNSUPPORTED')

    def test_surviving_reviewed_counterexample_blocks_approval(self):
        self.write('quality/mutants/accepts-two.py', support.TARGET)
        self.freeze()
        self.rejected('ORACLE_SURVIVED')

    def test_unexpected_test_failure_is_inconclusive(self):
        self.entry['mutants'][0]['expected_tests'] = ['tests.test_app.TestApp.test_other_risk']
        self.freeze()
        self.rejected('ORACLE_INCONCLUSIVE')

    def test_mutant_import_failure_after_healthy_controls_is_inconclusive(self):
        self.write('quality/mutants/accepts-two.py', "import missing_reviewed_mutant_dependency\n" + MUTANT)
        self.freeze()
        self.rejected('ORACLE_INCONCLUSIVE')

    def test_broken_original_control_never_counts_as_detection(self):
        self.oracle('import missing_original_control_dependency\n' + support.STRONG)
        self.freeze()
        self.rejected('ORACLE_CONTROL')

    def test_unrelated_assertions_do_not_establish_risk_detection(self):
        self.oracle('import unittest\nfrom src.app import accept\nclass TestApp(unittest.TestCase):\n def test_value(self):self.assertEqual(2+2,4)\n')
        self.freeze()
        self.rejected('ORACLE_SURVIVED')

    def test_incomplete_contract_cannot_be_reviewed_as_valid(self):
        self.contract.write_text(self.contract.read_text(encoding='utf-8').replace(
            '## Examples', '## Removed examples'), encoding='utf-8')
        self.freeze()
        self.rejected('ORACLE_CONTRACT')

    def test_unsupported_command_is_rejected_before_execution(self):
        self.contract.write_text(self.contract.read_text(encoding='utf-8').replace(
            'python -m unittest tests/test_app.py', 'pytest tests/test_app.py'), encoding='utf-8')
        self.freeze()
        self.rejected('ORACLE_UNSUPPORTED')

    def test_duplicate_counterexample_id_is_rejected(self):
        self.entry['mutants'].append(dict(self.entry['mutants'][0]))
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_review_side_effect_cannot_hide_a_frozen_source_change(self):
        path = self.root / 'quality/mutants/accepts-two.py'
        prefix = ('from pathlib import Path\n'
            "if Path.cwd().name.startswith('mutant-'):\n"
            f' Path({str(path)!r}).write_text({support.TARGET!r})\n')
        self.oracle(prefix + support.STRONG)
        self.freeze()
        result = self.run_gate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Protected file changed', result.stdout + result.stderr)
        self.assertFalse((self.root / 'checks.txt').exists())
        # The runner blocks approval; arbitrary hostile side effects have no rollback guarantee.

    def test_empty_required_review_list_is_rejected(self):
        self.policy['oracle_reviews'] = []
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_missing_reviewed_mutants_is_rejected(self):
        self.entry['mutants'] = []
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_expected_test_identity_is_required(self):
        self.entry['mutants'][0]['expected_tests'] = []
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_mutant_source_must_be_frozen_in_protected(self):
        self.policy['protected'].remove('quality/mutants/accepts-two.py')
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_review_runner_must_be_frozen_in_protected(self):
        self.policy['protected'].remove('scripts/mutation_audit.py')
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_contract_and_oracle_must_be_frozen_in_protected(self):
        self.policy['protected'].remove('tests/test_app.py')
        self.freeze()
        self.rejected('ORACLE_POLICY')

    def test_altered_frozen_mutant_is_rejected_by_integrity(self):
        self.write('quality/mutants/accepts-two.py', support.TARGET)
        self.rejected('Protected file changed')

    def test_legacy_policy_still_runs_checks_without_claiming_oracle_assurance(self):
        del self.policy['oracle_reviews']
        self.freeze()
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('ORACLE_REVIEW ', result.stdout)
        self.assertIn('oracle assurance not requested', result.stdout)
        self.assertEqual((self.root / 'checks.txt').read_text().splitlines(), ['check'] * 4)

    def test_existing_advisory_auditor_keeps_its_default_exit_semantics(self):
        self.oracle('import unittest\nfrom src.app import accept\nclass TestApp(unittest.TestCase):\n def test_value(self):assert True\n')
        base = [sys.executable, str(ROOT / 'scripts/audit_seals.py'),
            str(self.root / 'knowledge/contracts'), '--repo-root', str(self.root)]
        advisory = subprocess.run(base, capture_output=True, text=True, timeout=10)
        strict = subprocess.run(base + ['--strict'], capture_output=True, text=True, timeout=10)
        self.assertEqual(advisory.returncode, 0)
        self.assertEqual(strict.returncode, 1)
        self.assertIn('WEAK_NO_ASSERTS', advisory.stdout)


if __name__ == '__main__':
    unittest.main()
