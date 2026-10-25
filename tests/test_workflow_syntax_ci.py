"""Real CI step bodies over Git fixtures and a verified offline tool cache."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tests import test_workflow_syntax as support


class WorkflowSyntaxCI(support.Fixture):
    def step(self, name):
        source = (support.ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        marker = '      - name: ' + name + '\n'
        self.assertIn(marker, source)
        return source.split(marker, 1)[1].split('\n      - ', 1)[0]

    def body(self, name):
        block = self.step(name)
        self.assertIn('        shell: python\n', block)
        self.assertIn('        run: |\n', block)
        lines = block.split('        run: |\n', 1)[1].splitlines()
        return '\n'.join(line[10:] if line.startswith('          ') else line for line in lines) + '\n'

    def test_steps_are_unconditional_and_precede_expensive_validation(self):
        source = (support.ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        names = ['Install pinned workflow checker', 'Validate all GitHub Actions workflows']
        for name in names:
            block = self.step(name)
            self.assertNotIn('        if:', block)
            self.assertNotIn('continue-on-error:', block)
            self.assertIn('scripts/validate_workflows.py', block)
        start = source.index('- name: Check approved contract and oracle baseline')
        install, check = [source.index('- name: ' + name) for name in names]
        self.assertLess(start, install)
        self.assertLess(install, check)
        for target in ['- name: Set up Node.js', '- name: Install pinned Pages publisher for PR',
                       "- name: Run each contract's test_command", '- name: Run unit tests (1/2)']:
            self.assertLess(check, source.index(target))
        install_body, check_body = [self.body(name) for name in names]
        for value in ['RUNNER_TEMP', 'GITHUB_ENV', 'GITHUB_PATH', 'kdd-actionlint', 'install']:
            self.assertIn(value, install_body)
        for value in ['KDD_ACTIONLINT_BINARY', 'check', '--repo-root']:
            self.assertIn(value, check_body)

    def test_existing_jobs_permissions_and_two_passes_remain(self):
        source = (support.ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertEqual(source.count('os: [ubuntu-latest, windows-latest]'), 2)
        jobs = source.split('\njobs:\n', 1)[1]
        names = set(re.findall(r'^  ([a-z_]+):$', jobs, re.M))
        self.assertEqual(names, {'validate', 'board'})
        command = 'run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'
        self.assertEqual(source.count(command), 2)
        self.assertEqual(source.count("KDD_SKIP_INIT_POST_APPLY_SUITE: '1'"), 2)
        self.assertIn('contents: read', source)
        self.assertIn('actions: read', source)
        self.assertNotIn('continue-on-error:', source)
        self.assertNotRegex(source, r'(?m)^\s+paths(?:-ignore)?:')
        self.assertNotRegex(source, r'(?m)^\s+(?:pages|id-token): write')

    def run_step_pair(self, bad=False):
        install = self.body('Install pinned workflow checker')
        check = self.body('Validate all GitHub Actions workflows')
        for rel in ['scripts/validate_workflows.py', 'scripts/process_tree.py',
                    'tools/workflow-syntax/actionlint.json']:
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((support.ROOT / rel).read_bytes())
        if bad:
            self.write('deploy-pages.yml', support.REGRESSION)
        self.commit('real CI step fixture')
        runner = self.area / 'runner temp'
        cache = runner / 'kdd-actionlint' / support.VERSION / self.platform_key
        cache.mkdir(parents=True)
        shutil.copyfile(self.archive, cache / self.pin['archive'])
        shutil.copyfile(self.binary, cache / self.pin['executable'])
        (cache / self.pin['executable']).chmod(0o755)
        env_file, path_file = runner / 'github-env', runner / 'github-path'
        env_file.write_text('', encoding='utf-8')
        path_file.write_text('', encoding='utf-8')
        env = {**os.environ, 'RUNNER_TEMP': str(runner), 'GITHUB_ENV': str(env_file), 'GITHUB_PATH': str(path_file)}
        result = subprocess.run([sys.executable, '-c', install], cwd=self.repo, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=150)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        exported = dict(line.split('=', 1) for line in env_file.read_text(encoding='utf-8').splitlines())
        self.assertEqual(set(exported), {'KDD_ACTIONLINT_BINARY', 'KDD_ACTIONLINT_ARCHIVE'})
        env.update(exported)
        env['PATH'] = os.pathsep.join(path_file.read_text(encoding='utf-8').splitlines() + [env['PATH']])
        before = self.git('status', '--porcelain')
        result = subprocess.run([sys.executable, '-c', check], cwd=self.repo, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=150)
        self.assertEqual(self.git('status', '--porcelain'), before)
        return result

    def test_real_step_bodies_accept_valid_workflows_without_network(self):
        result = self.run_step_pair()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('WORKFLOW_SYNTAX_PASS', result.stdout)

    def test_real_step_bodies_reject_untriggered_pages_yaml(self):
        result = self.run_step_pair(bad=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WORKFLOW_SYNTAX', result.stdout)
        self.assertIn('deploy-pages.yml', result.stdout)
        data = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
        self.assertTrue(any(e.get('line') == 50 for e in data.get('diagnostics', [])))


if __name__ == '__main__':
    support.unittest.main()
