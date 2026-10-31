"""Real Git regressions for the task journal's complexity reduction."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_task_approval_identity import GitFixture, real_env
import task_git as journal
from task_model import TaskError
from validate_tasks import validate_range, validate_snapshot


ROOT = Path(__file__).resolve().parents[1]


class ExistingBudgets(unittest.TestCase):
    def check_budget(self, contract):
        self.assertTrue((ROOT / 'knowledge/contracts' / (contract + '.md')).is_file())
        self.assertTrue((ROOT / 'scripts/task_git.py').is_file())
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_budgets.py'),
                               str(ROOT / 'knowledge/contracts'), '--repo-root', str(ROOT),
                               '--contract', contract], capture_output=True, text=True,
                              encoding='utf-8', timeout=60, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_journal_budget(self):
        self.check_budget('task-journal')

    def test_committed_artifacts_budget(self):
        self.check_budget('task-committed-artifacts')

    def test_fresh_main_budget(self):
        self.check_budget('task-main-read-budget')


class TaskGitComplexityIntegration(GitFixture):
    def cli(self, project, operation, *args):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
                   KDD_PYTHON=sys.executable)
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts/tasks.py'), '--repo-root',
                               str(project.root), operation, 'TASK-001', *args, '--json'],
                              cwd=project.root, env=env, capture_output=True, text=True,
                              encoding='utf-8', timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_cli_full_lifecycle_records_commits_and_real_evidence(self):
        p = self.project()
        created = self.cli(p, 'create', '--title', 'Real task', '--description', 'Verify lifecycle',
                           '--contract', p.contract)
        ready = self.cli(p, 'ready', '--approved-ref', p.approved)
        started = self.cli(p, 'start', '--assignee', 'developer')
        blocked = self.cli(p, 'block', '--reason', 'Need review')
        resumed = self.cli(p, 'resume', '--reason', 'Review complete')
        restarted = self.cli(p, 'start', '--assignee', 'developer')
        branch_tip = p.git('rev-parse', 'task/TASK-001')
        p.git('switch', '-q', 'task/TASK-001')
        (p.root / 'src/value.py').write_text('def value():\n    return 7 # implementation\n', encoding='utf-8')
        implementation = p.commit('implement task')
        self.assertNotEqual(implementation, branch_tip)
        p.git('switch', '-q', 'main')
        p.git('merge', '--no-ff', '-qm', 'integrate task', 'task/TASK-001')
        integrated = p.git('rev-parse', 'HEAD')
        closed = self.cli(p, 'finish')
        commits = [x['commit'] for x in (created, ready, started, blocked, resumed, restarted, closed)]
        self.assertEqual(len(set(commits)), 7)
        self.assertEqual(closed['task']['status'], 'done')
        self.assertEqual(closed['task']['verified_ref'], integrated)
        self.assertEqual(p.git('rev-parse', 'HEAD^'), integrated)
        report = json.loads((p.root / closed['task']['evidence']).read_text(encoding='utf-8'))
        self.assertEqual(report['tested_commit'], integrated)
        self.assertEqual(report['branch_tip'], implementation)
        self.assertGreater(report['passed_tests'], 0)
        self.assertEqual(validate_snapshot(p.root, 'HEAD'), [])
        self.assertEqual(validate_range(p.root, p.approved, 'HEAD'), [])
        self.assertEqual([x['status'] for x in journal.history(p.root, 'TASK-001')],
                         ['backlog', 'ready', 'in_progress', 'needs_human_input', 'ready',
                          'in_progress', 'done'])
        self.assertEqual(p.git('status', '--porcelain'), '')

    def test_moving_refs_and_immutable_objects_stay_distinct_in_cache(self):
        for algorithm in ('sha1', 'sha256'):
            with self.subTest(algorithm=algorithm):
                p = self.project(algorithm)
                name = 'src/value.py'
                original = p.approved
                with journal.object_cache():
                    old = journal.blobs(p.root, 'main', [name, name])
                    self.assertEqual(list(old), [name])
                    (p.root / name).write_text('def value():\n    return 8\n', encoding='utf-8')
                    newer = p.commit('move main')
                    self.assertEqual(journal.commit_sha(p.root, 'main'), newer)
                    self.assertEqual(journal.commit_sha(p.root, original), original)
                    self.assertEqual(journal.blob(p.root, original, name), old[name])
                    self.assertIn('return 8', journal.blob(p.root, 'main', name))
                    self.assertNotEqual(newer, original)

    def test_rejects_invalid_approved_identity_without_writing(self):
        p = self.project()
        p.act('create')
        before = p.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(TaskError, 'TASK_APPROVAL'):
            p.act('ready', approved_ref='main')
        self.assertEqual(p.git('rev-parse', 'HEAD'), before)
        self.assertEqual(journal.read_tasks(p.root)['TASK-001']['status'], 'backlog')
        self.assertEqual(p.git('status', '--porcelain'), '')

    def test_historical_metadata_rejects_git_symlink_even_when_checkout_is_regular(self):
        p = self.project()
        p.act('create')
        p.act('ready', approved_ref=p.approved)
        task = journal.read_tasks(p.root)['TASK-001']
        original = p.git('rev-parse', 'HEAD:src/value.py')
        p.git('update-index', '--cacheinfo', '120000,' + original + ',src/value.py')
        p.git('commit', '-qm', 'record unsafe Git mode')
        revision = p.git('rev-parse', 'HEAD')
        self.assertTrue((p.root / 'src/value.py').is_file())
        before = p.git('status', '--porcelain')
        with self.assertRaisesRegex(TaskError, 'TASK_PATH'):
            journal.contract_metadata(p.root, task, revision, committed_only=True)
        self.assertEqual(p.git('rev-parse', 'HEAD'), revision)
        self.assertEqual(p.git('status', '--porcelain'), before)

    def test_real_git_commit_hook_failure_rolls_back_task_and_branch(self):
        p = self.project()
        p.act('create')
        p.act('ready', approved_ref=p.approved)
        head = p.git('rev-parse', 'HEAD')
        path = p.root / 'knowledge/tasks/TASK-001.md'
        original = path.read_bytes()
        hook = p.root / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n', encoding='utf-8', newline='\n')
        hook.chmod(0o755)
        with self.assertRaises(TaskError):
            p.act('start', assignee='developer')
        self.assertEqual(p.git('rev-parse', 'HEAD'), head)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(p.git('status', '--porcelain'), '')
        self.assertNotIn('task/TASK-001', p.git('branch', '--format=%(refname:short)').splitlines())
        self.assertFalse((p.root / '.git/kdd-tasks.lock').exists())

    def test_main_checks_remain_fresh_and_use_at_most_two_git_processes(self):
        p = self.project()
        trace = p.root.parent / 'trace.jsonl'
        with real_env({'GIT_TRACE2_EVENT': str(trace)}), journal.object_cache():
            self.assertEqual(journal._clean_main(p.root, p.approved), p.approved)
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()]
        starts = [entry for entry in events if entry.get('event') == 'start']
        self.assertGreaterEqual(len(starts), 1)
        self.assertLessEqual(len(starts), 2)
        (p.root / 'outside.txt').write_text('keep', encoding='utf-8')
        with journal.object_cache(), self.assertRaisesRegex(TaskError, 'TASK_DIRTY'):
            journal._clean_main(p.root, p.approved)
        self.assertEqual((p.root / 'outside.txt').read_text(encoding='utf-8'), 'keep')


if __name__ == '__main__':
    unittest.main()
