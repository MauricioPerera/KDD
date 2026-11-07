"""Windows PATH precedence and a real child Git history without global edits."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_runtime_oracle', ROOT / 'scripts/validation_runtime.py')
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class ValidationNativeGitPath(unittest.TestCase):
    def installation(self, owner, layout):
        home = owner / 'installed Git-\u00f1' / 'Git'
        for relative in ('cmd/git.exe', layout + '/bin/git.exe'):
            path = home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'existing executable path fixture')
        return home

    def test_windows_selected_direct_layout_is_preserved_without_processes_or_mutation(self):
        for layout in ('ucrt64', 'mingw64'):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as directory:
                home = self.installation(Path(directory), layout)
                direct = str(home / layout / 'bin')
                supplied = {'ProgramFiles': str(home.parent), 'Path': direct + ';' + str(home / 'cmd')}
                original = dict(supplied)
                observed = []
                # A separate real Python process hosts the audit hook so it cannot
                # observe or interfere with another test's subprocesses.
                probe = ('import importlib.util,json,sys; '
                         's=importlib.util.spec_from_file_location("r",sys.argv[1]); '
                         'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                         'events=[]; sys.addaudithook(lambda e,a: events.append(e) if e=="subprocess.Popen" else None); '
                         'env=json.loads(sys.argv[2]); before=dict(env); '
                         'result=m.runtime_environment(env,platform="nt"); '
                         'print(json.dumps(dict(result=result,unchanged=env==before,events=events)))')
                result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe,
                    str(ROOT / 'scripts/validation_runtime.py'), json.dumps(supplied)],
                    capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['result']['PATH'], supplied['Path'])
                self.assertTrue(report['unchanged'])
                self.assertEqual(report['events'], observed)
                self.assertEqual(supplied, original)

    def test_windows_first_git_and_missing_companion_keep_historical_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            area = Path(directory)
            home = self.installation(area, 'ucrt64')
            earlier = area / 'earlier Git'
            earlier.mkdir()
            (earlier / 'git.exe').write_bytes(b'earlier executable fixture')
            direct = str(home / 'ucrt64/bin')
            env = {'PROGRAMFILES': str(home.parent), 'PATH': str(earlier) + ';' + direct}
            self.assertEqual(runtime.runtime_environment(env, platform='nt')['PATH'].split(';')[0], str(home / 'cmd'))
            (home / 'cmd/git.exe').unlink()
            self.assertEqual(runtime.runtime_environment(env, platform='nt')['PATH'], env['PATH'])
            self.assertEqual(runtime.runtime_environment(env, platform='posix'), env)

    def test_real_selected_git_child_preserves_version_commits_and_external_state(self):
        with tempfile.TemporaryDirectory(prefix='kdd-runtime-child-') as directory:
            area = Path(directory)
            before = dict(os.environ)
            executable = Path(shutil.which('git')).resolve()
            if os.name == 'nt':
                home = executable.parent.parent if executable.parent.name.lower() in ('cmd', 'bin') else executable.parents[2]
                candidates = [home / layout / 'bin/git.exe' for layout in ('ucrt64', 'mingw64')]
                executable = next((path for path in candidates if path.is_file()), executable)
            env = dict(os.environ, PATH=str(executable.parent) + os.pathsep + os.environ['PATH'])
            prepared = runtime.runtime_environment(env)
            selected = Path(shutil.which('git', path=prepared['PATH'])).resolve()
            self.assertEqual(selected, executable)
            self.assertEqual(subprocess.check_output([str(selected), '--version']),
                             subprocess.check_output([str(executable), '--version']))
            global_config = area / 'global-canary'
            global_config.write_text('[user]\n name = Outside sentinel\n', encoding='utf-8')
            canary = global_config.read_bytes(), global_config.stat().st_mtime_ns
            prepared.update(GIT_CONFIG_GLOBAL=str(global_config), GIT_CONFIG_NOSYSTEM='1',
                GIT_AUTHOR_NAME='Runtime child', GIT_AUTHOR_EMAIL='runtime@example.invalid',
                GIT_COMMITTER_NAME='Runtime child', GIT_COMMITTER_EMAIL='runtime@example.invalid')
            child = ('import subprocess,sys; from pathlib import Path; '
                'git=sys.argv[1]; subprocess.run([git,"init","-q","-b","main"],check=True); '
                'Path("value.txt").write_text("real history\\n"); '
                'subprocess.run([git,"add","value.txt"],check=True); '
                'subprocess.run([git,"-c","commit.gpgsign=false","commit","-qm","real child commit"],check=True); '
                'subprocess.run([git,"cat-file","-e","HEAD:value.txt"],check=True); sys.exit(7)')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', child, str(selected)],
                cwd=area, env=prepared, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 7, result.stderr.decode('utf-8', errors='replace'))
            self.assertEqual((global_config.read_bytes(), global_config.stat().st_mtime_ns), canary)
            self.assertEqual(dict(os.environ), before)


if __name__ == '__main__':
    unittest.main()
