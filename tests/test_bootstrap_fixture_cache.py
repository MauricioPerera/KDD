"""Real offline installs and subprocess calls of the frozen cold-start fixture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests import test_bootstrap_cold_start as cold
from tests import test_workflow_syntax as workflow


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/validate_workflows.py'
PROBE = """import hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tests import test_bootstrap_cold_start as cold
case=cold.BootstrapColdStart('test_empty_cache_missing_tool_is_explicit_failure')
case.root=Path(sys.argv[1])
case.area=Path(sys.argv[2])
case.env=dict(os.environ)
try:
    archive,pin=case.reviewed_archive()
except AssertionError as error:
    print(json.dumps(dict(ok=False,error_type=type(error).__name__,message=str(error))))
    raise SystemExit(2)
print(json.dumps(dict(ok=True,archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
"""


class BootstrapFixtureCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary, archive, cls.platform_key, cls.pin = workflow.tool()
        cls.official = archive.read_bytes()
        cls.assertion_binary = binary

    def setUp(self):
        # Keep the extra subprocess level below Git for Windows MAX_PATH.
        self.temp = tempfile.TemporaryDirectory(prefix='kfc ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.home = self.area / 'tmp space'
        self.home.mkdir()
        self.selected = self.area / 'selected archive'
        self.selected.mkdir()
        self.input = self.area / self.pin['archive']
        self.input.write_bytes(self.official)
        self.env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        for key in list(self.env):
            if key.startswith('KDD_ACTIONLINT_') or key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR'):
                self.env.pop(key)
        parts = [p for p in self.env.get('PATH','').split(os.pathsep)
                 if p and not (Path(p) / self.pin['executable']).is_file()]
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.pathsep.join(parts)
        for key in ('TMPDIR','TEMP','TMP'):
            self.env[key] = str(self.home)
        self.assertIsNone(shutil.which(self.pin['executable'], path=self.env['PATH']))
        self.assertFalse(any(k.startswith('KDD_ACTIONLINT_') for k in self.env))

    def command(self, argv, env=None, timeout=300):
        return subprocess.run(argv, cwd=ROOT, env=env or self.env, capture_output=True,
                              text=True, encoding='utf-8', timeout=timeout)

    def install(self):
        p = self.command([sys.executable, '-B', '-X', 'utf8', str(SCRIPT),
                          'install', '--archive', str(self.input)])
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        result = json.loads(p.stdout)
        self.assertTrue(result['ok'])
        expected = self.home / 'kdd-actionlint' / '1.7.12' / self.platform_key
        self.assertEqual(Path(result['binary']).resolve().parent, expected.resolve())
        for field in ('binary','archive'):
            self.assertEqual(hashlib.sha256(Path(result[field]).read_bytes()).hexdigest(),
                             self.pin[field+'_sha256'])
        return result

    def probe(self, env=None):
        return self.command([sys.executable, '-I', '-B', '-X', 'utf8', '-c', PROBE,
                             str(ROOT), str(self.selected)], env=env)

    def assert_selected(self, p):
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        result = json.loads(p.stdout)
        self.assertTrue(result['ok'])
        self.assertEqual(result['sha256'], self.pin['archive_sha256'])
        path = Path(result['archive'])
        self.assertEqual(path.parent.resolve(), self.selected.resolve())
        self.assertEqual(path.read_bytes(), self.official)

    def assert_rejected(self, p):
        self.assertEqual(p.returncode, 2, p.stdout+p.stderr)
        result = json.loads(p.stdout)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'AssertionError')
        self.assertNotEqual(result['message'], '')
        self.assertEqual(list(self.selected.iterdir()), [])

    def copy_tool(self, source, name):
        directory = self.area / name
        directory.mkdir()
        for field in ('binary','archive'):
            shutil.copy2(source[field], directory / Path(source[field]).name)
        return directory

    def test_default_installer_cache_without_exports_is_used(self):
        installed = self.install()
        before = {field:Path(installed[field]).read_bytes() for field in ('binary','archive')}
        self.assert_selected(self.probe())
        self.assertEqual(before, {field:Path(installed[field]).read_bytes() for field in before})

    def test_explicit_archive_has_priority_over_bad_cache_and_binary(self):
        installed = self.install()
        Path(installed['archive']).write_bytes(b'corrupt default archive')
        env = dict(self.env, KDD_ACTIONLINT_ARCHIVE=str(self.input),
                   KDD_ACTIONLINT_BINARY=str(self.area/'missing binary'))
        self.assert_selected(self.probe(env))

    def test_explicit_binary_neighbor_has_priority_over_default_cache(self):
        installed = self.install()
        directory = self.copy_tool(installed, 'explicit tool with spaces')
        Path(installed['archive']).write_bytes(b'corrupt default archive')
        env = dict(self.env, KDD_ACTIONLINT_BINARY=str(directory/self.pin['executable']))
        self.assert_selected(self.probe(env))

    def test_path_binary_neighbor_has_priority_over_default_cache(self):
        installed = self.install()
        directory = self.copy_tool(installed, 'path tool with spaces')
        Path(installed['archive']).write_bytes(b'corrupt default archive')
        env = dict(self.env, PATH=str(directory)+os.pathsep+self.env['PATH'])
        self.assert_selected(self.probe(env))

    def test_corrupt_explicit_archive_cannot_fall_back_to_good_cache(self):
        installed = self.install()
        corrupt = self.area/'explicit corrupt archive'
        corrupt.write_bytes(b'corrupt explicit archive')
        before = Path(installed['archive']).read_bytes()
        self.assert_rejected(self.probe(dict(self.env, KDD_ACTIONLINT_ARCHIVE=str(corrupt))))
        self.assertEqual(Path(installed['archive']).read_bytes(), before)

    def test_missing_default_cache_is_an_explicit_failure(self):
        self.assert_rejected(self.probe())
        self.assertFalse((self.home/'kdd-actionlint').exists())

    def test_corrupt_default_archive_is_not_accepted_or_repaired(self):
        installed = self.install()
        path = Path(installed['archive'])
        path.write_bytes(b'corrupt installed archive')
        self.assert_rejected(self.probe())
        self.assertEqual(path.read_bytes(), b'corrupt installed archive')

    def test_only_the_pinned_version_and_platform_cache_are_considered(self):
        for version, platform in [('0.0.0', self.platform_key), ('1.7.12', 'other_platform')]:
            path = self.home/'kdd-actionlint'/version/platform/self.pin['archive']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.official)
        self.assert_rejected(self.probe())

    @unittest.skipUnless(cold.support.IS_TEMPLATE,
                         'template-only cold bootstrap: project already initialized')
    def test_documented_default_preparation_runs_real_cold_guide_and_27_oracles(self):
        self.install()
        p = self.command([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest',
            'tests.test_bootstrap_cold_start.BootstrapColdStart.test_cold_guide_installs_verified_bytes_and_runs_real_oracles'])
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertRegex(p.stderr, r'Ran 1 test in ')
        self.assertRegex(p.stderr, r'\nOK\s*\Z')
        self.assertNotIn('skipped=', p.stderr)


if __name__ == '__main__':
    unittest.main()
