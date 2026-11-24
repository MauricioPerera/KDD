"""Real Git and CLI controls for source dependencies and rename endpoints."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = 'knowledge/contracts/fixture.md'
PACKAGE = 'fixture-tools'


class ChangeAuditIntegration(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='kdd-change-endpoints-')
        self.addCleanup(area.cleanup)
        self.root = Path(area.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_CONFIG')}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                        GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
                        PYTHONUTF8='1')
        self.git('init', '-q', '-b', 'main')

    def run_process(self, command):
        return subprocess.run(command, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding='utf-8', timeout=45)

    def git(self, *args):
        result = self.run_process(['git', '-c', 'commit.gpgsign=false', '-c', 'core.autocrlf=false', *args])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
        return path

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'Fixture state')
        return self.git('rev-parse', 'HEAD')

    def contract(self, target, language, allowed_paths, dependencies=()):
        oracle = 'import unittest\nclass Fixture(unittest.TestCase):\n    def test_value(self): self.assertEqual(1, 1)\n'
        self.write('tests/test_value.py', oracle)
        sig = 'def value(item):' if language == 'python' else 'export function value(item)'
        self.write(CONTRACT, f"""---
type: 'Task Contract'
title: 'Change audit fixture'
description: 'Check the endpoints of an isolated change.'
tags: ['fixture']
task: fixture
intent: 'Verify the declared change.'
language: {language}
target: {target}
signature: '{sig}'
test_command: 'python -m unittest tests/test_value.py'
budget:
  cyclomatic_max: 2
  nesting_max: 4
  lines_max: 40
  params_max: 4
tests: 'tests/test_value.py'
tests_sha256: '{hashlib.sha256(oracle.encode()).hexdigest()}'
touch_only: {json.dumps(allowed_paths)}
deps_allowed: {json.dumps(dependencies)}
forbids: ['network']
---
## Intent
Verify an allowed change.
## Interface
The fixture returns a value.
## Invariants
The perimeter is enforced.
## Examples
- An allowed source edit passes.
- A disallowed endpoint fails.
## Do / Don't
- DO preserve the original source for a copy.
## Tests
Use the sealed oracle.
## Constraints
PARAR y reportar si se necesita otro perimetro.
""")

    def audit(self, base, head):
        return self.run_process([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/validate_change_contract.py'),
                                 '--repo-root', str(self.root), '--contract', CONTRACT,
                                 '--base-ref', base, '--head-ref', head])

    def assert_result(self, result, code, marker=None):
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, code, output)
        if marker:
            self.assertIn(marker, output)

    def test_move_checks_source_and_destination_with_rename_detection_enabled(self):
        target = 'src/value.py'
        self.write(target, 'def value(item):\n    return item\n')
        self.contract(target, 'python', [target, 'allowed/**'])
        origin = self.write('outside/note.txt', 'Fixture contents preserved verbatim when moved.\n')
        base = self.commit()
        self.write('allowed/note.txt', origin.read_text(encoding='utf-8'))
        copied = self.commit()
        self.assert_result(self.audit(base, copied), 0)
        origin.unlink()
        moved = self.commit()
        self.git('config', 'diff.renames', 'true')
        self.assertTrue(self.git('diff', '--name-status', base, moved).startswith('R100'))
        self.assert_result(self.audit(base, moved), 1, 'OUT_OF_PERIMETER')
        self.git('config', 'diff.renames', 'false')
        self.assert_result(self.audit(base, moved), 1, 'OUT_OF_PERIMETER')

    def test_type_script_import_equals_uses_the_declared_dependency_allowlist(self):
        target = 'src/value.ts'
        self.write('package.json', json.dumps({'dependencies': {PACKAGE: '1.0.0'}}) + '\n')
        self.write(target, 'export function value() { return 1; }\n')
        self.contract(target, 'typescript', [target])
        deny = self.commit()
        self.write(target, f'import thing = require("{PACKAGE}");\nexport function value() {{ return thing; }}\n')
        imported = self.commit()
        self.assert_result(self.audit(deny, imported), 1, 'DEP_UNDECLARED')

    def test_type_script_import_equals_allows_an_explicit_package_and_internal_alias(self):
        target = 'src/value.ts'
        self.write('package.json', json.dumps({'dependencies': {PACKAGE: '1.0.0'}}) + '\n')
        self.write(target, 'export function value() { return 1; }\n')
        self.contract(target, 'typescript', [target], [PACKAGE])
        base = self.commit()
        self.write(target, f'import thing = require("{PACKAGE}");\n'
                   'import alias = thing.member;\nexport function value() { return alias; }\n')
        self.assert_result(self.audit(base, self.commit()), 0)
