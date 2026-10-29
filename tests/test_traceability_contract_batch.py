"""Real Git controls for batching contract paths without changing semantics."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests import test_traceability_model as support
import task_git as journal
from traceability_git import _Projection, build_trace
from validate_contracts import parse_frontmatter


class RealRepository:
    def __init__(self, parent, object_format='sha1'):
        self.root = Path(parent)
        self.root.mkdir(parents=True, exist_ok=True)
        self.git('init', '-q', '-b', 'main', '--object-format=' + object_format)
        for key, value in [('user.name', 'Batch fixture'), ('user.email', 'batch@example.invalid'),
                           ('core.autocrlf', 'false'), ('maintenance.autoDetach', 'false'),
                           ('gc.autoDetach', 'false')]:
            self.git('config', key, value)
        self.oracle = 'tests/test_value.py'
        self.target = 'src/value.py'
        self.contract = 'knowledge/contracts/value.md'
        self.write(self.oracle, 'oracle content\n')
        self.write(self.target, 'target content\n')
        self.write_contract(self.oracle, self.target)
        self.commit('fixture')

    def git(self, *args, input=None):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
            env.pop(name, None)
        result = subprocess.run(['git', '--literal-pathspecs', '-C', str(self.root), *args],
                                input=input, capture_output=True, text=True, encoding='utf-8',
                                env=env, timeout=60)
        if result.returncode:
            raise AssertionError('Git failed: ' + repr(args) + '\n' + result.stderr)
        return result.stdout.strip()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')

    def write_contract(self, oracle, target):
        seal = hashlib.sha256(b'oracle content\n').hexdigest()
        self.write(self.contract, "---\ntype: 'Task Contract'\n"
                   + "tests: '" + oracle + "'\ntarget: '" + target + "'\n"
                   + "test_command: 'python -m unittest tests/test_value.py'\n"
                   + "tests_sha256: '" + seal + "'\n---\n")

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        self.revision = self.git('rev-parse', 'HEAD')

    def link_in_index(self, name):
        oid = self.git('hash-object', '-w', '--stdin', input='outside\n')
        self.git('update-index', '--add', '--cacheinfo', '120000,' + oid + ',' + name)
        self.git('commit', '-qm', 'committed Git link')
        self.revision = self.git('rev-parse', 'HEAD')


def serial_contract(root, revision, name):
    """Existing observable order, deliberately using individual blob reads."""
    projection = _Projection(root, revision, 'quality/traceability.json')
    with journal.object_cache():
        metadata, _ = parse_frontmatter(projection.blob(revision, name))
        oracle = projection.blob(revision, metadata['tests'])
        projection.blob(revision, metadata['target'])
        return metadata, hashlib.sha256(oracle.encode('utf-8')).hexdigest() == metadata['tests_sha256']


def outcome(call):
    try:
        return 'value', call()
    except Exception as error:
        return 'error', type(error).__name__, str(error)


def commands(trace):
    return [event['argv'] for line in trace.read_text(encoding='utf-8').splitlines()
            if (event := json.loads(line)).get('event') == 'start']


def pair_queries(entries, first, second):
    found = []
    for argv in entries:
        if 'ls-tree' not in argv or '--' not in argv:
            continue
        names = argv[argv.index('--') + 1:]
        if set(names) == {first, second} and len(names) == 2:
            found.append(argv)
    return found


def single_path_queries(entries, names):
    return [argv for argv in entries if 'ls-tree' in argv and '--' in argv
            and argv[argv.index('--') + 1:] in [[name] for name in names]]


class ContractPathsRealGit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kdd batch paths ')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.repo = RealRepository(self.area / 'repo')

    def projected(self, repo=None, revision=None):
        repo = repo or self.repo
        revision = revision or repo.revision
        projection = _Projection(repo.root, revision, 'quality/traceability.json')
        with journal.object_cache():
            return projection.contract(revision, repo.contract)

    def assert_serial_equivalence(self, repo=None):
        repo = repo or self.repo
        expected = outcome(lambda: serial_contract(repo.root, repo.revision, repo.contract))
        actual = outcome(lambda: self.projected(repo))
        self.assertEqual(actual, expected)
        return actual

    def test_regular_oracle_and_target_use_one_real_tree_query_in_both_formats(self):
        for fmt in ('sha1', 'sha256'):
            with self.subTest(object_format=fmt):
                repo = RealRepository(self.area / fmt, fmt)
                expected = serial_contract(repo.root, repo.revision, repo.contract)
                before = repo.git('status', '--porcelain=v1')
                trace = self.area / (fmt + '-trace.jsonl')
                with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                    actual = self.projected(repo)
                self.assertEqual(actual, expected)
                self.assertTrue(actual[1])
                entries = commands(trace)
                self.assertEqual(len(pair_queries(entries, repo.oracle, repo.target)), 1,
                                 'both regular paths must share one Git ls-tree process')
                self.assertEqual(single_path_queries(entries, (repo.oracle, repo.target)), [])
                self.assertEqual(repo.git('status', '--porcelain=v1'), before)

    def test_unicode_and_space_paths_keep_values_and_seal(self):
        self.repo.write('tests/prueba ñ.py', 'oracle content\n')
        self.repo.write('src/valor ñ.py', 'other target\n')
        self.repo.write_contract('tests/prueba ñ.py', 'src/valor ñ.py')
        self.repo.commit('unicode paths')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'value')
        self.assertTrue(result[1][1])

    def test_oracle_symlink_and_missing_target_preserve_first_error(self):
        self.repo.write_contract(self.repo.oracle, 'src/missing.py')
        self.repo.commit('missing target')
        self.repo.link_in_index(self.repo.oracle)
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('expected a regular Git blob: tests/test_value.py', result[2])

    def test_missing_oracle_and_target_symlink_preserve_first_error(self):
        self.repo.write_contract('tests/missing.py', self.repo.target)
        self.repo.commit('missing oracle')
        self.repo.link_in_index(self.repo.target)
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('missing regular Git file: tests/missing.py', result[2])

    def test_existing_oracle_and_missing_target_remain_an_error(self):
        self.repo.write_contract(self.repo.oracle, 'src/missing.py')
        self.repo.commit('missing target')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('missing regular Git file: src/missing.py', result[2])

    def test_symlink_target_is_rejected_in_both_object_formats(self):
        for fmt in ('sha1', 'sha256'):
            with self.subTest(object_format=fmt):
                repo = RealRepository(self.area / ('linked-' + fmt), fmt)
                repo.link_in_index(repo.target)
                result = self.assert_serial_equivalence(repo)
                self.assertEqual(result[0], 'error')
                self.assertIn('expected a regular Git blob: src/value.py', result[2])

    def test_directory_and_descendant_do_not_bypass_regular_blob_check(self):
        self.repo.write('bundle/target.py', 'target\n')
        self.repo.write_contract('bundle', 'bundle/target.py')
        self.repo.commit('overlapping paths')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('expected a regular Git blob: bundle', result[2])

    def test_same_oracle_and_target_returns_the_serial_result(self):
        self.repo.write_contract(self.repo.oracle, self.repo.oracle)
        self.repo.commit('duplicate paths')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'value')
        self.assertTrue(result[1][1])

    def test_invalid_target_preserves_serial_error(self):
        self.repo.write_contract(self.repo.oracle, 'src/../escape')
        self.repo.commit('invalid target')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('TRACE_INPUT:', result[2])

    def test_missing_oracle_blob_precedes_missing_target(self):
        self.repo.write_contract(self.repo.oracle, 'src/missing.py')
        self.repo.commit('missing target with valid oracle tree entry')
        oid = self.repo.git('rev-parse', self.repo.revision + ':' + self.repo.oracle)
        object_path = (self.repo.root / '.git' / 'objects' / oid[:2] / oid[2:]).resolve()
        self.assertTrue(object_path.is_relative_to((self.repo.root / '.git' / 'objects').resolve()))
        self.assertTrue(object_path.is_file(), 'fixture must use a loose real Git object')
        object_path.chmod(stat.S_IREAD | stat.S_IWRITE)
        object_path.unlink()
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('TASK_GIT:', result[2])

    def test_git_submodule_mode_is_not_a_regular_target(self):
        self.repo.git('update-index', '--add', '--cacheinfo',
                      '160000,' + self.repo.revision + ',' + self.repo.target)
        self.repo.git('commit', '-qm', 'target with Git submodule mode')
        self.repo.revision = self.repo.git('rev-parse', 'HEAD')
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('expected a regular Git blob: src/value.py', result[2])

    def test_new_revision_cannot_reuse_old_regular_mode(self):
        first = self.repo.revision
        self.assertTrue(self.projected(revision=first)[1])
        self.repo.link_in_index(self.repo.target)
        result = self.assert_serial_equivalence()
        self.assertEqual(result[0], 'error')
        self.assertIn('expected a regular Git blob: src/value.py', result[2])
        self.assertTrue(self.projected(revision=first)[1])

    def test_separate_repositories_do_not_share_projection_state(self):
        other = RealRepository(self.area / 'other')
        other.write(other.oracle, 'different oracle\n')
        other.commit('different bytes')
        with journal.object_cache():
            a = _Projection(self.repo.root, self.repo.revision, 'quality/traceability.json')
            b = _Projection(other.root, other.revision, 'quality/traceability.json')
            self.assertTrue(a.contract(self.repo.revision, self.repo.contract)[1])
            self.assertFalse(b.contract(other.revision, other.contract)[1])


class CompletedTaskIntegration(support.RepositoryFixture):
    def test_completed_task_keeps_real_proof_and_groups_projection_paths(self):
        before = support.git(self.root, 'status', '--porcelain=v1')
        trace = Path(self.temp.name) / 'projection-trace.jsonl'
        with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
            report = build_trace(self.root, 'main', 'quality/traceability.json', require_verified=True)
        self.assertTrue(report['ok'], report['findings'])
        self.assertTrue(report['complete'])
        link = report['requirements'][0]['links'][0]
        self.assertEqual(link['state'], 'verified')
        self.assertEqual(link['tested_commit'], self.refs['tested'])
        self.assertEqual(link['approved_ref'], self.refs['approved'])
        self.assertEqual(support.git(self.root, 'status', '--porcelain=v1'), before)
        self.assertTrue(pair_queries(commands(trace), 'tests/test_value.py', 'src/value.py'),
                        'the real projection must group the oracle and target mode checks')

    def test_moving_main_recomputes_trace_instead_of_reusing_evidence(self):
        first = build_trace(self.root, 'main', 'quality/traceability.json', require_verified=True)
        self.assertTrue(first['complete'])
        support.write(self.root, 'src/value.py', 'def value(item):\n    return 123\n')
        changed = support.commit(self.root, 'change target after task closure')
        second = build_trace(self.root, 'main', 'quality/traceability.json', require_verified=True)
        self.assertEqual(second['observed_commit'], changed)
        self.assertNotEqual(first['observed_commit'], second['observed_commit'])
        self.assertFalse(second['complete'])
        self.assertTrue(any(f['code'] == 'TRACE_STALE' for f in second['findings']))


if __name__ == '__main__':
    unittest.main()
