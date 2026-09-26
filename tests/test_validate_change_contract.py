"""A sealed baseline must govern checks against an actual Git change."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_change_contract as gate  # noqa: E402
import change_contract_multilang as languages  # noqa: E402


class ChangeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self._git('init', '-q')
        self._git('config', 'user.name', 'KDD Test')
        self._git('config', 'user.email', 'kdd@example.test')
        self.contract = 'knowledge/contracts/demo.md'
        self._write(self.contract, self._contract())
        self._write('src/app.py', 'def value():\n    return 1\n')
        self._write('tests/test_app.py', '# frozen oracle\n')
        self.base = self._commit('approved baseline')

    def _git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args],
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')

    def _commit(self, message):
        self._git('add', '-A')
        self._git('commit', '-qm', message)
        return self._git('rev-parse', 'HEAD')

    def _contract(self, allowed='[]', perimeter="['src/app.py']",
                  budget=12, target='src/app.py', metric='cyclomatic_max'):
        return ("---\n"
                "task: demo\n"
                "target: {}\n"
                "tests: tests/test_app.py\n"
                "touch_only: {}\n"
                "deps_allowed: {}\n"
                "budget:\n  {}: {}\n"
                "---\n").format(target, perimeter, allowed, metric, budget)

    def _rules(self, head):
        findings = gate.audit_change(self.root, self.contract,
                                     self.base, head)
        return {finding['rule'] for finding in findings}

    def test_target_change_with_stdlib_import_passes(self):
        self._write('src/app.py', 'import json\n\ndef value():\n    return 2\n')
        self.assertEqual(self._rules(self._commit('implementation')), set())

    def test_real_diff_outside_touch_only_fails(self):
        self._write('README.md', 'unapproved edit\n')
        self.assertIn('OUT_OF_PERIMETER', self._rules(self._commit('escape')))

    def test_frozen_oracle_change_fails(self):
        self._write('tests/test_app.py', '# altered oracle\n')
        self.assertIn('TESTS_TOUCHED', self._rules(self._commit('alter oracle')))

    def test_new_undeclared_external_import_fails(self):
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('add import')))

    def test_new_local_import_passes(self):
        self._write('src/helper.py', 'VALUE = 2\n')
        self.base = self._commit('local helper baseline')
        self._write('src/app.py', 'from src import helper\n\ndef value():\n'
                                  '    return helper.VALUE\n')
        self.assertEqual(self._rules(self._commit('use helper')), set())

    def test_declared_external_import_passes(self):
        self._write(self.contract, self._contract(allowed="['requests']"))
        self.base = self._commit('approved dependency')
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.assertEqual(self._rules(self._commit('use dependency')), set())

    def test_existing_external_import_is_grandfathered(self):
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 1\n')
        self.base = self._commit('existing import')
        self._write('src/app.py', 'import requests\n\ndef value():\n    return 2\n')
        self.assertEqual(self._rules(self._commit('change logic')), set())

    def test_budget_is_enforced_on_changed_python_target(self):
        self._write(self.contract, self._contract(budget=1))
        self.base = self._commit('strict budget')
        self._write('src/app.py',
                    'def value(x):\n    if x:\n        return 1\n    return 2\n')
        self.assertIn('BUDGET_CYCLOMATIC',
                      self._rules(self._commit('complex implementation')))

    def test_contract_change_cannot_expand_approved_perimeter(self):
        self._write(self.contract, self._contract(perimeter="['*']"))
        self._write('README.md', 'out of perimeter\n')
        rules = self._rules(self._commit('self approve'))
        self.assertIn('OUT_OF_PERIMETER', rules)

    def test_base_must_be_ancestor(self):
        self._write('src/app.py', 'def value():\n    return 2\n')
        head = self._commit('implementation')
        findings = gate.audit_change(self.root, self.contract, head,
                                     self.base)
        self.assertIn('GIT_RANGE', {item['rule'] for item in findings})

    def test_missing_target_is_not_silently_skipped(self):
        (self.root / 'src' / 'app.py').unlink()
        self.assertIn('TARGET_MISSING', self._rules(self._commit('remove target')))

    def _language_base(self, target, source, manifest, manifest_text,
                       allowed='[]', budget=12, metric='cyclomatic_max'):
        self._write(self.contract, self._contract(
            target=target, perimeter="['{}', '{}']".format(target, manifest),
            allowed=allowed, budget=budget, metric=metric))
        self._write(target, source)
        self._write(manifest, manifest_text)
        self.base = self._commit('approved language baseline')

    def test_javascript_declared_package_and_scoped_import_pass(self):
        self._language_base('src/app.js', 'export function value() { return 1; }\n',
                            'package.json', '{"dependencies":{"@acme/tool":"1"}}',
                            allowed="['@acme/tool']")
        self._write('src/app.js',
                    "import tool from '@acme/tool/sub';\n"
                    'export function value() { return tool; }\n')
        self.assertEqual(self._rules(self._commit('use JS package')), set())

    def test_adapter_directly_checks_a_simple_javascript_function(self):
        findings = languages.audit_source(
            'src/app.js', b'function value() { return 1; }\n',
            b'function value() { return 2; }\n',
            {'budget': {'cyclomatic_max': 2}, 'deps_allowed': []},
            {'before': '{}', 'after': '{}'})
        self.assertEqual(findings, [])

    def test_javascript_undeclared_import_fails(self):
        self._language_base('src/app.js', 'export function value() { return 1; }\n',
                            'package.json', '{"dependencies":{"lodash":"1"}}')
        self._write('src/app.js',
                    "import _ from 'lodash';\nexport function value() { return _; }\n")
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('new JS import')))

    def test_javascript_new_manifest_dependency_is_checked(self):
        self._language_base('src/app.js', 'export function value() { return 1; }\n',
                            'package.json', '{"dependencies":{}}')
        self._write('package.json', '{"dependencies":{"lodash":"1"}}')
        self._write('src/app.js', 'export function value() { return 2; }\n')
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('new package')))

    def test_javascript_complexity_budget_fails(self):
        self._language_base('src/app.js', 'function value(x) { return x; }\n',
                            'package.json', '{}', budget=1)
        self._write('src/app.js',
                    'function value(x) { if (x) return 1; return 0; }\n')
        self.assertIn('BUDGET_CYCLOMATIC', self._rules(self._commit('branch')))

    def test_typescript_parameters_budget_fails(self):
        self._language_base('src/app.ts', 'export function value(a:number) { return a; }\n',
                            'package.json', '{}', budget=1, metric='params_max')
        self._write('src/app.ts',
                    'export function value(a:number,b:number) { return a+b; }\n')
        self.assertIn('BUDGET_PARAMS', self._rules(self._commit('extra argument')))

    def test_tsx_local_import_and_jsx_pass(self):
        self._language_base('src/app.tsx', 'export const View = () => <div/>;\n',
                            'package.json', '{}')
        self._write('src/local.ts', 'export const x = 1;\n')
        self.base = self._commit('local module baseline')
        self._write('src/app.tsx',
                    "import {x} from './local';\nexport const View = () => <div>{x}</div>;\n")
        self.assertEqual(self._rules(self._commit('TSX view')), set())

    def test_javascript_syntax_error_fails_closed(self):
        self._language_base('src/app.js', 'function value() { return 1; }\n',
                            'package.json', '{}')
        self._write('src/app.js', 'function value( {\n')
        self.assertIn('CHECK_PARSE', self._rules(self._commit('broken JS')))

    def test_go_declared_module_and_stdlib_pass(self):
        self._language_base('src/app.go', 'package src\nfunc value() int { return 1 }\n',
                            'go.mod', 'module example.com/demo\ngo 1.23\n'
                            'require github.com/acme/lib v1.0.0\n',
                            allowed="['github.com/acme/lib']")
        self._write('src/app.go', 'package src\nimport (\n"fmt"\n"github.com/acme/lib"\n)\n'
                    'func value() int { fmt.Println("ok"); return 1 }\n')
        self.assertEqual(self._rules(self._commit('Go imports')), set())

    def test_go_undeclared_module_fails(self):
        self._language_base('src/app.go', 'package src\nfunc value() int { return 1 }\n',
                            'go.mod', 'module example.com/demo\ngo 1.23\n'
                            'require github.com/acme/lib v1.0.0\n')
        self._write('src/app.go', 'package src\nimport "github.com/acme/lib"\n'
                    'func value() int { return 1 }\n')
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('Go import')))

    def test_go_nesting_budget_fails(self):
        self._language_base('src/app.go', 'package src\nfunc value(x int) int { return x }\n',
                            'go.mod', 'module example.com/demo\ngo 1.23\n',
                            budget=1, metric='nesting_max')
        self._write('src/app.go', 'package src\nfunc value(x int) int { '
                    'if x>0 { for x>1 { return x } }; return 0 }\n')
        self.assertIn('BUDGET_NESTING', self._rules(self._commit('nested Go')))

    def test_rust_declared_crate_passes(self):
        self._language_base('src/lib.rs', 'pub fn value() -> i32 { 1 }\n',
                            'Cargo.toml', '[package]\nname="demo"\nversion="0.1.0"\n'
                            '[dependencies]\nserde="1"\n', allowed="['serde']")
        self._write('src/lib.rs', 'use serde::Serialize;\n'
                    'pub fn value() -> i32 { 1 }\n')
        self.assertEqual(self._rules(self._commit('Rust import')), set())

    def test_rust_undeclared_crate_fails(self):
        self._language_base('src/lib.rs', 'pub fn value() -> i32 { 1 }\n',
                            'Cargo.toml', '[package]\nname="demo"\nversion="0.1.0"\n'
                            '[dependencies]\nserde="1"\n')
        self._write('src/lib.rs', 'use serde::Serialize;\n'
                    'pub fn value() -> i32 { 1 }\n')
        self.assertIn('DEP_UNDECLARED', self._rules(self._commit('Rust import')))

    def test_rust_macro_budget_is_explicitly_unsupported(self):
        self._language_base('src/lib.rs', 'pub fn value() -> i32 { 1 }\n',
                            'Cargo.toml', '[package]\nname="demo"\nversion="0.1.0"\n')
        self._write('src/lib.rs', 'pub fn value() -> i32 { println!("hi"); 1 }\n')
        self.assertIn('BUDGET_UNSUPPORTED', self._rules(self._commit('macro')))

    def test_rust_complexity_budget_fails(self):
        self._language_base('src/lib.rs', 'pub fn value(x:i32) -> i32 { x }\n',
                            'Cargo.toml', '[package]\nname="demo"\nversion="0.1.0"\n',
                            budget=1)
        self._write('src/lib.rs', 'pub fn value(x:i32) -> i32 { '
                    'if x>0 { 1 } else { 0 } }\n')
        self.assertIn('BUDGET_CYCLOMATIC', self._rules(self._commit('branch')))

    def test_unsupported_language_still_fails(self):
        self._language_base('src/App.java', 'class App {}\n',
                            'pom.xml', '<project/>')
        self._write('src/App.java', 'class App { int x; }\n')
        self.assertIn('CHECK_UNSUPPORTED', self._rules(self._commit('Java change')))


if __name__ == '__main__':
    unittest.main()
