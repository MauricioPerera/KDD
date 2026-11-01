"""Real Git checks for separately reviewed changes to trusted CI files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import guard_pr_baseline as guard


class TrustedChangeReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd-trusted-review-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.old_cwd)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Reviewer')
        self.git('config', 'user.email', 'reviewer@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.write('knowledge/contracts/task.md', "---\ntype: 'Task Contract'\ntests: 'tests/task.py'\n---\n")
        self.write('tests/task.py', 'assert True\n')
        self.write('.github/workflows/validate.yml', 'name: old\n')
        self.base = self.commit()
        self.write('.github/workflows/validate.yml', 'name: reviewed\n')
        self.candidate = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.PIPE).decode('utf-8').strip()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'synthetic review')
        return self.git('rev-parse', 'HEAD')

    def entry(self, revision, path):
        output = self.git('ls-tree', revision, '--', path)
        if not output:
            return None
        header, found = output.split('\t', 1)
        mode, kind, oid = header.split()
        self.assertEqual((found, kind), (path, 'blob'))
        return {'mode': mode, 'oid': oid}

    def review(self):
        path = '.github/workflows/validate.yml'
        return {'schema_version': 1, 'base_commit': self.base,
                'candidate_tree': self.git('rev-parse', self.candidate + '^{tree}'),
                'files': [{'path': path, 'before': self.entry(self.base, path),
                           'after': self.entry(self.candidate, path)}]}

    def check(self, review, candidate=None):
        try:
            return guard.check(self.base, candidate or self.candidate, self.base,
                               reviewed_changes=review)
        except TypeError as exc:
            self.fail('external exact-change review is not implemented: ' + str(exc))

    def test_without_review_guard_remains_fail_closed(self):
        self.assertTrue(any('trusted gate file changed' in item
                            for item in guard.check(self.base, self.candidate, self.base)))

    def test_exact_external_review_allows_only_that_change(self):
        self.assertEqual(self.check(json.dumps(self.review())), [])

    def test_wrong_base_or_tree_cannot_authorize(self):
        for field in ('base_commit', 'candidate_tree'):
            with self.subTest(field=field):
                review = self.review()
                review[field] = '0' * 40
                self.assertTrue(self.check(json.dumps(review)))

    def test_changed_oid_and_mode_are_rejected(self):
        for field, value in (('oid', '0' * 40), ('mode', '100755')):
            with self.subTest(field=field):
                review = self.review()
                review['files'][0]['after'][field] = value
                self.assertTrue(self.check(json.dumps(review)))

    def test_unreviewed_additional_protected_file_blocks(self):
        self.write('scripts/validate_baseline.py', 'raise SystemExit(0)\n')
        later = self.commit()
        self.assertTrue(self.check(json.dumps(self.review()), later))

    def test_duplicate_json_keys_and_extra_fields_are_rejected(self):
        review = self.review()
        invalid = json.dumps(review)[:-1] + ', "schema_version": 1}'
        self.assertTrue(self.check(invalid))
        review['unreviewed'] = True
        self.assertTrue(self.check(json.dumps(review)))

    def test_oracle_drift_still_rejected_with_valid_review(self):
        self.write('tests/task.py', 'assert False\n')
        self.candidate = self.commit()
        result = self.check(json.dumps(self.review()))
        self.assertTrue(any('oracle differs' in item for item in result), result)

    def test_review_can_cover_a_real_deletion_without_allowing_extra_paths(self):
        (self.root / '.github/workflows/validate.yml').unlink()
        self.candidate = self.commit()
        review = self.review()
        self.assertIsNone(review['files'][0]['after'])
        self.assertEqual(self.check(json.dumps(review)), [])

    def test_cli_reads_external_review_and_fetches_real_proposed_merge(self):
        self.git('update-ref', 'refs/pull/42/merge', self.candidate)
        self.git('remote', 'add', 'origin', str(self.root))
        env = dict(os.environ, KDD_TRUSTED_CHANGE_REVIEW=json.dumps(self.review()),
                   PYTHONUTF8='1', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        command = [sys.executable, str(ROOT / 'scripts/guard_pr_baseline.py'), '--pr-number', '42',
                   '--base-ref', self.base, '--approved-ref', self.base]
        result = subprocess.run(command, cwd=self.root, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS:', result.stdout)
        env.pop('KDD_TRUSTED_CHANGE_REVIEW')
        result = subprocess.run(command, cwd=self.root, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('trusted gate file changed', result.stdout)

    def test_review_data_in_candidate_is_not_external_approval(self):
        self.write('.github/kdd-trusted-review.json', json.dumps(self.review()))
        candidate = self.commit()
        self.assertTrue(guard.check(self.base, candidate, self.base))


if __name__ == '__main__':
    unittest.main()
