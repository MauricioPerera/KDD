"""An independently completed CI run is required before project closure."""

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_completion_runs as verifier  # noqa: E402


REPO = 'ExampleCo/Shop'
RUN_ID = 12345
RUN_URL = 'https://github.com/{}/actions/runs/{}'.format(REPO, RUN_ID)
SHA = 'a' * 40


def _evidence():
    return {'ci': {'run_url': RUN_URL, 'head_sha': SHA}}


def _run(**changes):
    result = {
        'id': RUN_ID,
        'html_url': RUN_URL,
        'repository': {'full_name': REPO},
        'head_sha': SHA,
        'status': 'completed',
        'conclusion': 'success',
        'name': 'validate-contracts',
        'path': '.github/workflows/validate.yml@refs/heads/main',
    }
    result.update(changes)
    return result


def _rules(evidence=None, run=None, current_run_id=99999):
    return {item['rule'] for item in verifier.verify_run(
        evidence or _evidence(), REPO, current_run_id,
        lambda repository, run_id: run or _run())}


class VerifyCompletionRunsTests(unittest.TestCase):
    def test_completed_successful_matching_run_passes(self):
        self.assertEqual(_rules(), set())

    def test_running_or_failed_run_cannot_certify_closure(self):
        self.assertIn('CI_RUN_NOT_SUCCESS', _rules(run=_run(status='in_progress',
                                                           conclusion=None)))
        self.assertIn('CI_RUN_NOT_SUCCESS', _rules(run=_run(conclusion='failure')))

    def test_sha_repository_and_url_must_match(self):
        self.assertIn('CI_RUN_SHA', _rules(run=_run(head_sha='b' * 40)))
        self.assertIn('CI_RUN_REPOSITORY', _rules(run=_run(
            repository={'full_name': 'Other/Repo'})))
        self.assertIn('CI_RUN_URL', _rules(run=_run(html_url='https://example.com/run')))

    def test_only_the_validation_workflow_can_certify(self):
        self.assertIn('CI_RUN_WORKFLOW', _rules(run=_run(name='unrelated')))
        self.assertIn('CI_RUN_WORKFLOW', _rules(run=_run(
            path='.github/workflows/other.yml@refs/heads/main')))

    def test_current_run_cannot_certify_itself(self):
        self.assertIn('CI_RUN_SELF', _rules(current_run_id=RUN_ID))

    def test_lookup_failure_is_not_a_pass(self):
        def denied(repository, run_id):
            raise OSError('API unavailable')

        findings = verifier.verify_run(_evidence(), REPO, 99999, denied)
        self.assertIn('CI_RUN_LOOKUP', {item['rule'] for item in findings})

    def test_only_closure_artifacts_may_change_after_verified_sha(self):
        allowed = [
            'specs/CONTRACT-34-example.md',
            'docs/reports/CONTRACT-34-REPORT.md',
            'docs/reports/CONTRACT-34-EVIDENCE.json',
            'CHANGELOG.md',
        ]
        self.assertEqual(verifier.verify_closure_diff(allowed), [])
        findings = verifier.verify_closure_diff(allowed + ['src/payment.py'])
        self.assertIn('CI_SOURCE_DRIFT', {item['rule'] for item in findings})


if __name__ == '__main__':
    unittest.main()
