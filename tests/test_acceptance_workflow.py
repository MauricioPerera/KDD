"""Exercise the actual CI Python block without dispatching a remote workflow."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class AcceptanceWorkflow(unittest.TestCase):
    def code(self):
        path = Path(__file__).resolve().parents[1] / '.github/workflows/validate.yml'
        text = path.read_text(encoding='utf-8')
        block = text.split('      - name: Verify required contract acceptance\n', 1)[1]
        block = block.split('      - name: Upload acceptance matrix\n', 1)[0]
        return compile(textwrap.dedent(block.split('        run: |\n', 1)[1]), str(path), 'exec')

    def environment(self, required=False):
        return {'KDD_ACCEPTANCE_POLICY': 'absent-acceptance-test-policy.json',
                'KDD_ACCEPTANCE_REQUIRED': 'true' if required else 'false',
                'KDD_ACCEPTANCE_APPROVED_REF': 'a' * 40, 'RUNNER_TEMP': '.'}

    def test_deleted_approved_policy_and_required_absence_are_not_skip(self):
        for exists_in_baseline, required in ((True, False), (False, True)):
            with self.subTest(approved=exists_in_baseline, required=required):
                with patch.dict(os.environ, self.environment(required)), \
                     patch('subprocess.run', return_value=SimpleNamespace(
                         returncode=0 if exists_in_baseline else 1)), \
                     patch('subprocess.call', return_value=37) as call:
                    with self.assertRaises(SystemExit) as error:
                        exec(self.code(), {})
                    self.assertEqual(error.exception.code, 37)
                    command = call.call_args.args[0]
                    self.assertEqual(command[:2], [sys.executable, 'scripts/verify_acceptance.py'])
                    self.assertIn('a' * 40, command)
                    self.assertIn('absent-acceptance-test-policy.json', command)

    def test_legacy_absence_reports_not_evaluated(self):
        output = io.StringIO()
        with patch.dict(os.environ, self.environment()), \
             patch('subprocess.run', return_value=SimpleNamespace(returncode=1)), \
             patch('subprocess.call') as call, redirect_stdout(output):
            exec(self.code(), {})
        call.assert_not_called()
        self.assertIn('NOT_EVALUATED', output.getvalue())


if __name__ == '__main__':
    unittest.main()
