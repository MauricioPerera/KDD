import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_security_findings as security


class SealedScanIntegration(unittest.TestCase):
    def test_valid_package_is_read_only_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            findings = {'documentType': 'codex-security.findings', 'schemaVersion': '1.0', 'scanId': 'fixture', 'findings': []}
            coverage = {'documentType': 'codex-security.coverage', 'schemaVersion': '1.0', 'scanId': 'fixture',
                        'mode': 'repository', 'completeness': 'partial', 'inventoryStrategy': 'repository',
                        'includePaths': [], 'excludePaths': [], 'surfaces': [], 'explicitExclusions': [], 'deferred': []}
            artifacts = []
            for name, data in [('findings.json', findings), ('coverage.json', coverage)]:
                raw = json.dumps(data).encode()
                (root / name).write_bytes(raw)
                artifacts.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'mediaType': 'application/json'})
            stamp = '2026-09-05T00:00:00Z'
            manifest = {'documentType': 'codex-security.scan-manifest', 'schemaVersion': '1.0', 'scan': {
                'id': 'fixture', 'producer': {'name': 'test-fixture', 'version': '1'}, 'status': 'completed',
                'startedAt': stamp, 'completedAt': stamp, 'sealedAt': stamp,
                'target': {'kind': 'git_revision', 'targetId': 'fixture', 'displayName': 'Fixture', 'revision': 'a' * 40},
                'scope': {'includePaths': [], 'excludePaths': []}, 'coverageRef': 'coverage.json', 'findingsRef': 'findings.json',
                'artifacts': artifacts}}
            (root / 'scan-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            before = {f.name: f.read_bytes() for f in root.iterdir()}
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = security.main([str(root), '--required'])
            self.assertEqual(code, 0, out.getvalue())
            self.assertEqual(before, {f.name: f.read_bytes() for f in root.iterdir()})
            (root / 'coverage.json').write_text('{}', encoding='utf-8')
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                self.assertEqual(security.main([str(root)]), 2)


if __name__ == '__main__':
    unittest.main()
