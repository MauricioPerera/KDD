"""Real filesystem and CLI coverage for OKF validator maintenance."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_okf as okf


def node(title='Example', node_type='Concept', tags="['small']", body=''):
    return ("---\ntype: '%s'\ntitle: '%s'\ndescription: 'example'\ntags: %s\n---\n%s\n"
            % (node_type, title, tags, body))


class ExistingBudget(unittest.TestCase):
    def test_okf_validator_respects_existing_budget(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_budgets.py'),
                                 str(ROOT / 'knowledge/contracts'), '--repo-root', str(ROOT),
                                 '--contract', 'validate-okf'], capture_output=True,
                                text=True, encoding='utf-8', timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class OkfIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd okf complexity ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'knowledge space'
        self.root.mkdir()

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8', newline='\n')
        return path

    def run_cli(self):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/validate_okf.py'), str(self.root)],
                              env=dict(os.environ, PYTHONUTF8='1'), capture_output=True, timeout=30)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_cli_valid_bundle_is_deterministic_and_read_only(self):
        self.put('index.md', '- [nodes](./nodes/)\n- [task](./task.md)\n')
        self.put('nodes/a.md', node(body='[task](../task.md)'))
        self.put('task.md', node('Task', 'Task', "['work']", '[a](./nodes/a.md)'))
        before = self.snapshot()
        self.assertEqual(okf.validate_okf(str(self.root)), [])
        first, second = self.run_cli(), self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn(b'0 error(es)', first.stdout)
        self.assertEqual(before, self.snapshot())

    def test_missing_index_and_unreachable_node_are_real_cli_errors(self):
        self.put('orphan.md', node())
        findings = okf.validate_okf(str(self.root))
        self.assertEqual([(f['file'], f['rule']) for f in findings],
                         [('index.md', 'INDEX'), ('orphan.md', 'ORPHAN')])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'[INDEX] index.md', result.stdout)
        self.assertIn(b'[ORPHAN] orphan.md', result.stdout)

    def test_directory_reachability_is_direct_and_not_transitive(self):
        self.put('index.md', '- [nodes](./nodes/)\n')
        self.put('nodes/a.md', node(body='[deep](./nested/deep.md)'))
        self.put('nodes/nested/deep.md', node())
        findings = okf.validate_okf(str(self.root))
        self.assertEqual([(f['file'], f['rule']) for f in findings],
                         [('nodes/nested/deep.md', 'ORPHAN')])
        self.assertIn(b'nodes/nested/deep.md', self.run_cli().stdout)

    def test_links_reject_missing_and_non_markdown_but_ignore_code_and_external(self):
        self.put('index.md', '- [node](./a.md)\n')
        self.put('notes.txt', 'not markdown')
        body = ('[missing](./gone.md) [other](./notes.txt) '
                '[outside](../outside.md) [web](https://example.invalid/)\n'
                '`[inline](./inline-missing.md)`\n```\n[fenced](./fenced-missing.md)\n```')
        self.put('a.md', node(body=body))
        links = [f for f in okf.validate_okf(str(self.root)) if f['rule'] == 'LINK']
        self.assertEqual(len(links), 2)
        self.assertTrue(any('gone.md' in f['msg'] for f in links))
        self.assertTrue(any('notes.txt' in f['msg'] and '.txt' in f['msg'] for f in links))
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b'inline-missing', result.stdout)
        self.assertNotIn(b'fenced-missing', result.stdout)

    def test_frontmatter_findings_are_ordered_and_specific(self):
        self.put('index.md', '- [node](./a.md)\n')
        self.put('a.md', "---\ntype: 'Invalid'\ntitle: ''\ntags: ['UPPER', '']\n---\n")
        findings = okf.validate_okf(str(self.root))
        self.assertEqual([f['rule'] for f in findings], ['FM_KEY', 'FM_KEY', 'TAGS', 'TAGS', 'TYPE'])
        messages = ' '.join(f['msg'] for f in findings)
        for expected in ('title', 'description', 'UPPER', 'tag vacio', 'Invalid'):
            self.assertIn(expected, messages)
        self.assertEqual(self.run_cli().returncode, 1)

    def test_nested_frontmatter_parses_and_real_cli_accepts_it(self):
        self.put('index.md', '- [node](./a.md)\n')
        text = ("\n---\ntype: 'Concept'\ntitle: 'O''Brien'\ndescription: \"a\"\n"
                "tags: ['small', 'tag,with,commas']\nmetadata:\n  nested:\n    value: 42\n---\nBody\n")
        self.put('a.md', text)
        parsed, body = okf.parse_frontmatter(text)
        self.assertEqual(parsed['title'], "O'Brien")
        self.assertEqual(parsed['tags'], ['small', 'tag,with,commas'])
        self.assertEqual(parsed['metadata']['nested']['value'], '42')
        self.assertEqual(body, 'Body')
        self.assertEqual(okf.validate_okf(str(self.root)), [])
        self.assertEqual(self.run_cli().returncode, 0)

    def test_changed_files_are_rechecked_without_caching(self):
        self.put('index.md', '- [node](./a.md)\n')
        path = self.put('a.md', node(body='[missing](./target.md)'))
        self.assertEqual(self.run_cli().returncode, 1)
        original = path.read_bytes()
        self.put('target.md', node())
        # Only index links grant reachability; link the repaired node explicitly.
        self.put('index.md', '- [node](./a.md)\n- [target](./target.md)\n')
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), original)

    def test_nonexistent_directory_is_rejected_by_api_and_cli(self):
        self.root.rmdir()
        findings = okf.validate_okf(str(self.root))
        self.assertEqual([f['rule'] for f in findings], ['IO'])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'no existe el directorio', result.stdout)


if __name__ == '__main__':
    unittest.main()
