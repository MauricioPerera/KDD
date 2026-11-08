"""The manifest hashes exact committed bytes, including binary and CRLF data."""
import hashlib
import json
import sys
import unittest

from tests.quality_review_fixture import QualityReviewFixture, ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
import quality_baseline
from verify_quality import oracle_equal


class QualityManifestBytesTests(QualityReviewFixture, unittest.TestCase):
    def manifest(self, reference):
        return quality_baseline.build_baseline(self.root, 'quality.json', reference)

    def assert_distinct(self, first, second):
        entries = []
        for value in (first, second):
            (self.root / 'data.bin').write_bytes(value)
            reference = self.commit('exact blob identity')
            entry = self.manifest(reference)['protected']['data.bin']
            self.assertEqual(entry['bytes'], len(value))
            self.assertEqual(set(entry), {'bytes', 'sha256'})
            entries.append(entry)
        self.assertNotEqual(entries[0]['sha256'], entries[1]['sha256'])
        self.assertEqual(entries[0]['sha256'], hashlib.sha256(first).hexdigest())
        self.assertEqual(entries[1]['sha256'], hashlib.sha256(second).hexdigest())

    def test_same_size_nul_binaries_keep_distinct_hashes(self):
        first, second = b'\x00\rDATA', b'\x00\nDATA'
        self.assertFalse(oracle_equal(first, second))
        self.assert_distinct(first, second)

    def test_non_utf8_binary_without_nul_is_not_normalized(self):
        self.assert_distinct(b'\xff\rDATA', b'\xff\nDATA')

    def test_committed_text_crlf_is_exact_blob_identity(self):
        first, second = b'line\r\n', b'line\n'
        self.assertTrue(oracle_equal(first, second))
        self.assert_distinct(first, second)

    def test_policy_hash_identifies_original_crlf_json(self):
        policy = json.loads((self.root / 'quality.json').read_bytes())
        raw = (json.dumps(policy, indent=2).replace('\n', '\r\n') + '\r\n').encode()
        (self.root / 'quality.json').write_bytes(raw)
        reference = self.commit('approved JSON bytes with CRLF')
        manifest = self.manifest(reference)
        self.assertEqual(manifest['policy_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest['approved_ref'], reference)

    def test_local_edits_do_not_replace_approved_binary_bytes(self):
        expected = hashlib.sha256(self.originals['data.bin']).hexdigest()
        (self.root / 'data.bin').write_bytes(b'\x00unreviewed local edit')
        before = self.snapshot()
        result = self.manifest(self.approved)
        self.assertEqual(result['protected']['data.bin']['sha256'], expected)
        self.assertEqual(self.snapshot(), before)

    def test_api_and_cli_preserve_schema_for_empty_and_utf8_blobs(self):
        for raw in (b'', 'texto con \u00f1\n'.encode('utf-8')):
            with self.subTest(raw=raw):
                (self.root / 'data.bin').write_bytes(raw)
                reference = self.commit('empty or UTF-8 approved bytes')
                manifest = self.manifest(reference)
                result = self.cli('quality_baseline.py', reference=reference)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout), manifest)
                self.assertEqual(set(manifest), {'approved_ref', 'policy', 'policy_sha256', 'protected'})
                self.assertEqual(manifest['protected']['data.bin'],
                    {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})


if __name__ == '__main__':
    unittest.main()
