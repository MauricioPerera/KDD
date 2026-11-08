"""Real Git scope reads: complete unions, bounded queries and safe recovery."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_task_history_read_cost as graph
import task_git as journal
from task_model import TaskError


def state(root):
    return (graph.git(root, 'rev-parse', 'HEAD'), graph.git(root, 'show-ref'),
            graph.git(root, 'status', '--porcelain=v1'),
            (root / '.git/index').read_bytes(), (root / '.git/config').read_bytes())


def commit_stream(number, branch, parent, files, merge=None):
    message = 'perimeter fixture ' + str(number)
    text = ('commit refs/heads/' + branch + '\nmark :' + str(number) +
            '\ncommitter Perimeter <perimeter@example.invalid> ' + str(1700000000 + number) +
            ' +0000\ndata ' + str(len(message.encode('utf-8'))) + '\n' + message + '\n')
    if parent is not None:
        text += 'from :' + str(parent) + '\n'
    if merge is not None:
        text += 'merge :' + str(merge) + '\n'
    for name, content in files:
        name = json.dumps(name, ensure_ascii=False)
        if content is None:
            text += 'D ' + name + '\n'
        else:
            text += 'M 100644 inline ' + name + '\ndata ' + str(len(content.encode('utf-8'))) + '\n' + content + '\n'
    return text + '\n'


class PerimeterStageBatchTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory(prefix='kdd-perimeter-stage-')
        self.addCleanup(self.area.cleanup)
        self.owner = Path(self.area.name).resolve()
        self.sequence = 0

    def repository(self, algorithm, *, product='src/value.py', merge_only=False):
        self.sequence += 1
        root = self.owner / ('repo-' + str(self.sequence))
        root.mkdir()
        graph.git(root, 'init', '-q', '-b', 'main', '--object-format=' + algorithm)
        graph.configure_git(root, {'user.name': 'Perimeter fixture',
                                   'user.email': 'perimeter@example.invalid'}, ephemeral=True)
        marks = self.owner / ('marks-' + str(self.sequence))
        merged = [(product, 'second\n')]
        if merge_only:
            merged.append(('integration-only.txt', 'merge resolution outside permission\n'))
        commands = ''.join([
            commit_stream(1, 'main', None, [('README.txt', 'baseline\n')]),
            commit_stream(2, 'main', 1, [('docs/main-only.txt', 'other work\n')]),
            commit_stream(3, 'task', 1, [(product, 'first\n')]),
            commit_stream(4, 'task', 3, [('outside-transient.txt', 'must remain in scope\n')]),
            commit_stream(5, 'task', 4, [('outside-transient.txt', None), (product, 'second\n')]),
            commit_stream(6, 'main', 2, merged, merge=5),
        ])
        graph.git(root, '-c', 'core.protectNTFS=false', 'fast-import', '--quiet',
                  '--export-marks=' + str(marks), input=commands)
        values = dict(line.split() for line in marks.read_text(encoding='ascii').splitlines())
        # Bad Windows filenames are committed objects, never live NTFS paths.
        graph.git(root, 'checkout', '--detach', '-q', values[':1'])
        refs = dict(base=values[':1'], main=values[':2'], parent=values[':4'],
                    tip=values[':5'], tested=values[':6'])
        refs['tree'] = graph.git(root, 'rev-parse', refs['tip'] + '^{tree}')
        return root, refs

    def observe(self, root, refs):
        self.sequence += 1
        trace = self.owner / ('trace-' + str(self.sequence) + '.jsonl')
        context = journal._PerimeterContext(refs['base'], refs['tip'], refs['tested'])
        with journal.object_cache():
            self.assertTrue(journal._native_oid(root, refs['base']))
            with patch.dict(os.environ, {'GIT_TRACE2_EVENT': str(trace)}):
                result = journal._perimeter_paths(root, context)
        self.assertTrue(trace.is_file(), 'scope validation must execute real Git')
        commands = [record['argv'] for line in trace.read_text(encoding='utf-8-sig').splitlines()
                    if (record := json.loads(line)).get('event') == 'start']
        return result, commands

    def test_linear_scope_reads_use_at_most_two_git_processes_in_both_formats(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                root, refs = self.repository(algorithm)
                before = state(root)
                changed, commands = self.observe(root, refs)
                self.assertEqual(changed, {'src/value.py', 'outside-transient.txt'})
                self.assertEqual(state(root), before)
                self.assertLessEqual(len(commands), 2, commands)

    def test_main_changes_are_excluded_and_merge_and_transient_changes_are_preserved(self):
        product = 'src/with space\ttab\nline-\u00f1.py'
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                root, refs = self.repository(algorithm, product=product, merge_only=True)
                before = state(root)
                changed, _ = self.observe(root, refs)
                self.assertEqual(changed, {product, 'outside-transient.txt', 'integration-only.txt'})
                self.assertNotIn('docs/main-only.txt', changed)
                self.assertEqual(state(root), before)
                with self.assertRaisesRegex(TaskError, 'TASK_PERIMETER: paths outside approved scope'):
                    journal._perimeter_check(dict(touch_only=['src/*'], tests='tests/test_value.py', target=product),
                                             'knowledge/contracts/value.md', changed)

    def test_ambiguous_replacement_is_rejected_and_recovery_is_fresh(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(object_format=algorithm):
                root, refs = self.repository(algorithm)
                replacement = graph.git(root, 'commit-tree', refs['tree'], '-p', refs['parent'],
                                        '-p', refs['main'], '-m', 'ambiguous replacement')
                graph.git(root, 'replace', refs['tip'], replacement)
                before = state(root)
                context = journal._PerimeterContext(refs['base'], refs['tip'], refs['tested'])
                with journal.object_cache():
                    with self.assertRaisesRegex(TaskError, 'TASK_PERIMETER: ambiguous implementation merge'):
                        journal._perimeter_paths(root, context)
                self.assertEqual(state(root), before)
                graph.git(root, 'replace', '-d', refs['tip'])
                before = state(root)
                changed, _ = self.observe(root, refs)
                self.assertEqual(changed, {'src/value.py', 'outside-transient.txt'})
                self.assertEqual(state(root), before)
