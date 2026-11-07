"""Real existing fixture setup, Git children and independent clone mutations."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIMPLE = (
    ('test_baseline_git_batch', 'BaselineGitBatchTests'),
    ('test_baseline_inventory_batch', 'BatchInventoryIntegration'),
    ('test_ci_trusted_execution', 'TrustedExecution'),
    ('test_git_reader_ref_cache', 'GitReaderRefCache'),
    ('test_group_contracts', 'GroupContractsIntegration'),
    ('test_guard_pr_baseline', 'TestTrustedPrBaseline'),
    ('test_trusted_change_review', 'TrustedChangeReview'),
    ('test_verify_quality', 'QualityApproval'),
    ('test_verify_quality_complexity', 'QualityIntegration'),
)


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
        stderr=subprocess.PIPE, timeout=30).decode('utf-8').strip()


def _settings(root):
    raw = _git(root, 'config', '--local', '--null', '--list')
    return dict(part.split('\n', 1) for part in raw.split('\0') if '\n' in part)


def _setters(events):
    return [args for args in events if isinstance(args, (list, tuple))
            and Path(args[0]).name.lower() in ('git', 'git.exe')
            and 'config' in args and not any(str(arg).startswith('--') for arg in args[args.index('config') + 1:])]


def _identity(root):
    return dict(head=_git(root, 'rev-parse', 'HEAD'),
                refs=_git(root, 'for-each-ref', '--format=%(refname) %(objectname)'),
                config=(root / '.git/config').read_bytes().hex(),
                files={path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in root.rglob('*') if path.is_file() and '.git' not in path.relative_to(root).parts})


def _probe(kind, area):
    sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
    observed = []
    sys.addaudithook(lambda event, args: observed.append(args[1]) if event == 'subprocess.Popen' else None)
    trace = area / 'git-trace.jsonl'
    global_config = area / 'external.gitconfig'
    global_config.write_text('[user]\n name = External sentinel\n email = external@example.invalid\n', encoding='utf-8')
    before = global_config.read_bytes(), global_config.stat().st_mtime_ns
    os.environ.update(GIT_CONFIG_GLOBAL=str(global_config), GIT_CONFIG_NOSYSTEM='1',
                      GIT_TRACE2_EVENT=str(trace), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
        os.environ.pop(key, None)
    rows = []
    if kind == 'simple':
        for module_name, name in SIMPLE:
            case = getattr(importlib.import_module('tests.' + module_name), name)()
            start = len(observed)
            try:
                case.setUp()
                root = Path(getattr(case, 'repo', None) or case.root)
                setters = _setters(observed[start:])
                settings = _settings(root)
                rows.append(dict(fixture=module_name, setters=setters, settings=settings,
                                 gitdir_regular=(root / '.git').is_dir()))
            finally:
                try:
                    case.tearDown()
                finally:
                    case.doCleanups()
        identity = importlib.import_module('tests.test_task_approval_identity')
        cls = identity.GitFixture
        case = cls()
        cls.setUpClass()
        try:
            start = len(observed)
            project = case.project()
            setters = _setters(observed[start:])
            rows.append(dict(fixture='test_task_approval_identity', setters=setters,
                             settings=_settings(project.root), gitdir_regular=(project.root / '.git').is_dir()))
        finally:
            case.doCleanups()
            cls.doClassCleanups()
    else:
        support = importlib.import_module('tests.test_traceability_model')
        cls = support.RepositoryFixture
        cls.setUpClass()
        cases = []
        try:
            for _ in range(2):
                case = cls()
                cases.append(case)
                start = len(observed)
                case.setUp()
                rows.append(dict(fixture='trace-clone', setters=_setters(observed[start:]),
                                 settings=_settings(case.root)))
            source_before, sibling_before = _identity(cls.base), _identity(cases[1].root)
            first = cases[0].root
            _git(first, 'config', 'user.name', 'Changed clone only')
            (first / 'private.txt').write_text('private real commit\n', encoding='utf-8')
            _git(first, 'add', 'private.txt')
            _git(first, 'commit', '-qm', 'independent mutation')
            _git(first, 'branch', 'private-branch')
            rows.append(dict(fixture='isolation', source_unchanged=_identity(cls.base) == source_before,
                             sibling_unchanged=_identity(cases[1].root) == sibling_before,
                             own_commit=_git(first, 'rev-parse', 'HEAD') != source_before['head'],
                             own_branch='private-branch' in _git(first, 'branch', '--list')))
        finally:
            for case in reversed(cases):
                case.doCleanups()
            cls.doClassCleanups()
    events = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
    maintenance = [row.get('name') for row in events if row.get('event') == 'cmd_name'
                   and row.get('name') in ('maintenance', 'gc')]
    return dict(rows=rows, maintenance=maintenance,
                external_unchanged=(global_config.read_bytes(), global_config.stat().st_mtime_ns) == before)


class PostinitFixtureConfig(unittest.TestCase):
    def probe(self, kind):
        with tempfile.TemporaryDirectory(prefix='kdd-prep-probe-') as directory:
            report = Path(directory) / 'report.json'
            result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                '--probe', kind, directory, str(report)], cwd=ROOT,
                capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode('utf-8', errors='replace'))
            return json.loads(report.read_text(encoding='utf-8'))

    def test_existing_fresh_setups_have_no_git_setters_or_automatic_maintenance(self):
        report = self.probe('simple')
        self.assertEqual(len(report['rows']), len(SIMPLE) + 1)
        for row in report['rows']:
            with self.subTest(fixture=row['fixture']):
                self.assertEqual(row['setters'], [])
                self.assertEqual(row['settings'].get('maintenance.auto'), 'false')
                self.assertEqual(row['settings'].get('gc.auto'), '0')
                self.assertTrue(row['gitdir_regular'])
        self.assertEqual(report['maintenance'], [])
        self.assertTrue(report['external_unchanged'])

    def test_trace_clones_keep_real_history_and_independent_config_refs_and_files(self):
        report = self.probe('trace')
        self.assertEqual(len(report['rows']), 3)
        for row in report['rows'][:2]:
            with self.subTest(clone=row['fixture']):
                self.assertEqual(row['setters'], [])
                self.assertEqual(row['settings'].get('user.name'), 'Trace case')
                self.assertEqual(row['settings'].get('user.email'), 'trace@example.invalid')
                self.assertEqual(row['settings'].get('maintenance.auto'), 'false')
                self.assertEqual(row['settings'].get('gc.auto'), '0')
        for name in ('source_unchanged', 'sibling_unchanged', 'own_commit', 'own_branch'):
            self.assertTrue(report['rows'][2][name], name)
        self.assertEqual(report['maintenance'], [])
        self.assertTrue(report['external_unchanged'])


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--probe':
        Path(sys.argv[4]).write_text(json.dumps(_probe(sys.argv[2], Path(sys.argv[3]))), encoding='utf-8')
    else:
        unittest.main()
