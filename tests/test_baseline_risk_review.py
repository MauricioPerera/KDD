"""Risk review integration with real commits, objects, processes and mutations."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import baseline_review as subject

LENSES = ('simplicity', 'oracle', 'implementation')


class ReviewFixture:
    @classmethod
    def setUpClass(cls):
        cls.seed_area = tempfile.TemporaryDirectory(prefix='kdd-review-seed-')
        cls.addClassCleanup(cls.seed_area.cleanup)
        cls.seed = Path(cls.seed_area.name) / 'seed'
        cls.seed.mkdir()
        cls.run_git(cls.seed, 'init', '-q', '-b', 'main')
        configure_git(cls.seed, {'user.name': 'Review Integration',
            'user.email': 'review@example.invalid', 'core.autocrlf': 'false',
            'commit.gpgsign': 'false'}, ephemeral=True)
        for name, data in {
            'README.md': '# A real project\n', 'src/app.py': 'VALUE = 1\n',
            'tests/oracle.py': 'assert 1 == 1\n',
            'knowledge/contracts/existing.md': '# Existing contract\n',
            'quality.json': json.dumps({'protected': ['tests/oracle.py'],
                'implementation': ['src/app.py'], 'pm': ['quality.json'],
                'required_kinds': ['functional', 'adversarial'],
                'checks': [{'name': kind, 'kind': kind, 'argv': ['python', '-V'],
                            'timeout': 10} for kind in ('functional', 'adversarial')]}),
            '.gitignore': '__pycache__/\n',
        }.items():
            target = cls.seed / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data, encoding='utf-8', newline='\n')
        cls.run_git(cls.seed, 'add', '-A')
        cls.run_git(cls.seed, 'commit', '-qm', 'independent base')
        cls.base = cls.run_git(cls.seed, 'rev-parse', 'HEAD')

    @staticmethod
    def run_git(root, *args):
        result = subprocess.run(['git', '-C', str(root), *args],
            capture_output=True, encoding='utf-8', timeout=30)
        if result.returncode:
            raise AssertionError('Real Git failed: ' + repr(args) + '\n' + result.stderr)
        return result.stdout.strip()

    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd review \u00f1 ')
        self.addCleanup(self.area.cleanup)
        self.owner = Path(self.area.name)
        self.root = self.owner / 'project'
        self.run_git(self.owner, 'clone', '-c', 'core.autocrlf=false', '--quiet', '--no-hardlinks', str(self.seed), str(self.root))
        configure_git(self.root, {'user.name': 'Review Integration',
            'user.email': 'review@example.invalid', 'core.autocrlf': 'false',
            'commit.gpgsign': 'false'}, ephemeral=True)
        self.changed = []

    def git(self, *args):
        return self.run_git(self.root, *args)

    def candidate(self, changes=None):
        changes = {'README.md': '# Defined goal and reuse\n'} if changes is None else changes
        self.changed = list(changes)
        for name, data in changes.items():
            path = self.root / name
            if data is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data.encode('utf-8') if isinstance(data, str) else data)
        self.git('add', '-A')
        self.git('commit', '-qm', 'candidate awaiting approval')
        self.head = self.git('rev-parse', 'HEAD')
        return self.head

    def receipt(self, risk='low', count=1, kind='agent'):
        reads = [{'revision': 'candidate' if (self.root / name).exists() else 'base',
                  'path': name} for name in self.changed]
        return {'schema_version': 1, 'base_commit': self.base,
            'candidate_commit': self.head, 'candidate_tree': self.git('rev-parse', self.head + '^{tree}'),
            'author': 'implementer', 'risk': risk, 'risk_rationale': 'Explicitly reviewed scope and failure modes.',
            'risk_factors': [], 'reviews': [
                {'id': 'review-' + str(i), 'reviewer': 'reader-' + str(i),
                 'kind': kind, 'fresh_context': True, 'status': 'completed',
                 'lenses': [{'name': lens, 'assessment': 'pass',
                            'rationale': 'Checked the committed source against the proposed obligation.'}
                            for lens in LENSES], 'read_set': copy.deepcopy(reads)}
                for i in range(count)], 'findings': []}

    def inspect(self, base=None, head=None):
        try:
            return subject.inspect_change(self.root, base or self.base, head or self.head)
        except subject.ReviewError as exc:
            self.fail('Expected a real Git inspection, received ' + str(exc))

    def verify(self, row, base=None, head=None):
        try:
            return subject.verify_review(self.root, base or self.base, head or self.head,
                row if isinstance(row, str) else json.dumps(row))
        except subject.ReviewError as exc:
            self.fail('Expected a review verdict, received ' + str(exc))

    def invalid(self, row, code='REVIEW_SCHEMA', base=None, head=None):
        with self.assertRaisesRegex(subject.ReviewError, code):
            subject.verify_review(self.root, base or self.base, head or self.head,
                row if isinstance(row, str) else json.dumps(row))

    def not_ready(self, row, code):
        result = self.verify(row)
        self.assertFalse(result['review_ready'], result)
        self.assertIn(code, [finding['code'] for finding in result['findings']], result)
        self.assertNotIn('approved_ref', result)

    def snapshot(self):
        paths = [p for p in self.root.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.root).parts]
        return (self.git('rev-parse', 'HEAD'), self.git('show-ref'),
            (self.root / '.git/index').read_bytes(), (self.root / '.git/config').read_bytes(),
            {p.relative_to(self.root).as_posix(): p.read_bytes() for p in paths})


class BaselineRiskReviewTests(ReviewFixture, unittest.TestCase):
    def test_clone_is_clean_under_global_autocrlf_and_preserves_base_bytes(self):
        config = self.owner / 'global.gitconfig'
        config.write_text('[core]\n\tautocrlf = true\n', encoding='utf-8')
        probe = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tests.test_baseline_risk_review import BaselineRiskReviewTests
cls = BaselineRiskReviewTests
cls.setUpClass()
case = cls('test_git_fixture_is_independent_and_has_real_committed_objects')
try:
    case.setUp()
    print(json.dumps({'status': case.git('status', '--porcelain=v1'),
                      'readme_hex': (case.root/'README.md').read_bytes().hex(),
                      'oracle_hex': (case.root/'tests/oracle.py').read_bytes().hex()}))
finally:
    case.doCleanups()
    cls.doClassCleanups()
'''
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe, str(ROOT)],
            capture_output=True, encoding='utf-8', timeout=90,
            env=dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['status'], '')
        self.assertEqual(bytes.fromhex(data['readme_hex']), b'# A real project\n')
        self.assertEqual(bytes.fromhex(data['oracle_hex']), b'assert 1 == 1\n')

    def test_git_fixture_is_independent_and_has_real_committed_objects(self):
        self.candidate()
        self.assertNotEqual(self.base, self.head)
        self.assertEqual(self.git('cat-file', '-t', self.head), 'commit')
        self.assertEqual(self.git('show', self.base + ':README.md'), '# A real project')
        self.assertEqual(self.git('status', '--porcelain=v1'), '')

    def test_low_document_review_is_bound_to_exact_commits_and_bytes(self):
        self.candidate()
        inspected = self.inspect()
        self.assertEqual(inspected['risk_floor'], 'low')
        self.assertFalse(inspected['review_ready'])
        self.assertEqual(inspected['base_commit'], self.base)
        self.assertEqual(inspected['candidate_commit'], self.head)
        self.assertEqual(inspected['candidate_tree'], self.git('rev-parse', self.head + '^{tree}'))
        self.assertEqual(inspected['changes'], [{'path': 'README.md',
            'before': {'mode': '100644', 'oid': self.git('rev-parse', self.base + ':README.md')},
            'after': {'mode': '100644', 'oid': self.git('rev-parse', self.head + ':README.md')}}])
        result = self.verify(self.receipt())
        self.assertTrue(result['review_ready'], result)
        self.assertEqual(result['required_reviewers'], 1)
        self.assertEqual(result['sources'][0]['sha256'], hashlib.sha256((self.root / 'README.md').read_bytes()).hexdigest())
        self.assertNotIn('approved_ref', result)

    def test_new_contract_and_oracle_need_medium_independent_review(self):
        self.candidate({'knowledge/contracts/new.md': '# New requirement\n', 'tests/new.py': 'assert True\n'})
        self.assertEqual(self.inspect()['risk_floor'], 'medium')
        row = self.receipt('medium')
        self.assertTrue(self.verify(row)['review_ready'])
        row['reviews'][0]['fresh_context'] = False
        self.not_ready(row, 'REVIEW_INDEPENDENCE')
        row['reviews'][0]['kind'] = 'human'
        self.assertTrue(self.verify(row)['review_ready'])

    def test_existing_oracles_and_contracts_cannot_disguise_their_risk(self):
        self.candidate({'tests/oracle.py': '# modified oracle\n', 'knowledge/contracts/existing.md': '# changed\n'})
        self.assertEqual(self.inspect()['risk_floor'], 'high')
        row = self.receipt('high', count=2)
        self.assertTrue(self.verify(row)['review_ready'])
        row['risk'] = 'medium'
        self.not_ready(row, 'RISK_TOO_LOW')

    def test_trust_paths_are_high_even_for_markdown_or_a_new_workflow(self):
        self.candidate({'.github/workflows/new.yml': 'name: reviewed\n',
                        '.agents/AGENTS.md': '# New instructions\n', 'quality/new.json': '{}\n'})
        self.assertEqual(self.inspect()['risk_floor'], 'high')
        self.assertTrue(self.verify(self.receipt('high', count=2))['review_ready'])
        self.not_ready(self.receipt('low'), 'RISK_TOO_LOW')

    def test_declared_factors_can_raise_but_never_lower_the_path_floor(self):
        self.candidate()
        for factor, level in [('api', 'medium'), ('performance', 'medium'), ('dependencies', 'medium'),
                              ('security', 'high'), ('data-loss', 'high'), ('concurrency', 'high'), ('trust-boundary', 'high')]:
            with self.subTest(factor=factor):
                row = self.receipt(level, count=2)
                row['risk_factors'] = [factor]
                self.assertEqual(self.verify(row)['risk_floor'], level)
                row['risk'] = 'low'
                self.not_ready(row, 'RISK_TOO_LOW')

    def test_author_aliases_and_unfinished_reviewers_do_not_count_as_independent(self):
        self.candidate({'src/app.py': 'VALUE = 2\n'})
        row = self.receipt('high', count=2)
        row['reviews'][1]['reviewer'] = 'implementer'
        self.not_ready(row, 'REVIEW_INDEPENDENCE')
        row['reviews'][1]['reviewer'] = 'reader-1'
        row['reviews'][1]['status'] = 'not_run'
        self.not_ready(row, 'REVIEW_INCOMPLETE')
        row['reviews'][1]['status'] = 'completed'
        row['reviews'][1]['fresh_context'] = False
        self.not_ready(row, 'REVIEW_INDEPENDENCE')

    def test_missing_or_blocked_perspectives_prevent_readiness(self):
        self.candidate()
        row = self.receipt()
        row['reviews'][0]['lenses'].pop()
        self.not_ready(row, 'LENS_MISSING')
        row = self.receipt()
        row['reviews'][0]['lenses'][0]['assessment'] = 'blocked'
        self.not_ready(row, 'LENS_BLOCKED')

    def test_deletion_and_rename_require_reading_the_original_and_new_paths(self):
        self.candidate({'tests/oracle.py': None, 'tests/renamed oracle.py': 'assert 1 == 1\n'})
        result = self.inspect()
        self.assertEqual(result['risk_floor'], 'high')
        self.assertEqual({item['path'] for item in result['changes']}, set(self.changed))
        row = self.receipt('high', count=2)
        self.assertTrue(self.verify(row)['review_ready'])
        for review in row['reviews']:
            review['read_set'] = [item for item in review['read_set'] if item['revision'] == 'candidate']
        self.not_ready(row, 'SOURCE_COVERAGE')

    def test_read_set_is_exact_and_cannot_escape_or_read_missing_sources(self):
        self.candidate()
        for source in [{'revision': 'candidate', 'path': '../outside.md'},
                       {'revision': 'working', 'path': 'README.md'},
                       {'revision': 'candidate', 'path': 'missing.md'},
                       {'revision': 'candidate', 'path': 'src'}]:
            with self.subTest(source=source):
                row = self.receipt()
                row['reviews'][0]['read_set'].append(source)
                self.invalid(row, 'REVIEW_SOURCE')

    def test_symbolic_objects_are_classified_high_and_never_followed(self):
        self.candidate()
        symbolic = self.owner / 'symbolic.txt'
        symbolic.write_bytes(b'../outside.md')
        blob = self.git('hash-object', '-w', str(symbolic))
        # Build the real symbolic Git mode without requiring OS symlink privileges.
        self.git('update-index', '--add', '--cacheinfo', '120000,' + blob + ',alias.md')
        self.git('commit', '-qm', 'symbolic source is not a readable regular source')
        self.head = self.git('rev-parse', 'HEAD')
        self.changed.append('alias.md')
        self.assertEqual(self.inspect()['risk_floor'], 'high')
        row = self.receipt('high', count=2)
        for review in row['reviews']:
            review['read_set'][-1]['revision'] = 'candidate'
        self.invalid(row, 'REVIEW_SOURCE')

    def test_receipt_for_another_commit_or_tree_is_rejected(self):
        self.candidate()
        for key, value in [('base_commit', self.head), ('candidate_commit', self.base),
                           ('candidate_tree', self.git('rev-parse', self.base + '^{tree}'))]:
            with self.subTest(key=key):
                row = self.receipt()
                row[key] = value
                self.invalid(row, 'REVIEW_IDENTITY')

    def test_ref_aliases_missing_objects_and_wrong_object_types_are_rejected(self):
        self.candidate()
        for ref in ['HEAD', self.head[:12], self.head.upper(), self.head + '^{commit}',
                    '0' * 40, self.git('rev-parse', self.head + ':README.md')]:
            with self.subTest(ref=ref):
                self.invalid(self.receipt(), 'REVIEW_REF', head=ref)

    def test_nonancestor_and_shallow_history_are_rejected_explicitly(self):
        self.candidate()
        self.invalid(self.receipt(), 'REVIEW_HISTORY', base=self.head, head=self.base)
        shallow = self.owner / 'shallow'
        self.run_git(self.owner, 'clone', '--quiet', '--depth=1', self.root.as_uri(), str(shallow))
        with self.assertRaisesRegex(subject.ReviewError, 'REVIEW_HISTORY'):
            subject.inspect_change(shallow, self.base, self.head)

    def test_checkout_edits_do_not_change_the_committed_sources_or_write_git(self):
        self.candidate()
        row = self.receipt()
        (self.root / 'README.md').write_bytes(b'not the reviewed bytes\n')
        (self.root / 'untracked.txt').write_bytes(b'keep this file')
        before = self.snapshot()
        result = self.verify(row)
        self.assertTrue(result['review_ready'], result)
        expected = hashlib.sha256(b'# Defined goal and reuse\n').hexdigest()
        self.assertEqual(result['sources'][0]['sha256'], expected)
        self.assertEqual(self.snapshot(), before)
        self.invalid('{', 'REVIEW_SCHEMA')
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_unknown_and_nonfinite_json_cannot_hide_an_incomplete_review(self):
        self.candidate()
        valid = self.receipt()
        mutations = ['{"schema_version":1,"schema_version":1}', '{',
                     json.dumps(dict(valid, unknown=True)), json.dumps(dict(valid, schema_version=True)),
                     json.dumps(dict(valid, risk_factors=['unknown'])), json.dumps(dict(valid, risk_rationale='  ')),
                     json.dumps(dict(valid, risk_factors=['api', 'api'])), json.dumps(dict(valid, risk_rationale=float('nan'))),
                     ' ' * 262145 + json.dumps(valid)]
        for raw in mutations:
            with self.subTest(raw=raw[:100]):
                self.invalid(raw, 'REVIEW_SCHEMA')
        for field in ('id', 'reviewer'):
            row = self.receipt('high', count=2)
            row['reviews'][1][field] = row['reviews'][0][field]
            self.invalid(row, 'REVIEW_SCHEMA')

    def test_major_and_blocker_open_findings_block_but_nits_do_not(self):
        self.candidate()
        row = self.receipt()
        row['findings'] = [{'id': 'issue-1', 'severity': 'nit', 'status': 'open',
            'scope': 'README.md', 'rationale': 'An optional wording improvement.',
            'decided_by': None, 'evidence': []}]
        self.assertTrue(self.verify(row)['review_ready'])
        for severity in ('major', 'blocker'):
            row['findings'][0]['severity'] = severity
            self.not_ready(row, 'OPEN_FINDING')

    def test_accepted_risk_needs_explicit_human_decision_and_committed_evidence(self):
        self.candidate()
        row = self.receipt()
        row['findings'] = [{'id': 'issue-1', 'severity': 'major', 'status': 'accepted',
            'scope': 'README.md', 'rationale': 'Owner accepts this documented limitation.',
            'decided_by': 'reader-0', 'evidence': [{'revision': 'candidate', 'path': 'README.md'}]}]
        self.not_ready(row, 'DECISION_INVALID')
        row['reviews'][0]['kind'] = 'human'
        self.assertTrue(self.verify(row)['review_ready'])
        row['findings'][0]['decided_by'] = 'implementer'
        self.not_ready(row, 'DECISION_INVALID')

    def test_fixed_and_contested_findings_need_a_completed_reviewer_and_evidence(self):
        self.candidate()
        row = self.receipt()
        row['findings'] = [{'id': 'issue-1', 'severity': 'major', 'status': 'fixed',
            'scope': 'README.md', 'rationale': 'Confirmed against the corrected committed wording.',
            'decided_by': 'reader-0', 'evidence': [{'revision': 'candidate', 'path': 'README.md'}]}]
        for status in ('fixed', 'contested'):
            row['findings'][0]['status'] = status
            self.assertTrue(self.verify(row)['review_ready'])
        row['findings'][0]['evidence'] = []
        self.not_ready(row, 'DECISION_INVALID')

    def test_candidate_programs_and_external_diff_are_never_executed(self):
        marker = self.owner / 'executed.txt'
        payload = 'from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\n'
        self.candidate({'README.md': '# Reviewed\n', 'src/app.py': payload})
        self.git('config', 'diff.external', str(self.root / 'src/app.py'))
        before = self.snapshot()
        result = self.verify(self.receipt('medium'))
        self.assertTrue(result['review_ready'], result)
        self.assertFalse(marker.exists())
        self.assertEqual(self.snapshot(), before)

    def test_git_replacement_does_not_substitute_the_reviewed_bytes(self):
        self.candidate()
        row = self.receipt()
        original = self.git('rev-parse', self.head + ':README.md')
        replacement_file = self.owner / 'replacement.txt'
        replacement_file.write_bytes(b'not the actual object')
        replacement = self.git('hash-object', '-w', str(replacement_file))
        self.git('replace', original, replacement)
        before = self.snapshot()
        result = self.verify(row)
        self.assertTrue(result['review_ready'], result)
        self.assertEqual(result['sources'][0]['oid'], original)
        self.assertEqual(result['sources'][0]['sha256'], hashlib.sha256(b'# Defined goal and reuse\n').hexdigest())
        self.assertEqual(self.snapshot(), before)

    def test_unicode_paths_and_native_sha256_commits_keep_their_exact_identity(self):
        root = self.owner / 'sha256'
        root.mkdir()
        self.run_git(root, 'init', '-q', '-b', 'main', '--object-format=sha256')
        configure_git(root, {'user.name': 'SHA256 Integration', 'user.email': 'sha256@example.invalid',
            'core.autocrlf': 'false', 'commit.gpgsign': 'false'}, ephemeral=True)
        (root / 'README.md').write_text('# Base\n', encoding='utf-8')
        self.run_git(root, 'add', '-A'); self.run_git(root, 'commit', '-qm', 'base')
        self.root, self.base = root, self.run_git(root, 'rev-parse', 'HEAD')
        name = 'docs/contrato \u00f1 y espacios.md'
        self.candidate({name: '# Unicode\n'})
        result = self.verify(self.receipt())
        self.assertTrue(result['review_ready'], result)
        self.assertEqual(len(result['candidate_commit']), 64)
        self.assertEqual(result['sources'][0]['path'], name)


if __name__ == '__main__':
    unittest.main()
