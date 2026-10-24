"""Repeat the dependency pilot through the real authenticated Board HTTP API.

This is HTTP/process integration, not a rendered-browser or remote GitHub test.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_generated_task_evidence import TaskProject, isolated_env


@unittest.skipUnless((ROOT / 'src/hello.py').is_file(),
                     'template-only end-to-end test: project already initialized')
class DependencyWorkflowE2E(unittest.TestCase):
    def test_bootstrap_board_four_tasks_history_and_generated_ci(self):
        temporary = tempfile.TemporaryDirectory(prefix='kdd-dependency-e2e-')
        self.addCleanup(temporary.cleanup)
        directory = temporary.name
        area = Path(directory)
        root = area / 'project'
        root.mkdir()
        names = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files',
                                         '--cached', '--others', '--exclude-standard', '-z'],
                                        text=True, encoding='utf-8').split('\0')
        for name in filter(None, names):
            source, target = ROOT / name, root / name
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        bootstrap = subprocess.run([sys.executable, str(ROOT / 'scripts/bootstrap_project.py'),
                                     '--repo-dir', str(root), '--apply', '--profile', 'minimal',
                                     '--name', 'Own dependency integration',
                                     '--repository', 'Fixture/DependencyIntegration'],
                                    capture_output=True, text=True, encoding='utf-8',
                                    env=isolated_env(), timeout=120)
        self.assertEqual(bootstrap.returncode, 0, bootstrap.stdout + bootstrap.stderr)
        self.assertFalse(list((root / 'knowledge/tasks').glob('TASK-*.md')))
        p = TaskProject(root, count=4)
        # Add the generated workflow to the synthetic reviewed boundary.
        policy = json.loads((root / 'quality/product.json').read_text())
        policy['protected'].append('.github/workflows/validate.yml')
        # Product checks cover this fixture's oracles; infrastructure runs separately.
        for check in policy['checks']:
            check['argv'] += ['-p', 'test_feature*.py']
        p.write('quality/product.json', json.dumps(policy, indent=2))
        p.ref = p.commit('Simulated fixture reviewer: own product and generated CI')
        # Stubs are real failures before any implementation.
        red = p.command([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                         '-p', 'test_feature*.py'], check=False)
        self.assertNotEqual(red.returncode, 0)
        self.assertIn('NotImplementedError', red.stderr)
        self.assertNotIn('ModuleNotFoundError', red.stderr)
        self.assertNotIn('SyntaxError', red.stderr)

        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        token = 'ephemeral-dependency-http-fixture'
        env = dict(p.env, KDD_PROJECT_DIR=str(root), KDD_PYTHON=sys.executable,
                   KDD_BOARD_TOKEN=token, PORT=str(port))
        output = open(area / 'server.log', 'w', encoding='utf-8')
        self.addCleanup(output.close)
        server = subprocess.Popen(['node', str(ROOT / 'tools/kdd-board/src/server.ts')],
                                  cwd=root, env=env, stdout=output, stderr=output,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.addCleanup(lambda: self.stop(server))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = 'http://127.0.0.1:%s' % port

        def request(method, route, data=None):
            raw = json.dumps(data).encode() if data is not None else None
            req = urllib.request.Request(base + route, data=raw, method=method,
                headers={'Authorization':'Bearer ' + token,'Content-Type':'application/json'})
            try:
                with opener.open(req, timeout=180) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                with error:
                    return error.code, json.load(error)

        deadline = time.monotonic() + 45
        while True:
            self.assertIsNone(server.poll(), 'Board exited before startup')
            try:
                code, _ = request('GET', '/api/board')
                if code == 200:
                    break
            except urllib.error.URLError:
                pass
            self.assertLess(time.monotonic(), deadline, 'Board startup timed out')
            time.sleep(0.05)
        self.assertEqual(request('GET', '/api/tasks'), (200, []))
        before = p.snapshot()
        unauthorized = urllib.request.Request(base + '/api/tasks')
        with self.assertRaises(urllib.error.HTTPError) as denied:
            opener.open(unauthorized, timeout=10)
        self.addCleanup(denied.exception.close)
        self.assertIn(denied.exception.code, (401, 403))
        denied.exception.close()
        self.assertEqual(p.snapshot(), before)

        def transition(number, status, **fields):
            code, result = request('PATCH', '/api/tasks/TASK-%03d/status' % number,
                                   dict(status=status, **fields))
            self.assertEqual(code, 200, result)
            self.assertEqual(result['commit'], p.git('rev-parse', 'HEAD'))
            self.assertEqual(result['task']['status'], status)
            return result

        def reject_start(number, pending):
            before = p.snapshot()
            code, result = request('PATCH', '/api/tasks/TASK-%03d/status' % number,
                                   {'status':'in_progress','assignee':'fixture worker'})
            self.assertEqual(code, 409, result)
            self.assertEqual(result.get('code'), 'TASK_DEPENDENCIES')
            self.assertEqual(result['details']['pending_dependencies'], pending)
            self.assertEqual(p.snapshot(), before)

        dependencies = {1:[], 2:[1], 3:[1], 4:[2, 3]}
        for number in range(1, 5):
            code, result = request('POST', '/api/tasks',
                {'task_id':'TASK-%03d' % number, 'title':'Own feature %s' % number,
                 'description':'Dependency integration through Board',
                 'contract':p.contract(number),
                 'depends_on':['TASK-%03d' % n for n in dependencies[number]]})
            self.assertEqual(code, 201, result)
            self.assertEqual(result['commit'], p.git('rev-parse', 'HEAD'))
            transition(number, 'ready', approved_ref=p.ref)
        reject_start(2, ['TASK-001'])
        reject_start(4, ['TASK-002', 'TASK-003'])
        transition(1, 'in_progress', assignee='worker1')
        tips = {1:p.implement(1)}
        transition(1, 'done')
        for number in (2, 3):
            transition(number, 'in_progress', assignee='worker%s' % number)
        original = p.git('rev-parse', 'task/TASK-003')
        transition(3, 'needs_human_input', reason='Simulated pause without changing requirements')
        transition(3, 'ready', reason='Simulated pause resolved')
        transition(3, 'in_progress', assignee='worker3')
        self.assertEqual(p.git('rev-parse', 'task/TASK-003'), original)
        tips[2] = p.implement(2)
        transition(2, 'done')
        reject_start(4, ['TASK-003'])
        tips[3] = p.implement(3)
        transition(3, 'done')
        transition(4, 'in_progress', assignee='worker4')
        tips[4] = p.implement(4)
        transition(4, 'done')
        code, tasks = request('GET', '/api/tasks')
        self.assertEqual(code, 200)
        self.assertEqual([task['status'] for task in tasks], ['done'] * 4)
        states = 0
        for number in range(1, 5):
            code, task = request('GET', '/api/tasks/TASK-%03d' % number)
            self.assertEqual(code, 200)
            expected = ['backlog','ready','in_progress','done']
            if number == 3:
                expected = ['backlog','ready','in_progress','needs_human_input','ready','in_progress','done']
            self.assertEqual([entry['status'] for entry in task['journal']], expected)
            states += len(expected)
            close = task['journal'][-1]['commit']
            self.assertEqual(p.git('rev-parse', close + '^'), task['verified_ref'])
            p.git('merge-base', '--is-ancestor', tips[number], 'main')
            report = json.loads((root / task['evidence']).read_text(encoding='utf-8'))
            self.assertEqual(report['passed_tests'], 2)
            self.assertEqual(report['tested_commit'], task['verified_ref'])
            self.assertEqual(task['approved_ref'], p.ref)
        self.assertEqual(states, 19)
        history = p.command([sys.executable, 'scripts/validate_tasks.py',
                             '--base-ref', p.ref, '--head-ref', 'main'])
        self.assertIn('0 error(s)', history.stdout)
        clean = p.snapshot()
        workflow = (root / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        def step(name):
            block = workflow.split('      - name: ' + name + '\n', 1)[1].split('      - name:', 1)[0]
            return textwrap.dedent(block.split('        run: |\n', 1)[1])
        ci_env = dict(p.env, KDD_QUALITY_POLICY='quality/product.json',
                      KDD_QUALITY_APPROVED_REF=p.ref, KDD_REQUIRED_EVIDENCE='quality',
                      KDD_APPROVED_BASELINE_REF=p.ref, KDD_CONTRACTS_DIR='knowledge/contracts')
        for layer in ('SECURITY','COMPLIANCE','PRIVACY','ACCESSIBILITY',
                      'DEPENDENCY_EOL','OBSERVABILITY','TEST_COVERAGE'):
            ci_env['KDD_' + layer + '_SCAN_DIR'] = layer.lower().replace('_', '-') + '/scan'
        for name in ('Check approved contract and oracle baseline',
                     'Check product quality approval configuration',
                     'Approve project quality (when configured)'):
            result = p.command([sys.executable, '-c', step(name)], env=ci_env, check=False, timeout=240)
            self.assertEqual(result.returncode, 0, name + '\n' + result.stdout + result.stderr)
            if name.startswith('Approve'):
                self.assertIn('PASS quality:', result.stdout)
                self.assertEqual(result.stdout.count('RUN '), 4)
        ci_env['KDD_QUALITY_OUTCOME'] = 'success'
        summary = p.command([sys.executable, 'scripts/optional_evidence.py', 'summary',
                            '--layers', 'security,compliance,privacy,accessibility,dependency-eol,observability,test-coverage,quality'],
                           env=ci_env)
        self.assertIn('PASS [quality]', summary.stdout)
        for layer in ('security','compliance','privacy','accessibility',
                      'dependency-eol','observability','test-coverage'):
            self.assertIn('SKIP [' + layer + ']', summary.stdout)
        self.assertEqual(p.snapshot(), clean)
        self.stop(server)
        output.close()

    @staticmethod
    def stop(server):
        if server.poll() is None:
            server.terminate()
        server.wait(timeout=20)


if __name__ == '__main__':
    unittest.main()
