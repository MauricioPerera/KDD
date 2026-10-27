"""Trace2 process budgets and fresh main preconditions with actual Git."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_task_approval_identity import GitFixture
import task_git as journal
from task_model import TaskError

class MainReadBudget(GitFixture):
    def test_twelve_fresh_checks_use_at_most_twenty_four_git_processes(self):
        p=self.project();trace=p.root.parent/'trace.jsonl'
        with patch.dict(os.environ,{'GIT_TRACE2_EVENT':str(trace)}),journal.object_cache():
            for _ in range(12):self.assertEqual(journal._clean_main(p.root),p.approved)
        starts=[json.loads(line) for line in trace.read_text(encoding='utf-8-sig').splitlines()
                if json.loads(line).get('event')=='start']
        self.assertTrue(starts)
        self.assertLessEqual(len(starts),24,'each main precondition check must stay fresh with <=2 Git processes')
        self.assertGreaterEqual(len(starts),12,'main checks must not be cached between calls')

    def test_sha256_head_and_upstream_metadata_are_preserved(self):
        p=self.project('sha256')
        self.assertEqual(len(journal._clean_main(p.root)),64)
        self.assertEqual(journal._clean_main(p.root,p.approved),p.approved)

    def dirty(self,kind):
        p=self.project()
        with journal.object_cache():
            self.assertEqual(journal._clean_main(p.root),p.approved)
            file=p.root/('untracked name with space [x].txt' if kind=='untracked' else 'src/value.py')
            file.write_text('preserve these user bytes\n',encoding='utf-8')
            if kind=='staged':p.git('add','--',str(file))
            before=file.read_bytes()
            with self.assertRaisesRegex(TaskError,'TASK_DIRTY'):journal._clean_main(p.root)
            self.assertEqual(file.read_bytes(),before)
        self.assertEqual(p.git('rev-parse','HEAD'),p.approved)

    def test_detects_fresh_unstaged_content(self):self.dirty('unstaged')
    def test_detects_fresh_staged_content(self):self.dirty('staged')
    def test_detects_fresh_untracked_names(self):self.dirty('untracked')

    def test_rejects_subdirectory_without_changing_files(self):
        p=self.project()
        with self.assertRaisesRegex(TaskError,'TASK_MAIN'):journal._clean_main(p.root/'src')
        self.assertEqual(p.git('status','--porcelain'),'')

    def test_rejects_other_branch_and_detached_head(self):
        p=self.project();p.git('switch','-qc','work')
        with self.assertRaisesRegex(TaskError,'TASK_MAIN'):journal._clean_main(p.root)
        p.git('switch','-q','--detach',p.approved)
        with self.assertRaisesRegex(TaskError,'TASK_MAIN'):journal._clean_main(p.root)
        self.assertEqual(p.git('rev-parse','HEAD'),p.approved)

    def test_expected_head_is_rechecked_after_an_external_commit(self):
        p=self.project()
        with journal.object_cache():
            self.assertEqual(journal._clean_main(p.root,p.approved),p.approved)
            (p.root/'src/value.py').write_text('def value(): return 8\n',encoding='utf-8')
            next_head=p.commit('external implementation commit')
            with self.assertRaisesRegex(TaskError,'TASK_RACE'):journal._clean_main(p.root,p.approved)
            self.assertEqual(journal._clean_main(p.root,next_head),next_head)

if __name__=='__main__':unittest.main()
