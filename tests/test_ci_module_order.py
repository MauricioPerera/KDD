"""Real module jobs, complete inventories and an optional post-init order."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/run_test_suite.py'
PROFILE = Path('tools/ci/postinit-module-order.json')


class ModuleOrder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd order \u00f1 ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.root = self.project('project with spaces')
        self.calls = 0

    def project(self, name, modules=('test_a', 'test_b', 'test_c')):
        root = self.area / name
        (root / 'tests').mkdir(parents=True)
        for module in modules:
            self.module(root, module)
        return root

    def module(self, root, name, body='self.assertTrue(True)'):
        source = ('import os,time,unittest\nfrom pathlib import Path\n'
                  'class T(unittest.TestCase):\n def test_case(self):\n'
                  '  with Path(%r).open("a",encoding="utf-8") as stream: stream.write("ran\\n")\n'
                  '%s\n') % (name + '.ran', '\n'.join('  ' + line for line in body.splitlines()))
        (root / 'tests' / (name + '.py')).write_text(source, encoding='utf-8')

    def profile(self, names, root=None):
        path = (root or self.root) / 'priorities \u00f1.json'
        path.write_text(json.dumps(names), encoding='utf-8')
        return path

    def invoke(self, root=None, profile=None, workers=2, launcher=False):
        root = root or self.root
        self.calls += 1
        report = self.area / ('report-%d.json' % self.calls)
        if launcher:
            command = [sys.executable, str(root / 'scripts/init_post_apply_suite.py'),
                       '--repo-root', str(root)]
        else:
            command = [sys.executable, str(RUNNER), '--start-directory', str(root / 'tests'),
                       '--pattern', 'test_*.py', '--workers', str(workers)]
            if profile is not None:
                command += ['--module-order', str(profile)]
        result = subprocess.run([*command, '--report-json', str(report)], cwd=root,
            capture_output=True, text=True, encoding='utf-8', timeout=120)
        return result, report

    def complete(self, result, path, names=('test_a', 'test_b', 'test_c')):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(path.is_file())
        report = json.loads(path.read_text(encoding='utf-8'))
        expected = sorted(name + '.T.test_case' for name in names)
        self.assertTrue(report['ok'])
        self.assertEqual(report['tests_run'], len(expected))
        self.assertEqual(report['expected_ids'], expected)
        self.assertEqual(report['executed_ids'], expected)
        self.assertEqual(report['skipped'], [])
        self.assertEqual(report['fixture_omitted_ids'], [])
        return report

    def test_default_order_still_executes_every_discovered_case(self):
        report = self.complete(*self.invoke())
        self.assertEqual([m['module'] for m in report['modules']], ['test_a', 'test_b', 'test_c'])
        for name in ('test_a', 'test_b', 'test_c'):
            self.assertEqual((self.root / (name + '.ran')).read_text(), 'ran\n')

    def test_priorities_reach_real_controller_and_worker_barriers(self):
        for name, other in (('test_b', 'test_c'), ('test_c', 'test_b')):
            self.module(self.root, name,
                'Path(%r).write_text(str(os.getpid()))\n' % (name + '.started') +
                'until=time.monotonic()+10\n'
                'while not Path(%r).exists() and time.monotonic()<until: time.sleep(.01)\n' % (other + '.started') +
                'self.assertTrue(Path(%r).exists(), "other priority job must actually start")' % (other + '.started'))
        self.module(self.root, 'test_a',
            'self.assertTrue(Path("test_b.started").is_file())\n'
            'self.assertTrue(Path("test_c.started").is_file())')
        profile = self.profile(['test_c', 'test_b'])
        report = self.complete(*self.invoke(profile=profile))
        self.assertEqual(report['scheduling']['modules'], ['test_c', 'test_b', 'test_a'])
        self.assertEqual(report['scheduling']['ignored_priorities'], 0)
        self.assertEqual(report['scheduling']['profile_sha256'], hashlib.sha256(profile.read_bytes()).hexdigest())
        self.assertNotEqual((self.root / 'test_b.started').read_text(),
                            (self.root / 'test_c.started').read_text())

    def test_direct_api_preserves_order_and_complete_inventory(self):
        profile = self.profile(['test_b', 'test_c'])
        output = self.area / 'api.json'
        code = ('import json,sys\nfrom pathlib import Path\n'
                'sys.path.insert(0,sys.argv[1])\nfrom run_test_suite import run_suite\n'
                'result=run_suite(sys.argv[2],workers=2,module_order=sys.argv[3])\n'
                'Path(sys.argv[4]).write_text(json.dumps(result),encoding="utf-8")\n')
        process = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT / 'scripts'),
            str(self.root / 'tests'), str(profile), str(output)], cwd=self.root,
            capture_output=True, text=True, encoding='utf-8', timeout=120)
        report = self.complete(process, output)
        self.assertEqual(report['scheduling']['modules'], ['test_b', 'test_c', 'test_a'])

    def test_unknown_priority_is_never_imported_or_executed(self):
        marker = self.root / 'unexpected-import'
        (self.root / 'trap.py').write_text(
            'from pathlib import Path\nPath("unexpected-import").touch()\n', encoding='utf-8')
        report = self.complete(*self.invoke(profile=self.profile(['trap', 'test_b'])))
        self.assertEqual(report['scheduling']['modules'], ['test_b', 'test_a', 'test_c'])
        self.assertEqual(report['scheduling']['ignored_priorities'], 1)
        self.assertFalse(marker.exists())

    def test_invalid_profiles_fail_before_any_case_executes(self):
        variants = [b'{', b'null', b'{}', b'42', b'[true]', b'["test_a","test_a"]',
                    b'["../outside"]', b'[""]', b'["test_a\\nother"]']
        for index, content in enumerate(variants):
            with self.subTest(index=index):
                path = self.root / ('invalid-%d.json' % index); path.write_bytes(content)
                result, _ = self.invoke(profile=path)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('SUITE_ORDER', result.stdout + result.stderr)
                self.assertEqual(list(self.root.glob('*.ran')), [])

    def test_missing_profile_fails_before_any_case_executes(self):
        result, _ = self.invoke(profile=self.root / 'missing.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SUITE_ORDER', result.stdout + result.stderr)
        self.assertEqual(list(self.root.glob('*.ran')), [])

    def test_empty_priority_list_preserves_the_complete_default_order(self):
        report = self.complete(*self.invoke(profile=self.profile([])))
        self.assertEqual(report['scheduling']['modules'], ['test_a','test_b','test_c'])
        self.assertEqual(report['scheduling']['ignored_priorities'], 0)

    def test_load_tests_origin_and_function_case_are_not_lost(self):
        (self.root / 'tests/test_provider.py').write_text(
            'import unittest\nfrom pathlib import Path\n'
            'def behavior(): Path("function-ran").write_text("ran",encoding="utf-8")\n'
            'def load_tests(loader,suite,pattern):\n'
            ' return unittest.TestSuite([unittest.FunctionTestCase(behavior)])\n', encoding='utf-8')
        result, path = self.invoke(profile=self.profile(['test_provider', 'test_c']))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(report['ok'])
        self.assertEqual(report['tests_run'], 4)
        self.assertEqual(report['expected_ids'], report['executed_ids'])
        self.assertEqual(len(set(report['executed_ids'])), 4)
        self.assertEqual(report['scheduling']['modules'], ['test_provider','test_c','test_a','test_b'])
        self.assertEqual((self.root / 'function-ran').read_text(encoding='utf-8'), 'ran')

    def test_nonempty_profile_requires_parallel_workers(self):
        result, _ = self.invoke(profile=self.profile(['test_b']), workers=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SUITE_ORDER', result.stdout + result.stderr)
        self.assertEqual(list(self.root.glob('*.ran')), [])

    def test_failures_and_aborts_remain_failures_with_all_jobs_scheduled(self):
        for mode, body in (('failure', 'self.fail("synthetic failure")'), ('abort', 'os._exit(0)')):
            with self.subTest(mode=mode):
                root = self.project(mode)
                self.module(root, 'test_a', body)
                result, path = self.invoke(root, self.profile(['test_c', 'test_b'], root))
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(path.is_file(), result.stdout + result.stderr)
                report = json.loads(path.read_text(encoding='utf-8'))
                self.assertFalse(report['ok'])
                self.assertTrue(report['failures'] or report['errors'])
                self.assertEqual(report['expected_ids'], sorted(n + '.T.test_case' for n in ('test_a','test_b','test_c')))
                for name in ('test_a','test_b','test_c'):
                    self.assertEqual((root / (name + '.ran')).read_text(), 'ran\n')

    def test_second_invocation_executes_again_with_the_same_ids(self):
        profile = self.profile(['test_c', 'test_a'])
        first = self.complete(*self.invoke(profile=profile))
        second = self.complete(*self.invoke(profile=profile))
        self.assertEqual(first['expected_ids'], second['expected_ids'])
        for name in ('test_a','test_b','test_c'):
            self.assertEqual((self.root / (name + '.ran')).read_text(), 'ran\nran\n')

    def launcher_files(self, root):
        (root / 'scripts').mkdir(exist_ok=True)
        for name in ('init_post_apply_suite.py', 'run_test_suite.py', 'process_tree.py'):
            shutil.copyfile(ROOT / 'scripts' / name, root / 'scripts' / name)

    def test_launcher_without_optional_profile_keeps_the_complete_suite(self):
        self.launcher_files(self.root)
        report = self.complete(*self.invoke(launcher=True))
        self.assertEqual(report['workers'], 8 if os.name == 'nt' else 4)
        self.assertEqual([m['module'] for m in report['modules']], ['test_a','test_b','test_c'])

    def test_invalid_existing_launcher_profile_fails_only_in_windows(self):
        self.launcher_files(self.root)
        target = self.root / PROFILE; target.parent.mkdir(parents=True)
        target.write_text('{ invalid', encoding='utf-8')
        result, path = self.invoke(launcher=True)
        if os.name == 'nt':
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SUITE_ORDER', result.stdout + result.stderr)
            self.assertEqual(list(self.root.glob('*.ran')), [])
        else:
            self.complete(result, path)

    def test_bootstrap_preserves_profile_and_launcher_runs_without_git(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import init_project as initializer
        profile = ROOT / PROFILE
        self.assertTrue(profile.is_file(), 'The measured advisory profile must be shipped')
        names = json.loads(profile.read_text(encoding='utf-8'))[:2]
        self.assertEqual(len(set(names)), 2)
        root = self.project('synthetic template', ('test_000_schedule_control', *names))
        self.launcher_files(root)
        for relative in initializer.MANIFEST:
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic removable template artifact\n', encoding='utf-8')
        for relative, content in (
            ('knowledge/index.md', '---\ntype: Index\ntitle: Fixture\ndescription: Synthetic template\ntags: [test]\n---\n# Fixture\n'),
            ('README.md', '# Synthetic template\n'), ('CHANGELOG.md', '# Changelog\n'),
            ('completion-legacy.json', '{}\n')):
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        workflow = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')
        for old, new in reversed(initializer._PRODUCT_CI_REPLACEMENTS):
            if new in workflow:
                workflow = workflow.replace(new, old)
        path = root / '.github/workflows/validate.yml'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(workflow, encoding='utf-8')
        target = root / PROFILE; target.parent.mkdir(parents=True)
        target.write_bytes(profile.read_bytes())
        result = initializer.init_project(str(root), True, 'Own project', 'ExampleCo/OwnProject')
        self.assertTrue(result['applied'])
        self.assertFalse((root / '.git').exists())
        self.assertEqual(target.read_bytes(), profile.read_bytes())
        report = self.complete(*self.invoke(root, launcher=True), names=('test_000_schedule_control', *names))
        if os.name == 'nt':
            self.assertIn('scheduling', report)
            self.assertEqual(report['scheduling']['modules'], [*names, 'test_000_schedule_control'])
        else:
            self.assertEqual(report['modules'][0]['module'], 'test_000_schedule_control')


if __name__ == '__main__':
    unittest.main()
