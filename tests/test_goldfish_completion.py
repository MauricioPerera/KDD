"""A previous Actions result cannot certify a criterion added at closure."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_validate_completion as fixture
from tests.test_fixture_preparation import configure_git

import verify_completion_runs as verify  # noqa: E402


class CriterionClosure(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-closure-')
        self.addCleanup(area.cleanup)
        self.repo = Path(area.name)
        self.git('init', '-q', '-b', 'main')
        configure_git(self.repo, {'user.name': 'Closure fixture',
                                  'user.email': 'closure@example.invalid'}, ephemeral=True)
        self.data = fixture._fixture(self.repo)
        self.spec = self.repo / fixture.SPEC
        self.report = self.repo / fixture.REPORT
        self.evidence = self.repo / fixture.EVIDENCE
        self.tested_text = self.spec.read_text(encoding='utf-8').replace(
            ' verde.\n', ' verde.\n  The unit test must exercise an actual repository.\n')
        self.spec.write_text(self.tested_text.replace('[x]', '[ ]'), encoding='utf-8')
        self.report_text = self.report.read_text(encoding='utf-8')
        self.report.unlink()
        self.evidence.unlink()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       encoding='utf-8', timeout=30).strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def close(self, text, extra=False):
        tested = self.commit('Candidate executed by CI')
        self.spec.parent.mkdir(parents=True, exist_ok=True)
        self.spec.write_text(text, encoding='utf-8')
        report = self.report_text
        if extra:
            marker = '| CI-1 | verified_in_ci | ' + fixture.RUN + ' |'
            report = report.replace(marker, marker + '\n| AC-9 | verified_in_ci | ' + fixture.RUN + ' |')
            self.data['criteria']['AC-9'] = dict(status='verified_in_ci', evidence=fixture.RUN)
        self.report.write_text(report, encoding='utf-8')
        self.data['ci']['head_sha'] = tested
        self.evidence.write_text(json.dumps(self.data), encoding='utf-8')
        self.commit('Report previous CI results')
        return self.verify(tested)

    def verify(self, tested, base=None, expected_checks=1, expected_calls=1, candidate=None):
        candidate = candidate or self.git('rev-parse', 'HEAD')
        stale_api = dict(id=12345, html_url=fixture.RUN, head_sha=tested, status='completed',
                         conclusion='success', name='validate-contracts',
                         repository={'full_name': 'MauricioPerera/KDD'},
                         path='.github/workflows/validate.yml@refs/heads/main')
        context = dict(repository='MauricioPerera/KDD', current_run_id=99999,
                       base_sha=base or tested, candidate_sha=candidate,
                       workflow=dict(name='validate-contracts', path='.github/workflows/validate.yml'))
        with patch.object(verify, '_fetch_run', return_value=stale_api) as remote:
            findings, checked = verify.verify_project(self.repo, context, 'fixture-token')
        if expected_calls is not None:
            self.assertEqual(remote.call_count, expected_calls, findings)
        if expected_checks is not None:
            self.assertEqual(checked, expected_checks, findings)
        return {finding['rule'] for finding in findings}

    def test_closing_existing_checkboxes_keeps_ci_reference_valid(self):
        self.assertEqual(self.close(self.tested_text), set())
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_new_criterion_cannot_reuse_previous_run(self):
        additional = '- [x] [AC-9] Claim a check the prior run never saw.'
        changed = self.tested_text.replace('## Restricciones', additional + '\n\n## Restricciones')
        self.assertIn('CI_CRITERIA_DRIFT', self.close(changed, extra=True))

    def test_criterion_continuation_is_frozen(self):
        changed = self.tested_text.replace('an actual repository', 'a fake repository')
        self.assertIn('CI_CRITERIA_DRIFT', self.close(changed))

    def test_missing_prior_spec_is_not_evidence(self):
        self.spec.unlink()
        self.assertIn('CI_CRITERIA_DRIFT', self.close(self.tested_text))

    def test_ambiguous_prior_criteria_sections_are_rejected(self):
        with self.spec.open('a', encoding='utf-8') as stream:
            stream.write(self.tested_text[self.tested_text.index('## Criterios'):])
        self.assertIn('CI_CRITERIA_DRIFT', self.close(self.tested_text))

    def test_new_report_revalidates_the_unchanged_manifest(self):
        tested = self.commit('Candidate executed by CI')
        self.data['ci']['head_sha'] = tested
        self.evidence.write_text(json.dumps(self.data), encoding='utf-8')
        pending = self.commit('Stage the manifest before publishing the report')
        self.report.write_text(self.report_text, encoding='utf-8')
        self.spec.write_text(self.tested_text.replace('an actual repository', 'a fake repository'),
                             encoding='utf-8')
        self.commit('Publish a report with altered criteria')
        self.assertIn('CI_CRITERIA_DRIFT', self.verify(tested, base=pending))

    def test_editing_only_text_of_closed_spec_does_not_recite_the_old_run(self):
        self.assertEqual(self.close(self.tested_text), set())
        closed = self.git('rev-parse', 'HEAD')
        self.spec.write_text(self.tested_text.replace('an actual repository', 'a fake repository'),
                             encoding='utf-8')
        self.commit('Silently change a previously credited criterion')
        self.assertIn('CI_CRITERIA_DRIFT', self.verify(closed, expected_checks=0, expected_calls=0))

    def test_editing_only_noncriterion_text_preserves_existing_closure(self):
        self.assertEqual(self.close(self.tested_text), set())
        closed = self.git('rev-parse', 'HEAD')
        self.spec.write_text(self.tested_text.replace('# Contract', '# Updated title'), encoding='utf-8')
        self.commit('Edit title while leaving criteria unchanged')
        self.assertEqual(self.verify(closed, expected_checks=0, expected_calls=0), set())

    def test_dirty_spec_cannot_be_used_as_the_tested_candidate(self):
        self.assertEqual(self.close(self.tested_text), set())
        closed = self.git('rev-parse', 'HEAD')
        tested = self.git('rev-parse', 'HEAD^')
        self.spec.write_text(self.tested_text.replace('an actual repository', 'a fake repository'),
                             encoding='utf-8')
        status = self.git('status', '--porcelain')
        self.assertIn('CI_CRITERIA_DRIFT', self.verify(tested, expected_checks=None, expected_calls=None))
        self.assertEqual(self.git('rev-parse', 'HEAD'), closed)
        self.assertEqual(self.git('status', '--porcelain'), status)

    def test_explicit_candidate_is_checked_even_if_checkout_has_good_criteria(self):
        changed = self.tested_text.replace('an actual repository', 'a fake repository')
        self.close(changed)
        candidate = self.git('rev-parse', 'HEAD')
        tested = self.git('rev-parse', 'HEAD^')
        self.spec.write_text(self.tested_text, encoding='utf-8')
        checkout = self.commit('Checkout and explicit candidate differ')
        self.assertIn('CI_CRITERIA_DRIFT', self.verify(tested, candidate=candidate))
        self.assertEqual(self.git('rev-parse', 'HEAD'), checkout)

    def test_dirty_manifest_cannot_substitute_the_committed_run(self):
        self.assertEqual(self.close(self.tested_text), set())
        tested = self.git('rev-parse', 'HEAD^')
        signed_bytes = self.evidence.read_bytes()
        self.data['ci']['head_sha'] = '1' * 40
        self.evidence.write_text(json.dumps(self.data), encoding='utf-8')
        self.commit('Claim a different run head in the candidate')
        self.evidence.write_bytes(signed_bytes)
        candidate = self.git('rev-parse', 'HEAD')
        self.assertIn('CI_EVIDENCE', self.verify(tested, expected_checks=None, expected_calls=None))
        self.assertEqual(self.git('rev-parse', 'HEAD'), candidate)

    def test_renaming_source_to_report_cannot_bypass_source_perimeter(self):
        source = self.repo / 'product.py'
        source.write_text(self.report_text, encoding='utf-8')
        tested = self.commit('Candidate includes a product source path')
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.git('mv', 'product.py', fixture.REPORT)
        self.spec.write_text(self.tested_text, encoding='utf-8')
        self.data['ci']['head_sha'] = tested
        self.evidence.write_text(json.dumps(self.data), encoding='utf-8')
        self.commit('Disguise source removal as publication of the report')
        self.assertIn('CI_SOURCE_DRIFT', self.verify(tested))


if __name__ == '__main__':
    unittest.main()
