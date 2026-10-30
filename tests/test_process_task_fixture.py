"""Real task-oracle startup, exit causes and uncontained survivors."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'kdd_task_timeout_fixture', ROOT / 'tests/test_process_tree_timeout.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ProcessTaskFixture(unittest.TestCase):
    def run_case(self, mode):
        class Scenario(fixture.ProcessTreeTimeout):
            def tree(self, *args, **kwargs):
                parent, body = super().tree(*args, **kwargs)
                if mode == 'slow':
                    body = 'import time\ntime.sleep(6.0)\n' + body
                elif mode == 'exit':
                    body = body.replace('time.sleep(25)', 'sys.exit(7)')
                elif mode == 'import':
                    # This import really fails inside the recognized unittest command.
                    body = 'import kdd_missing_task_fixture_module\n' + body
                elif mode == 'no_tree':
                    body = 'import time\ntime.sleep(25)\n'
                parent.write_text(body, encoding='utf-8')
                return parent, body

            def module(self, name):
                module = super().module(name)
                if mode == 'uncontained' and name == 'task_evidence':
                    # Deliberately broken containment, with actual subprocesses.
                    module.subprocess = SimpleNamespace(
                        run=subprocess.run, DEVNULL=subprocess.DEVNULL,
                        SubprocessError=subprocess.SubprocessError)
                return module

        case = Scenario('test_task_oracle_timeout_cleans_descendants')
        stream = io.StringIO()
        # Match the scripts entry point used by the actual task executor.
        previous = list(sys.path)
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(case)
        finally:
            sys.path[:] = previous
        self.assertEqual(result.testsRun, 1, stream.getvalue())
        self.assertEqual(result.errors, [], stream.getvalue())
        self.assertEqual(result.skipped, [], stream.getvalue())
        return result, stream.getvalue()

    def rejected(self, result, details):
        self.assertFalse(result.wasSuccessful(), details)
        self.assertEqual(len(result.failures), 1, details)
        return result.failures[0][1]

    def test_six_second_startup_reaches_real_tree_and_is_cancelled(self):
        result, details = self.run_case('slow')
        self.assertTrue(result.wasSuccessful(), details)

    def test_nonzero_exit_after_readiness_is_not_a_timeout(self):
        result, details = self.run_case('exit')
        failure = self.rejected(result, details)
        self.assertIn('Task oracle must fail because of TimeoutExpired', failure)
        self.assertNotIn('must observe real child', failure)
        self.assertNotIn('child survived the timeout', failure)

    def test_real_import_failure_reports_startup_and_adapter_error(self):
        result, details = self.run_case('import')
        failure = self.rejected(result, details)
        self.assertIn('must observe real child', failure)
        self.assertIn('missing=', failure)
        self.assertIn('child.ready', failure)
        self.assertIn('grand.ready', failure)
        self.assertIn('tree.ready', failure)
        self.assertIn('kdd_missing_task_fixture_module', failure)
        self.assertIn('TASK_TESTS', failure)

    def test_real_timeout_without_descendants_is_inconclusive(self):
        result, details = self.run_case('no_tree')
        failure = self.rejected(result, details)
        self.assertIn('must observe real child', failure)
        self.assertIn('missing=', failure)
        self.assertIn('elapsed=', failure)
        self.assertIn('timeout=15.0', failure)
        self.assertIn('TASK_TESTS', failure)
        self.assertNotIn('child survived the timeout', failure)

    def test_uncontained_task_is_rejected_for_real_late_write(self):
        result, details = self.run_case('uncontained')
        failure = self.rejected(result, details)
        self.assertIn('child survived the timeout', failure)
        self.assertNotIn('must observe real child', failure)


if __name__ == '__main__':
    unittest.main()
