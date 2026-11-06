"""Real filesystem and CLI regression oracle for skill-validator complexity."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_skills as skills


def content(name, desc='Description that is longer than fifty characters for a real skill.', body='Instructions.\n'):
    return "---\nname: " + name + "\ndescription: " + desc + "\n---\n" + body


class SkillsBudget(unittest.TestCase):
    def test_existing_budget_applies_to_every_function(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_budgets.py'),
            str(ROOT / 'knowledge/contracts'), '--repo-root', str(ROOT), '--contract', 'skills-gate'],
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SkillsIntegration(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='skills budget integration ')
        self.addCleanup(self.area.cleanup)
        self.root = Path(self.area.name)
        self.first = self.root / 'first skills'
        self.second = self.root / 'other skills'
        self.first.mkdir(); self.second.mkdir()

    def put(self, parent, folder, text):
        path = parent / folder / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
        return path

    def cli(self, *dirs):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/validate_skills.py'),
            *map(str, dirs)], capture_output=True, text=True, encoding='utf-8', timeout=30,
            env=dict(os.environ, PYTHONUTF8='1'))

    def test_valid_cli_is_deterministic_and_does_not_write(self):
        path = self.put(self.first, 'alpha', content('alpha', body='Instruccion con acento: accion.\n'))
        before = path.read_bytes()
        a, b = self.cli(self.first), self.cli(self.first)
        self.assertEqual((a.returncode, a.stdout, a.stderr), (b.returncode, b.stdout, b.stderr))
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        self.assertIn('0 error(es) en 1 skill(s)', a.stdout)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_directories_are_info_and_exit_zero(self):
        missing = self.root / 'missing'
        result = self.cli(missing)
        self.assertEqual(result.returncode, 0)
        self.assertIn('[DIR_MISSING]', result.stdout)
        self.assertIn('0 error(es) en 0 skill(s)', result.stdout)

    def test_duplicates_across_directories_are_stable(self):
        self.put(self.first, 'same', content('same'))
        self.put(self.second, 'same', content('same'))
        actual = skills.validate_skills([str(self.first), str(self.second)])
        duplicates = [f for f in actual if f['rule'] == 'NAME_DUP']
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(actual, sorted(actual, key=lambda f: (f['file'], f['rule'])))
        result = self.cli(self.first, self.second)
        self.assertEqual(result.returncode, 1)
        self.assertIn('[NAME_DUP]', result.stdout)
        self.assertIn('1 error(es) en 2 skill(s)', result.stdout)

    def test_description_boundaries_and_empty_body(self):
        self.put(self.first, 'short', content('short', desc='x' * 49))
        self.put(self.first, 'exact', content('exact', desc='y' * 50))
        self.put(self.first, 'empty', content('empty', body=''))
        findings = skills.validate_skills([str(self.first)])
        pairs = {(Path(f['file']).parts[-2], f['rule']) for f in findings}
        self.assertIn(('short', 'FM_DESC_LEN'), pairs)
        self.assertIn(('empty', 'BODY_EMPTY'), pairs)
        self.assertFalse(any(folder == 'exact' for folder, _ in pairs))

    def test_only_real_unresolved_links_are_reported(self):
        body = '[broken](missing.md) ` [hidden](ignored.md) `\n```md\n[hidden](missing2.md)\n```\n[web](https://example.invalid/)\n'
        self.put(self.first, 'links', content('links', body=body))
        findings = skills.validate_skills([str(self.first)])
        links = [f for f in findings if f['rule'] == 'LINK_BROKEN']
        self.assertEqual(len(links), 1)
        self.assertIn('missing.md', links[0]['msg'])

    def test_missing_frontmatter_does_not_emit_other_errors(self):
        self.put(self.first, 'malformed', '# no frontmatter\n')
        findings = skills.validate_skills([str(self.first)])
        self.assertEqual([f['rule'] for f in findings], ['FM_PARSE'])

    def test_missing_skill_file_and_top_level_file_handling(self):
        (self.first / 'empty').mkdir()
        (self.first / 'README.md').write_text('not a skill', encoding='utf-8')
        result = self.cli(self.first)
        self.assertEqual(result.returncode, 1)
        self.assertIn('[SKILL_MISSING]', result.stdout)
        self.assertIn('1 error(es) en 1 skill(s)', result.stdout)


if __name__ == '__main__':
    unittest.main()
