"""Real delayed startup, real uncontained negative control and early deadline."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kdd_fixture_oracle', ROOT / 'tests/test_process_tree_timeout.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ProcessFixtureStartup(unittest.TestCase):
    def delayed_case(self, uncontained=False):
        class Delayed(fixture.ProcessTreeTimeout):
            def tree(self, *args, **kwargs):
                parent, body = super().tree(*args, **kwargs)
                body = 'import time\ntime.sleep(2.0)\n' + body
                parent.write_text(body, encoding='utf-8')
                return parent, body

            def module(self, name):
                if uncontained and name == 'process_tree':
                    # Fault injection uses actual OS processes and the former
                    # uncontained stdlib behavior, never fake lifecycle results.
                    return SimpleNamespace(run=subprocess.run)
                return super().module(name)

        case = Delayed('test_direct_timeout_cancels_child_and_grandchild_with_detached_output')
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(case)
        return result, stream.getvalue()

    def test_delayed_real_tree_reaches_handshake_and_is_cancelled(self):
        result, details = self.delayed_case()
        self.assertEqual(result.testsRun, 1, details)
        self.assertTrue(result.wasSuccessful(), details)
        self.assertEqual(result.skipped, [], details)

    def test_uncontained_real_tree_is_rejected_for_late_write(self):
        result, details = self.delayed_case(uncontained=True)
        self.assertEqual(result.testsRun, 1, details)
        self.assertEqual(result.errors, [], details)
        self.assertEqual(len(result.failures), 1, details)
        self.assertIn('child survived the timeout', result.failures[0][1])
        self.assertNotIn('must observe real child', result.failures[0][1])

    def test_short_deadline_still_covers_target_startup(self):
        spec = importlib.util.spec_from_file_location('kdd_actual_timeout', ROOT / 'scripts/process_tree.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(prefix='kdd startup deadline ') as directory:
            root = Path(directory)
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.run([sys.executable, '-c', 'import time;from pathlib import Path;'
                            'time.sleep(2.5);Path("late").write_text("not cancelled")'],
                           cwd=root, timeout=1.5, capture_output=True)
            self.assertLess(time.monotonic() - started, 7.5)
            while time.monotonic() < started + 3.5:
                time.sleep(.05)
            self.assertFalse((root / 'late').exists())


if __name__ == '__main__':
    unittest.main()
