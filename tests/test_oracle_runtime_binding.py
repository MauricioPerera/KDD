"""Declared Python versions must match the instrumented interpreter."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from oracle_execution import execute_oracle


class RuntimeBinding(unittest.TestCase):
    def run_oracle(self, executable):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'oracle.py').write_text(
                'import unittest\nclass Oracle(unittest.TestCase):\n'
                ' def test_case(self): self.assertTrue(True)\n', encoding='utf-8')
            return execute_oracle({'tests': 'oracle.py', 'oracle_files': ['oracle.py'],
                                   'test_runner': 'python-unittest',
                                   'test_command': executable + ' -m unittest oracle.py'}, root)

    def test_mismatched_version_is_rejected(self):
        result = self.run_oracle('python3.' + str(sys.version_info.minor + 1))
        self.assertFalse(result['ok'])
        self.assertIn('version', result['error'])

    def test_matching_version_records_actual_invocation(self):
        result = self.run_oracle('python3.' + str(sys.version_info.minor))
        self.assertTrue(result['ok'], result)
        self.assertEqual(Path(result['instrumented_argv'][0]), Path(sys.executable))
        self.assertIn('unittest_oracle_runner.py', result['instrumented_argv'][5])
        self.assertEqual(result['runtime_version'], sys.version.split()[0])
