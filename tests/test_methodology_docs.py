"""Keep operational instructions aligned with runnable examples."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_documentation_examples import verify_documentation_examples

ROOT = Path(__file__).resolve().parents[1]


class DocumentationExamples(unittest.TestCase):
    def test_documented_quickstart_runs_red_then_green_with_real_oracle(self):
        result = verify_documentation_examples(ROOT)
        self.assertTrue(result['ok'], result)
        self.assertFalse(result['stub']['ok'])
        self.assertTrue(result['implemented']['ok'])
        self.assertEqual(result['implemented']['executed_tests'], 2)
        self.assertEqual(result['contract_findings'], [])

    def test_skill_uses_canonical_template_and_no_rejected_budget_example(self):
        text = (ROOT / '.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('TEMPLATE-task-contract.md', text)
        self.assertNotIn('max_cyclomatic_complexity:', text)
        self.assertNotIn('a1b2c3d4e5f6...', text)

    def test_prerequisites_and_limits_are_explicit(self):
        quickstart = (ROOT / 'knowledge/quickstart.md').read_text(encoding='utf-8')
        self.assertIn('Python 3.11+', quickstart)
        self.assertIn('Node.js 24', quickstart)
        self.assertIn('requirements-change-audit.txt', quickstart)
        self.assertIn('npm ci --ignore-scripts', quickstart)
        self.assertNotIn('no de KDD', quickstart)
        for name in ('metodologia-ejecucion.md', 'validacion.md'):
            text = (ROOT / 'knowledge' / name).read_text(encoding='utf-8')
            self.assertNotIn('≈ sin flaky', text)
        human = (ROOT / 'knowledge/supervision-humana.md').read_text(encoding='utf-8')
        self.assertNotIn('verifican que el codigo cumple EL CONTRATO', human)


if __name__ == '__main__':
    unittest.main()
