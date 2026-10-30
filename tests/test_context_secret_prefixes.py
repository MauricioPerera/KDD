"""Keep real prefix guards while admitting ordinary task contract names."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import assemble_context as assembler


def policy():
    return json.loads((ROOT / 'ccdd/context.json').read_text(encoding='utf-8'))


def runtime_policy():
    config = copy.deepcopy(policy())
    config['slots'] = [{'id': 'input', 'source': 'runtime', 'priority': 0}]
    return config


class ContextSecretPrefixes(unittest.TestCase):
    def test_ordinary_contract_names_are_not_credentials(self):
        for text in ('knowledge/contracts/task-worktree-integration.md',
                     'task-worktree-integration', 'multitask-coordination-documentation'):
            with self.subTest(text=text):
                try:
                    result = assembler.assemble(runtime_policy(), text, str(ROOT))
                except assembler.GuardrailAbort as error:
                    self.fail('Ordinary contract name incorrectly rejected: ' + str(error))
                self.assertTrue(result['guardrails']['ok'])

    def test_real_cli_can_assemble_the_new_contract_context(self):
        result = subprocess.run([sys.executable, 'scripts/assemble_context.py',
                                 'ccdd/context.json', 'revisar task-worktree-integration'],
                                cwd=ROOT, capture_output=True, text=True,
                                encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('guardrails: ok', result.stdout)
        self.assertIn('task-worktree-integration', result.stdout)

    def test_synthetic_credential_prefixes_still_abort(self):
        for prefix in ('sk-', 'sk-proj-', 'sk-svcacct-'):
            with self.subTest(prefix=prefix), self.assertRaises(assembler.GuardrailAbort):
                assembler.assemble(runtime_policy(), prefix + 'A' * 32, str(ROOT))

    def test_delimiters_do_not_hide_a_credential(self):
        for start, end in (('', ''), (' ', '\n'), ('"', '"'), ("'", "'"),
                           ('=', ''), ('/', ''), ('_', '')):
            value = start + 'sk-' + 'A' * 32 + end
            with self.subTest(start=start), self.assertRaises(assembler.GuardrailAbort):
                assembler.assemble(runtime_policy(), value, str(ROOT))

    def test_other_rules_budgets_slots_and_abort_policy_are_unchanged(self):
        config = policy()
        config['guardrails']['regex_deny']['patterns'][9] = '<reviewed-prefix-pattern>'
        digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest, '8a197ab6cad91ab42fc355bd987c8798201337802638d0ea2321fe76fa532066')


if __name__ == '__main__':
    unittest.main()
