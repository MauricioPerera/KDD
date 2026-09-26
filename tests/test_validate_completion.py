"""Regression cases for project-level spec/report completion evidence."""

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_completion as vc  # noqa: E402


SPEC = 'specs/CONTRACT-34-example.md'
REPORT = 'docs/reports/CONTRACT-34-REPORT.md'
EVIDENCE = 'docs/reports/CONTRACT-34-EVIDENCE.json'
RUN = 'https://github.com/MauricioPerera/KDD/actions/runs/12345'


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def _fixture(root, pending=False, evidence=True):
    spec = (
        '# Contract\n\n## Criterios de aceptación\n\n'
        '- [{}] [AC-1] `python -m unittest` verde.\n'
        '- [x] [CI-1] CI en ambos sistemas.\n\n## Restricciones\n\n'
    ).format(' ' if pending else 'x')
    _write(root, SPEC, spec)
    _write(root, REPORT, '# Report\n\nSpec: `{}`\n\nCI: {}\n\n'
           '## Pendientes\n\nNinguno.\n'.format(SPEC, RUN))
    data = {
        'schema_version': 1, 'spec': SPEC, 'state': 'verified_in_ci',
        'ci': {'run_url': RUN, 'head_sha': 'a' * 40},
        'criteria': {
            'AC-1': {'status': 'locally_verified', 'evidence': 'test log 1'},
            'CI-1': {'status': 'verified_in_ci', 'evidence': RUN},
        },
    }
    if evidence:
        _write(root, EVIDENCE, json.dumps(data))
    _write(root, 'completion-legacy.json', json.dumps({
        'schema_version': 1, 'repository': 'MauricioPerera/KDD',
        'legacy_pairs': {},
    }))
    return data


def _rules(root):
    return {item['rule'] for item in vc.validate_completion(str(root))}


class CompletionTests(unittest.TestCase):
    def test_real_historical_pairs_are_explicit_skips(self):
        findings, counts = vc._audit(str(ROOT), 'completion-legacy.json')
        self.assertEqual(findings, [])
        policy = json.loads((ROOT / 'completion-legacy.json').read_text(encoding='utf-8'))
        if policy['repository'] == 'MauricioPerera/KDD':
            self.assertEqual(len(policy['legacy_pairs']), 33)
            self.assertEqual(counts, {'PASS': 0, 'FAIL': 0, 'SKIP': 33})
        else:
            self.assertEqual(policy['legacy_pairs'], {})
            self.assertEqual(list((ROOT / 'specs').glob('CONTRACT-[0-9]*.md')), [])
            self.assertEqual(list((ROOT / 'docs/reports').glob('CONTRACT-[0-9]*-REPORT.md')), [])
            self.assertEqual(counts, {'PASS': 0, 'FAIL': 0, 'SKIP': 0})

    def test_new_complete_pair_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root)
            self.assertEqual(vc.validate_completion(str(root)), [])

    def test_consumer_without_legacy_policy_is_still_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root, pending=True)
            (root / 'completion-legacy.json').unlink()
            findings = vc.validate_completion(str(root), repository='MauricioPerera/KDD')
            self.assertIn('CRITERION_PENDING', {item['rule'] for item in findings})
            self.assertIn('POLICY', {item['rule'] for item in vc.validate_completion(str(root))})

    def test_policy_repository_must_match_ci_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root)
            findings = vc.validate_completion(str(root), repository='another/repo')
            self.assertIn('POLICY_REPOSITORY', {item['rule'] for item in findings})

    def test_open_specs_without_reports_do_not_claim_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root, SPEC, '# Still open\n')
            self.assertEqual(vc.validate_completion(str(root), repository='owner/repo'), [])

    def test_report_cannot_close_unchecked_criterion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root, pending=True)
            self.assertIn('CRITERION_PENDING', _rules(root))

    def test_missing_evidence_does_not_count_as_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root, evidence=False)
            self.assertIn('EVIDENCE_MISSING', _rules(root))

    def test_evidence_ids_must_match_spec_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = _fixture(root)
            data['criteria']['EXTRA'] = data['criteria'].pop('AC-1')
            _write(root, EVIDENCE, json.dumps(data))
            self.assertIn('EVIDENCE_CRITERIA', _rules(root))

    def test_ci_criterion_must_reference_same_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = _fixture(root)
            data['criteria']['CI-1']['evidence'] = 'local log only'
            _write(root, EVIDENCE, json.dumps(data))
            self.assertIn('CI_CRITERION_EVIDENCE', _rules(root))

    def test_run_and_sha_must_be_reviewable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = _fixture(root)
            data['ci'] = {'run_url': 'https://example.com/actions/runs/1',
                          'head_sha': 'HEAD'}
            _write(root, EVIDENCE, json.dumps(data))
            self.assertTrue({'CI_RUN_URL', 'CI_HEAD_SHA'} <= _rules(root))

    def test_report_must_reference_same_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root)
            _write(root, REPORT, '# Report\n\nSpec: `{}`\n\nNinguno.\n'.format(SPEC))
            self.assertIn('REPORT_EVIDENCE', _rules(root))

    def test_orphan_report_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root)
            (root / SPEC).unlink()
            self.assertIn('PAIR_MISSING', _rules(root))

    def test_legacy_pair_never_becomes_pass_and_edit_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _fixture(root)
            spec, report = root / SPEC, root / REPORT
            digest = vc._legacy_digest(spec, report)
            policy = json.loads((root / 'completion-legacy.json').read_text())
            policy['legacy_pairs']['CONTRACT-34'] = digest
            _write(root, 'completion-legacy.json', json.dumps(policy))
            findings, counts = vc._audit(str(root), 'completion-legacy.json')
            self.assertEqual(findings, [])
            self.assertEqual(counts['SKIP'], 1)
            _write(root, REPORT, report.read_text() + '\nchanged\n')
            self.assertIn('LEGACY_DRIFT', _rules(root))


if __name__ == '__main__':
    unittest.main()
