"""Real Git controls for missing objects behind two regular contract paths."""
from functools import partial
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests import test_traceability_contract_batch as support
import task_git as journal
from traceability_git import _Projection


class ContractMissingBlobs(unittest.TestCase):
    def _grouped(self, repo):
        projection = _Projection(repo.root, repo.revision, 'quality/traceability.json')
        with journal.object_cache():
            return projection.contract(repo.revision, repo.contract)

    def _check_missing(self, missing, expected):
        for object_format in ('sha1', 'sha256'):
            with self.subTest(object_format=object_format), TemporaryDirectory(
                prefix='kdd missing blobs ',
            ) as area:
                root = Path(area)
                repo = support.RealRepository(root / 'repo', object_format)
                paths = (repo.oracle, repo.target)
                oids = {
                    name: repo.git('rev-parse', repo.revision + ':' + name)
                    for name in paths
                }
                self.assertEqual(len(set(oids.values())), 2)
                tree_args = ('ls-tree', '-z', repo.revision, '--', *paths)
                regular_entries = {
                    f'100644 blob {oid}\t{name}' for name, oid in oids.items()
                }
                self.assertEqual(set(repo.git(*tree_args).strip('\0').split('\0')),
                                 regular_entries)
                serial = partial(support.serial_contract, repo.root, repo.revision, repo.contract)
                baseline = serial()
                self.assertTrue(baseline[1])
                self.assertEqual(self._grouped(repo), baseline)

                object_root = (repo.root / '.git' / 'objects').resolve()
                missing_paths = {getattr(repo, role) for role in missing}
                for name, oid in oids.items():
                    loose = (object_root / oid[:2] / oid[2:]).resolve()
                    self.assertTrue(loose.is_relative_to(object_root))
                    self.assertTrue(loose.is_file())
                    if name in missing_paths:
                        loose.chmod(stat.S_IREAD | stat.S_IWRITE)
                        loose.unlink()

                self.assertEqual(set(repo.git(*tree_args).strip('\0').split('\0')),
                                 regular_entries)
                error = ('error', 'TaskError',
                         'TASK_GIT: missing or invalid blob: ' + getattr(repo, expected))
                self.assertEqual(support.outcome(serial), error)
                trace = root / 'grouped-trace.jsonl'
                with patch.dict('os.environ', {'GIT_TRACE2_EVENT': str(trace)}):
                    self.assertEqual(support.outcome(lambda: self._grouped(repo)), error)
                commands = support.commands(trace)
                self.assertEqual(len(support.pair_queries(commands, *paths)), 1)
                self.assertEqual(support.single_path_queries(commands, paths), [])

    def test_missing_oracle_blob_preserves_error(self):
        self._check_missing(('oracle',), 'oracle')

    def test_missing_target_blob_preserves_error(self):
        self._check_missing(('target',), 'target')

    def test_missing_both_blobs_reports_oracle_first(self):
        self._check_missing(('oracle', 'target'), 'oracle')
