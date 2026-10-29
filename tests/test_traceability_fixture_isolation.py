"""A real task fixture must not import an unrelated installed src package."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_traceability_model as support


class TraceabilityFixtureIsolation(unittest.TestCase):
    def test_completed_task_with_competing_src_package(self):
        with tempfile.TemporaryDirectory(prefix='kdd-src-collision-') as folder:
            root = Path(folder)
            external = root / 'site'
            (external / 'src').mkdir(parents=True)
            (external / 'src' / '__init__.py').write_text('SENTINEL = 123\n', encoding='utf-8')
            bindir = root / 'bin'
            bindir.mkdir()
            if os.name == 'nt':
                bindir = Path(sys.executable).parent
            else:
                (bindir / 'python').symlink_to(sys.executable)
            path = str(bindir) + os.pathsep + os.environ.get('PATH', '')
            with patch.dict(os.environ, {'PYTHONPATH': str(external), 'PATH': path}):
                probe = subprocess.run([sys.executable, '-c', 'import src; print(src.SENTINEL)'],
                                       cwd=root, env=support.isolated_env(), capture_output=True,
                                       text=True, encoding='utf-8', timeout=30)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertEqual(probe.stdout.strip(), '123')
                project = root / 'project'
                refs = support.prepare_project(project)
                self.assertTrue((project / 'src' / '__init__.py').is_file())
                self.assertEqual(support.git(project, 'rev-parse', 'main'), refs['closed'])
                result = support.command(project, [sys.executable, 'scripts/traceability.py',
                    '--repo-root', str(project), '--ref', 'main', '--manifest',
                    'quality/traceability.json', '--require-verified'])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
