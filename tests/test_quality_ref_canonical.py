"""Real native Git objects and local quality APIs/CLIs, with execution canaries."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests.test_fixture_preparation import configure_git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_quality as quality
import quality_baseline as baseline


class QualityRefCanonical(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd quality oid ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            self.env.pop(key, None)
        self.prepare('sha1')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
            stderr=subprocess.PIPE, env=self.env, text=True, encoding='utf-8').strip()

    def prepare(self, algorithm):
        self.git('init', '-q', '-b', 'main', '--object-format=' + algorithm)
        configure_git(self.root, {'user.name': 'Synthetic quality reviewer',
            'user.email': 'fixture@example.invalid', 'commit.gpgsign': 'false',
            'maintenance.autoDetach': 'false', 'gc.autoDetach': 'false'}, ephemeral=True)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/process_tree.py', self.root / 'scripts/process_tree.py')
        (self.root / '.gitignore').write_text('.check-count\n__pycache__/\n')
        (self.root / 'oracle.py').write_text(
            'from pathlib import Path\np=Path(".check-count")\n'
            'p.write_text(p.read_text()+"x" if p.exists() else "x")\n', encoding='utf-8')
        (self.root / 'app.py').write_text('value = 1\n')
        policy = dict(protected=['oracle.py'], implementation=['app.py'], pm=[],
            required_kinds=['functional', 'adversarial'], checks=[
                dict(name='functional', kind='functional', argv=[sys.executable, '-I', 'oracle.py'], timeout=10),
                dict(name='adversarial', kind='adversarial', argv=[sys.executable, '-I', '-c', 'assert 1+1 == 2'], timeout=10)])
        (self.root / 'quality.json').write_text(json.dumps(policy), encoding='utf-8')
        self.git('add', '.'); self.git('commit', '-qm', 'Synthetic reviewed baseline')
        self.approved = self.git('rev-parse', 'HEAD')
        self.git('branch', 'reviewed-quality', self.approved)
        self.git('tag', 'lightweight', self.approved)
        self.git('tag', '-a', 'annotated', '-m', 'Own annotated object', self.approved)

    def cli(self, script, reference):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script),
            '--repo-root', str(self.root), '--policy', 'quality.json', '--approved-ref', reference],
            cwd=self.root, env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=45)

    def unchanged(self):
        return (self.git('rev-parse', 'HEAD'), self.git('for-each-ref', '--format=%(refname) %(objectname)'),
                self.git('ls-files', '--stage'), self.git('status', '--porcelain'),
                (self.root / 'oracle.py').read_bytes(), (self.root / 'quality.json').read_bytes())

    def reject_cli(self, reference):
        before = self.unchanged()
        for script in ('verify_quality.py', 'quality_baseline.py'):
            with self.subTest(script=script, reference=reference):
                result = self.cli(script, reference)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('REJECT', result.stderr)
                self.assertNotIn('PASS quality:', result.stdout)
                self.assertFalse((self.root / '.check-count').exists())
                self.assertEqual(self.unchanged(), before)

    def test_canonical_sha1_cli_runs_quality_twice(self):
        (self.root / 'app.py').write_text('value = 2\n')
        result = self.cli('verify_quality.py', self.approved)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / '.check-count').read_text(), 'xx')
        self.assertIn('PASS quality:', result.stdout)
        result = self.cli('quality_baseline.py', self.approved)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['approved_ref'], self.approved)

    def test_canonical_sha1_apis_preserve_identity(self):
        original = self.unchanged()
        manifest = baseline.build_baseline(self.root, 'quality.json', self.approved)
        self.assertEqual(manifest['approved_ref'], self.approved)
        with redirect_stdout(io.StringIO()):
            quality.approve(self.root, 'quality.json', self.approved)
        self.assertEqual((self.root / '.check-count').read_text(), 'xx')
        self.assertEqual(self.unchanged(), original)

    def test_head_is_not_an_approval(self):
        self.reject_cli('HEAD')

    def test_head_commit_expression_is_not_an_approval(self):
        self.reject_cli('HEAD^0')

    def test_head_tilde_expression_is_not_an_approval(self):
        self.reject_cli('HEAD~0')

    def test_current_branch_is_not_an_approval(self):
        self.reject_cli('refs/heads/main')

    def test_named_review_branch_is_not_an_approval(self):
        self.reject_cli('reviewed-quality')

    def test_full_review_branch_is_not_an_approval(self):
        self.reject_cli('refs/heads/reviewed-quality')

    def test_lightweight_tag_is_not_an_approval(self):
        self.reject_cli('lightweight')

    def test_annotated_tag_name_is_not_an_approval(self):
        self.reject_cli('annotated')

    def test_annotated_tag_oid_is_not_a_commit_approval(self):
        self.reject_cli(self.git('rev-parse', 'refs/tags/annotated'))

    def test_abbreviated_commit_is_not_an_approval(self):
        self.reject_cli(self.approved[:12])

    def test_tree_oid_is_not_a_commit_approval(self):
        self.reject_cli(self.git('rev-parse', 'HEAD^{tree}'))

    def test_blob_oid_is_not_a_commit_approval(self):
        self.reject_cli(self.git('rev-parse', 'HEAD:oracle.py'))

    def test_other_format_hexadecimal_branch_is_not_an_approval(self):
        foreign = 'a' * 64
        self.git('branch', foreign, self.approved)
        self.reject_cli(foreign)

    def test_api_rejects_aliases_before_executing_checks(self):
        for reference in ('HEAD^0', 'refs/heads/reviewed-quality', self.approved[:12],
                          self.git('rev-parse', 'refs/tags/annotated')):
            with self.subTest(reference=reference):
                with self.assertRaises(quality.Rejected):
                    baseline.build_baseline(self.root, 'quality.json', reference)
                with self.assertRaises(quality.Rejected), redirect_stdout(io.StringIO()):
                    quality.approve(self.root, 'quality.json', reference)
                self.assertFalse((self.root / '.check-count').exists())

    def test_moved_alias_never_reapproves_a_changed_oracle(self):
        (self.root / 'oracle.py').write_text('raise SystemExit(0)\n')
        self.git('add', 'oracle.py'); self.git('commit', '-qm', 'Candidate changes protected oracle')
        self.git('branch', '-f', 'reviewed-quality', 'HEAD')
        original = self.cli('verify_quality.py', self.approved)
        self.assertNotEqual(original.returncode, 0)
        self.assertIn('Protected file changed', original.stderr)
        self.reject_cli('refs/heads/reviewed-quality')

    def test_canonical_sha256_and_foreign_length_branch(self):
        self.root = self.root / 'native sha256'; self.root.mkdir()
        self.prepare('sha256')
        self.assertEqual(len(self.approved), 64)
        result = self.cli('verify_quality.py', self.approved)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / '.check-count').read_text(), 'xx')
        (self.root / '.check-count').unlink()
        manifest = baseline.build_baseline(self.root, 'quality.json', self.approved)
        self.assertEqual(manifest['approved_ref'], self.approved)
        foreign = 'b' * 40; self.git('branch', foreign, self.approved)
        self.reject_cli(foreign)


if __name__ == '__main__':
    unittest.main()
