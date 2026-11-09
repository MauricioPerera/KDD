"""Exercise the ODD route with real Git objects and the baseline review CLI."""
import json
import subprocess
import sys
import unittest

from tests.test_baseline_risk_review import ROOT, ReviewFixture


class OddLightweightTests(ReviewFixture, unittest.TestCase):
    def cli(self, *options, candidate=None, base=None):
        return subprocess.run(
            [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/baseline_review.py'),
             '--repo-root', str(self.root), '--base-ref', base or self.base,
             '--candidate-ref', candidate or self.head, *options],
            capture_output=True, encoding='utf-8', timeout=60)

    def classify(self, route, reason, *, candidate=None, confirm=True):
        flags = ['--small-change'] + (['--editorial-only'] if confirm else [])
        result = self.cli(*flags, candidate=candidate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report['route'], report['reason']), (route, reason))
        self.assertEqual(report['base_commit'], self.base)
        self.assertEqual(report['candidate_commit'], candidate or self.head)
        self.assertIs(report['review_ready'], False)
        self.assertNotIn('approved_ref', report)
        return report

    def test_existing_readme_edit_has_exact_evidence_and_no_side_effects(self):
        self.candidate({'README.md': '# A real project\n\nAn editorial correction.\n'})
        tree = self.git('rev-parse', self.head + '^{tree}')
        (self.root / 'src/app.py').write_bytes(b'Unstaged unrelated content\n')
        (self.root / 'README.md').write_bytes(b'Unstaged README bytes\n')
        before = self.snapshot()
        report = self.classify('lightweight', 'editorial_only')
        self.assertEqual(report['candidate_tree'], tree)
        self.assertEqual(report['risk_floor'], 'low')
        self.assertEqual([row['path'] for row in report['changes']], ['README.md'])
        self.assertEqual(self.snapshot(), before)

    def test_existing_nested_guide_is_eligible(self):
        path = 'docs/guides/getting-started/guide.md'
        self.base = self.candidate({path: '# A guide\n'})
        self.candidate({path: '# An existing guide\n'})
        self.classify('lightweight', 'editorial_only')

    def test_explicit_confirmation_is_required(self):
        self.candidate()
        self.classify('standard', 'confirmation_required', confirm=False)

    def test_code_mixed_with_docs_is_not_eligible(self):
        self.candidate({'README.md': '# Editorial\n', 'src/app.py': 'VALUE = 2\n'})
        report = self.classify('standard', 'outside_scope')
        self.assertEqual(report['risk_floor'], 'medium')
        self.assertEqual([row['path'] for row in report['changes']],
                         ['README.md', 'src/app.py'])

    def test_contract_oracle_policy_and_workflow_are_outside_the_route(self):
        changes = {
            'knowledge/contracts/existing.md': '# Weakened contract\n',
            'tests/oracle.py': 'assert True\n',
            'quality.json': '{}\n',
            '.github/workflows/validate.yml': 'jobs: {}\n',
        }
        for path, content in changes.items():
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.candidate({'README.md': '# Editorial\n', path: content})
                report = self.classify('standard', 'outside_scope')
                self.assertEqual(report['risk_floor'], 'high')

    def test_existing_evidence_and_hidden_guide_are_outside_the_route(self):
        evidence = 'docs/reports/evidence.md'
        hidden = 'docs/guides/.internal/guide.md'
        self.base = self.candidate({evidence: '# Evidence\n', hidden: '# Internal\n'})
        for path in (evidence, hidden):
            with self.subTest(path=path):
                self.git('reset', '--hard', self.base)
                self.candidate({path: '# Changed text\n'})
                self.classify('standard', 'outside_scope')

    def test_add_delete_and_rename_are_outside_the_route(self):
        guide = 'docs/guides/readme.md'
        for changes in ({guide: '# New\n'}, {'README.md': None},
                        {'README.md': None, guide: '# A real project\n'}):
            with self.subTest(changes=changes):
                self.git('reset', '--hard', self.base)
                self.candidate(changes)
                self.classify('standard', 'outside_scope')

    def test_mode_changes_and_symlink_objects_are_outside_the_route(self):
        blob = self.git('rev-parse', self.base + ':README.md')
        for mode in ('100755', '120000'):
            with self.subTest(mode=mode):
                self.git('reset', '--hard', self.base)
                self.git('update-index', '--cacheinfo', mode + ',' + blob + ',README.md')
                self.git('commit', '-qm', 'Change only the committed file mode')
                self.head = self.git('rev-parse', 'HEAD')
                report = self.classify('standard', 'outside_scope')
                self.assertEqual(report['changes'][0]['after']['mode'], mode)

    def test_intermediate_code_change_cannot_be_hidden_by_restoring_it(self):
        self.candidate({'src/app.py': 'VALUE = 9\n'})
        self.candidate({'README.md': '# Editorial\n', 'src/app.py': 'VALUE = 1\n'})
        report = self.classify('standard', 'history')
        self.assertEqual([row['path'] for row in report['changes']], ['README.md'])

    def test_merge_with_base_as_first_parent_requires_standard_flow(self):
        self.git('switch', '-c', 'side')
        self.git('commit', '--allow-empty', '-qm', 'Second parent')
        self.git('switch', '-')
        self.base = self.candidate()
        self.git('merge', '--no-ff', '-qm', 'Merge the side branch', 'side')
        self.head = self.git('rev-parse', 'HEAD')
        self.classify('standard', 'history')

    def test_empty_commit_requires_standard_flow(self):
        self.git('commit', '--allow-empty', '-qm', 'Empty candidate')
        self.head = self.git('rev-parse', 'HEAD')
        self.classify('standard', 'empty_change')

    def test_replacement_commit_cannot_hide_changed_code(self):
        unsafe = self.candidate({'src/app.py': 'VALUE = 9\n'})
        self.git('switch', '--detach', self.base)
        safe = self.candidate()
        self.git('replace', unsafe, safe)
        self.assertEqual(self.git('show', '-s', '--format=%T', unsafe),
                         self.git('show', '-s', '--format=%T', safe))
        report = self.classify('standard', 'outside_scope', candidate=unsafe)
        self.assertEqual([row['path'] for row in report['changes']], ['src/app.py'])

    def test_invalid_git_identities_do_not_classify(self):
        self.candidate()
        for base, candidate, code in (('HEAD', self.head, 'REVIEW_REF'),
                (self.base, 'HEAD', 'REVIEW_REF'),
                (self.head, self.base, 'REVIEW_HISTORY')):
            with self.subTest(base=base, candidate=candidate):
                result = self.cli('--small-change', '--editorial-only',
                                  base=base, candidate=candidate)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(code, result.stderr)

    def test_mode_arguments_are_exclusive(self):
        self.candidate()
        for options, message in (
                (('--editorial-only',), 'requires --small-change'),
                (('--small-change', '--review', 'unused.json'), 'not allowed')):
            with self.subTest(options=options):
                result = self.cli(*options)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(message, result.stderr)

    def test_existing_review_remains_separate_from_classification(self):
        self.candidate()
        review = self.owner / 'review.json'
        review.write_text(json.dumps(self.receipt()), encoding='utf-8')
        result = self.cli('--review', str(review))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertIs(report['review_ready'], True)
        self.assertNotIn('route', report)
        self.assertNotIn('approved_ref', report)


if __name__ == '__main__':
    unittest.main()
