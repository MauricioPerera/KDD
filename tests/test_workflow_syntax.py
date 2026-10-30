"""Real actionlint, fresh CLI processes and Git fixtures; no network in tests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/validate_workflows.py'
MANIFEST = ROOT / 'tools/workflow-syntax/actionlint.json'
MANIFEST_SHA = 'c700cffd8c202f794fb0dc8a31ade2a4c9f5f21e0eb6ef22e1b1aef7892865e2'
VERSION = '1.7.12'
GOOD = 'name: fixture\non: [push, pull_request]\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo safe\n'
REGRESSION = r"""name: deploy-pages

on:
  workflow_run:
    workflows: [validate-contracts]
    types: [completed]

permissions:
  contents: read

jobs:
  deploy:
    if: >-
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.event == 'push' &&
      github.event.workflow_run.head_branch == 'main' &&
      github.event.workflow_run.repository.full_name == 'MauricioPerera/KDD'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      actions: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    concurrency:
      group: github-pages
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ github.event.workflow_run.head_sha }}
          persist-credentials: false

      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: '3.11'

      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: '24'
          cache: npm
          cache-dependency-path: site/package-lock.json

      - name: Install pinned publisher
        run: npm ci --prefix site --ignore-scripts --no-audit --no-fund

      - name: Install pinned discovery parsers
        run: python -m pip install --only-binary=:all: -r requirements-change-audit.txt

      - name: Download Ubuntu CI inventory
        uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: kdd-ci-inventory-${{ github.event.workflow_run.id }}-${{ github.event.workflow_run.run_attempt }}-ubuntu-latest
          run-id: ${{ github.event.workflow_run.id }}
          repository: ${{ github.repository }}
          github-token: ${{ github.token }}
          digest-mismatch: error
          path: ${{ runner.temp }}/kdd-ci-inventory/ubuntu-latest

      - name: Download Windows CI inventory
        uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: kdd-ci-inventory-${{ github.event.workflow_run.id }}-${{ github.event.workflow_run.run_attempt }}-windows-latest
          run-id: ${{ github.event.workflow_run.id }}
          repository: ${{ github.repository }}
          github-token: ${{ github.token }}
          digest-mismatch: error
          path: ${{ runner.temp }}/kdd-ci-inventory/windows-latest

      - name: Verify Pages build contract
        run: |
          python -m unittest tests/test_pages_build.py
          python scripts/validate_contracts.py knowledge/contracts

      - name: Build and validate public bundle
        env:
          CI_RUN_URL: ${{ github.event.workflow_run.html_url }}
          CI_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt }}
          KDD_TRUSTED_RUNTIME_REF: ${{ vars.KDD_TRUSTED_RUNTIME_REF }}
        run: python site/build.py --output "$RUNNER_TEMP/kdd-pages" --ci-run-url "$CI_RUN_URL" --ci-inventory-dir "$RUNNER_TEMP/kdd-ci-inventory" --ci-run-attempt "$CI_RUN_ATTEMPT" --ci-trusted-runtime-ref "$KDD_TRUSTED_RUNTIME_REF"

      - uses: actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0

      - uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0
        with:
          path: ${{ runner.temp }}/kdd-pages

      - id: deployment
        uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1
"""


def tool():
    pins = json.loads(MANIFEST.read_text(encoding='utf-8'))
    system = {'win32': 'windows', 'darwin': 'darwin'}.get(sys.platform, 'linux')
    machine = platform.machine().lower()
    arch = {'amd64': 'amd64', 'x86_64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}[machine]
    key = system + '_' + arch
    item = pins['platforms'][key]
    selected = os.environ.get('KDD_ACTIONLINT_BINARY') or shutil.which(item['executable'])
    binary = Path(selected) if selected else Path(tempfile.gettempdir()) / 'kdd-actionlint' / VERSION / key / item['executable']
    archive = Path(os.environ.get('KDD_ACTIONLINT_ARCHIVE', str(binary.parent / item['archive'])))
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != item['binary_sha256']:
        raise AssertionError('Prepare the reviewed actionlint binary before running integration tests: ' + str(binary))
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != item['archive_sha256']:
        raise AssertionError('Prepare the reviewed offline actionlint archive: ' + str(archive))
    return binary.resolve(), archive.resolve(), key, item


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd workflow syntax ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.repo = self.area / 'project with spaces'
        self.workflows = self.repo / '.github/workflows'
        self.workflows.mkdir(parents=True)
        self.binary, self.archive, self.platform_key, self.pin = tool()
        self.git('init', '-q', '-b', 'main')
        self.write('ci.yml', GOOD)
        self.commit('baseline')

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'user.name=Workflow test', '-c', 'user.email=workflow@example.invalid',
                                        '-c', 'maintenance.autoDetach=false', '-c', 'gc.autoDetach=false', *args],
                                       cwd=self.repo, text=True, encoding='utf-8', stderr=subprocess.PIPE)

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', message)
        return self.git('rev-parse', 'HEAD').strip()

    def write(self, name, text):
        (self.workflows / name).write_text(text, encoding='utf-8')

    def engine(self, paths=None, config=True):
        cfg = self.area / 'trusted config.yaml'
        cfg.write_text('{}\n', encoding='utf-8')
        args = [str(self.binary), '-shellcheck=', '-pyflakes=', '-format', '{{json .}}']
        if config:
            args += ['-config-file', str(cfg)]
        return subprocess.run([*args, *map(str, paths or sorted(self.workflows.glob('*.yml')))],
                              cwd=self.repo, capture_output=True, text=True, encoding='utf-8', timeout=120)

    def cli(self, *args, cwd=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=cwd or self.repo,
                                capture_output=True, text=True, encoding='utf-8', timeout=150)
        try:
            data = json.loads(result.stdout)
        except ValueError:
            self.fail('CLI must provide JSON, not vacuous output: ' + result.stdout + result.stderr)
        self.assertIsInstance(data, dict)
        return result, data

    def check(self, cwd=None, binary=None):
        return self.cli('check', '--repo-root', self.repo, '--actionlint', binary or self.binary, cwd=cwd)

    def failure(self, result, data, code):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(data.get('ok'), False)
        self.assertEqual(data.get('code'), code, data)


class EngineControls(Fixture):
    def test_reviewed_engine_accepts_current_real_workflows(self):
        result = self.engine(sorted((ROOT / '.github/workflows').glob('*.yml')))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_engine_reproduces_actual_pages_error_at_line_50(self):
        self.write('deploy-pages.yml', REGRESSION)
        result = self.engine()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        errors = json.loads(result.stdout)
        self.assertTrue(any(e['line'] == 50 and e['kind'] == 'syntax-check' for e in errors), errors)

    def test_engine_accepts_the_literal_and_quoted_original_command(self):
        command = 'python -m pip install --only-binary=:all: -r requirements-change-audit.txt'
        for value in ('run: |\n          ' + command, 'run: "' + command + '"'):
            self.write('ci.yml', GOOD.replace('run: echo safe', value))
            result = self.engine()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_engine_checks_actions_expressions_not_only_yaml(self):
        self.write('ci.yml', GOOD.replace('echo safe', 'echo ${{ github.property_that_does_not_exist }}'))
        result = self.engine()
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any(e['kind'] == 'expression' for e in json.loads(result.stdout)))


class WorkflowChecker(Fixture):
    def test_all_files_and_both_suffixes_are_enumerated(self):
        self.write('future.yaml', GOOD)
        self.write('notes.txt', 'not a workflow')
        result, data = self.check()
        self.assertEqual(result.returncode, 0, data)
        self.assertIs(data.get('ok'), True)
        self.assertEqual(data.get('files'), ['.github/workflows/ci.yml', '.github/workflows/future.yaml'])
        self.assertEqual(data.get('diagnostics'), [])
        self.assertEqual(data.get('version'), VERSION)
        self.assertEqual(data.get('tool_exit_code'), 0)

    def test_untriggered_pages_workflow_regression_is_a_real_failure(self):
        self.write('deploy-pages.yml', REGRESSION)
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX')
        errors = data.get('diagnostics', [])
        self.assertTrue(any(e.get('line') == 50 and e.get('column', 0) > 0
                            and e.get('filepath', '').endswith('deploy-pages.yml') for e in errors), data)

    def test_future_yaml_file_cannot_be_omitted(self):
        self.write('not-yet-triggered.yaml', GOOD.replace('run: echo safe', 'run: invalid: value'))
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX')
        self.assertIn('.github/workflows/not-yet-triggered.yaml', data.get('files', []))

    def test_invalid_actions_expression_is_reported(self):
        self.write('ci.yml', GOOD.replace('echo safe', 'echo ${{ github.property_that_does_not_exist }}'))
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX')
        self.assertTrue(any(e.get('kind') == 'expression' for e in data.get('diagnostics', [])))

    def test_duplicate_workflow_keys_are_rejected(self):
        self.write('ci.yml', GOOD.replace('name: fixture', 'name: fixture\nname: duplicate'))
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX')
        self.assertTrue(data.get('diagnostics'))

    def test_empty_inventory_is_not_a_pass(self):
        (self.workflows / 'ci.yml').unlink()
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX_INPUT')

    def test_missing_inventory_directory_is_not_a_pass(self):
        (self.workflows / 'ci.yml').unlink()
        self.workflows.rmdir()
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX_INPUT')

    def test_nonregular_workflow_entry_is_rejected(self):
        (self.workflows / 'directory.yaml').mkdir()
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX_INPUT')

    def test_cwd_does_not_change_the_selected_project(self):
        other = self.area / 'unrelated'
        other.mkdir()
        result, data = self.check(cwd=other)
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data.get('files'), ['.github/workflows/ci.yml'])

    def test_candidate_ignore_config_cannot_hide_a_real_expression_error(self):
        self.write('ci.yml', GOOD.replace('echo safe', 'echo ${{ github.property_that_does_not_exist }}'))
        (self.repo / '.github/actionlint.yaml').write_text("paths:\n  '.github/workflows/**':\n    ignore: ['.*']\n", encoding='utf-8')
        control = self.engine(config=False)
        self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
        result, data = self.check()
        self.failure(result, data, 'WORKFLOW_SYNTAX')
        self.assertTrue(any(e.get('kind') == 'expression' for e in data.get('diagnostics', [])))

    def test_workflow_commands_are_never_executed(self):
        marker = self.area / 'workflow-must-not-run'
        self.write('ci.yml', GOOD.replace('echo safe', 'echo executed > "' + str(marker) + '"'))
        result, data = self.check()
        self.assertEqual(result.returncode, 0, data)
        self.assertFalse(marker.exists())

    def test_unicode_paths_and_working_tree_are_preserved(self):
        self.write('flujo con espacio \u00f1.yaml', GOOD)
        head = self.commit('unicode workflow')
        before = {p.name: p.read_bytes() for p in self.workflows.iterdir()}
        result, data = self.check()
        self.assertEqual(result.returncode, 0, data)
        self.assertIn('.github/workflows/flujo con espacio \u00f1.yaml', data.get('files', []))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.workflows.iterdir()})
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), head)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_unreviewed_binary_is_rejected_before_execution(self):
        fake = self.area / self.pin['executable']
        fake.write_bytes(b'not the reviewed executable')
        result, data = self.check(binary=fake)
        self.failure(result, data, 'WORKFLOW_SYNTAX_TOOL')
        self.assertIn('hash', json.dumps(data).lower())


class Installer(Fixture):
    def test_manifest_is_an_exact_reviewed_dependency(self):
        normalized = MANIFEST.read_bytes().replace(b'\r\n', b'\n')
        self.assertEqual(hashlib.sha256(normalized).hexdigest(), MANIFEST_SHA)
        self.assertEqual(json.loads(normalized)['version'], VERSION)

    def test_offline_install_exports_only_verified_paths(self):
        cache = self.area / 'external cache'
        env_file, path_file = self.area / 'github-env', self.area / 'github-path'
        env_file.write_text('', encoding='utf-8')
        path_file.write_text('', encoding='utf-8')
        result, data = self.cli('install', '--cache-dir', cache, '--archive', self.archive,
                                '--github-env', env_file, '--github-path', path_file)
        self.assertEqual(result.returncode, 0, data)
        binary = Path(data.get('binary', 'missing'))
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), self.pin['binary_sha256'])
        values = dict(line.split('=', 1) for line in env_file.read_text(encoding='utf-8').splitlines())
        self.assertEqual(set(values), {'KDD_ACTIONLINT_BINARY', 'KDD_ACTIONLINT_ARCHIVE'})
        self.assertEqual(values['KDD_ACTIONLINT_BINARY'], str(binary))
        self.assertEqual(path_file.read_text(encoding='utf-8').splitlines(), [str(binary.parent)])

    def test_corrupt_archive_fails_without_exporting_a_tool(self):
        bad = self.area / self.pin['archive']
        bad.write_bytes(b'corrupt archive')
        env_file, path_file = self.area / 'github-env', self.area / 'github-path'
        env_file.write_text('', encoding='utf-8')
        path_file.write_text('', encoding='utf-8')
        result, data = self.cli('install', '--cache-dir', self.area / 'cache', '--archive', bad,
                                '--github-env', env_file, '--github-path', path_file)
        self.failure(result, data, 'WORKFLOW_SYNTAX_TOOL')
        self.assertEqual(env_file.read_text(encoding='utf-8'), '')
        self.assertEqual(path_file.read_text(encoding='utf-8'), '')

    def test_cache_hit_rechecks_binary_integrity(self):
        cache = self.area / 'cache'
        args = ['install', '--cache-dir', cache, '--archive', self.archive]
        result, data = self.cli(*args)
        self.assertEqual(result.returncode, 0, data)
        result, reused = self.cli(*args)
        self.assertEqual(result.returncode, 0, reused)
        self.assertEqual(reused.get('binary'), data.get('binary'))
        Path(data['binary']).write_bytes(b'tampered cache entry')
        result, bad = self.cli(*args)
        self.failure(result, bad, 'WORKFLOW_SYNTAX_TOOL')
        self.assertIn('hash', json.dumps(bad).lower())


class GuardIntegration(Fixture):
    def assert_protected(self, path):
        for rel in ['scripts/guard_pr_baseline.py', 'scripts/validate_contracts.py',
                    'scripts/validate_workflows.py', 'tools/workflow-syntax/actionlint.json',
                    'knowledge/contracts/workflow-syntax.md', 'tests/test_workflow_syntax.py']:
            dest = self.repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / rel).read_bytes())
        baseline = self.commit('reviewed fixture baseline')
        target = self.repo / path
        target.write_bytes(target.read_bytes() + b'\n# changed candidate bytes\n')
        head = self.commit('candidate changes protected tool')
        code = "import json,sys;sys.path.insert(0,'scripts');import guard_pr_baseline as g;print(json.dumps(g.check(*sys.argv[1:])))"
        result = subprocess.run([sys.executable, '-c', code, baseline, head, baseline],
                                cwd=self.repo, capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(path + ': trusted gate file changed in PR', json.loads(result.stdout))

    def test_validator_is_protected_using_two_real_commits(self):
        self.assert_protected('scripts/validate_workflows.py')

    def test_tool_manifest_is_protected_using_two_real_commits(self):
        self.assert_protected('tools/workflow-syntax/actionlint.json')


if __name__ == '__main__':
    unittest.main()
