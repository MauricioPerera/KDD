"""Quality approval and its manifest must read original real Git objects."""
import hashlib
import json
import sys
import unittest

from tests.quality_review_fixture import QualityReviewFixture, ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
import quality_baseline
import verify_quality


class QualityApprovedObjectsTests(QualityReviewFixture, unittest.TestCase):
    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('PASS quality:', result.stdout)

    def test_reviewed_project_passes_and_wrong_product_is_rejected(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RUN 2/2 adversarial', result.stdout)
        self.assertIn('PASS quality:', result.stdout)
        (self.root / 'product.txt').write_bytes(b'BAD\n')
        self.assert_rejected(self.cli())

    def test_commit_replacement_cannot_authorize_changed_oracles(self):
        candidate = self.weaken()
        self.assert_rejected(self.cli())
        self.git('replace', self.approved, candidate)
        self.assert_rejected(self.cli())

    def test_blob_replacements_cannot_authorize_changed_oracles(self):
        candidate = self.weaken()
        for name in ('functional.py', 'adversarial.py'):
            original = self.git('rev-parse', self.approved + ':' + name)
            altered = self.git('rev-parse', candidate + ':' + name)
            self.git('replace', original, altered)
        self.assert_rejected(self.cli())

    def test_batch_reader_returns_original_blobs(self):
        original = self.git('rev-parse', self.approved + ':functional.py')
        altered = self.git('hash-object', '-w', '--stdin', data=b'not the reviewed bytes\n')
        self.git('replace', original, altered)
        values = verify_quality._objects(self.root, [self.approved + ':functional.py', original])
        self.assertEqual(values[self.approved + ':functional.py'], self.originals['functional.py'])
        self.assertEqual(values[original], self.originals['functional.py'])

    def test_manifest_commit_and_blob_replacements_keep_reviewed_hashes(self):
        candidate = self.weaken()
        expected = hashlib.sha256(self.originals['functional.py']).hexdigest()
        for kind in ('commit', 'blob'):
            with self.subTest(kind=kind):
                original = self.approved if kind == 'commit' else self.git('rev-parse', self.approved + ':functional.py')
                altered = candidate if kind == 'commit' else self.git('rev-parse', candidate + ':functional.py')
                self.git('replace', original, altered)
                try:
                    manifest = quality_baseline.build_baseline(self.root, 'quality.json', self.approved)
                    self.assertEqual(manifest['approved_ref'], self.approved)
                    self.assertEqual(manifest['protected']['functional.py']['sha256'], expected)
                finally:
                    self.git('replace', '-d', original)

    def test_unreviewed_process_helper_is_never_imported(self):
        marker = self.area / 'unreviewed-helper.txt'
        helper = self.root / 'scripts/process_tree.py'
        helper.write_bytes(helper.read_bytes() + ("\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").write_bytes(b'unreviewed')\n").encode())
        candidate = self.commit('unreviewed helper side effect')
        self.git('replace', self.approved, candidate)
        result = self.cli()
        self.assertFalse(marker.exists(), result.stdout + result.stderr)
        self.assert_rejected(result)

    def test_check_cannot_hide_an_outside_perimeter_commit(self):
        script = ("from pathlib import Path\nimport subprocess\n"
            "def git(*args): return subprocess.check_output(['git', *args]).decode().strip()\n"
            "assert Path('product.txt').read_bytes() == b'GOOD\\n'\n"
            "if not Path('outside.txt').exists():\n"
            "    approved = git('rev-parse', 'HEAD')\n"
            "    Path('outside.txt').write_bytes(b'outside approved perimeter')\n"
            "    git('add', 'outside.txt')\n"
            "    git('commit', '-qm', 'unapproved side effect')\n"
            "    git('replace', approved, git('rev-parse', 'HEAD'))\n")
        (self.root / 'functional.py').write_bytes(script.encode())
        reviewed = self.commit('reviewed adversarial side-effect control')
        result = self.cli(reference=reviewed)
        self.assertTrue((self.root / 'outside.txt').is_file(), result.stdout + result.stderr)
        self.assert_rejected(result)

    def test_custom_namespace_cannot_override_manifest_objects(self):
        candidate = self.weaken()
        self.git('update-ref', 'refs/quality-review/' + self.approved, candidate)
        result = self.cli('quality_baseline.py', extra_env={
            'GIT_REPLACE_REF_BASE': 'refs/quality-review/'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest['protected']['functional.py']['sha256'],
            hashlib.sha256(self.originals['functional.py']).hexdigest())

    def test_reads_leave_replacement_refs_and_repository_unchanged(self):
        original = self.git('rev-parse', self.approved + ':functional.py')
        altered = self.git('hash-object', '-w', '--stdin', data=b'harmless replacement control\n')
        self.git('replace', original, altered)
        before = self.snapshot()
        manifest = quality_baseline.build_baseline(self.root, 'quality.json', self.approved)
        self.assertEqual(manifest['approved_ref'], self.approved)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
