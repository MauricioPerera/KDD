"""Real native commit identities and immutable approval boundaries."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'tests')]
from test_task_git import Repository
import task_git as journal
from task_model import TaskError,render_task
from validate_tasks import validate_range,validate_snapshot

@contextmanager
def real_env(values):
    before={key:os.environ.get(key) for key in values}
    os.environ.update(values)
    try:yield
    finally:
        for key,value in before.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value

class GitFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seeds={}
        for algorithm in ['sha1','sha256']:
            with real_env({'GIT_DEFAULT_HASH':algorithm}):seed=Repository()
            assert seed.root.resolve().parent==Path(tempfile.gettempdir()).resolve()
            cls.addClassCleanup(seed.close)
            cls.seeds[algorithm]=seed

    def project(self,algorithm='sha1'):
        area=tempfile.TemporaryDirectory(prefix='kdd-approval-identity-')
        self.addCleanup(area.cleanup)
        root=Path(area.name)/'repo'
        seed=self.seeds[algorithm]
        def git(*args):
            return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE,
                timeout=30).decode('utf-8').strip()
        subprocess.run(['git','-c','core.autocrlf=false','clone','-q','--no-hardlinks',str(seed.root),str(root)],
            capture_output=True,check=True,timeout=30)
        root=root.resolve()
        for name,value in [('user.name','KDD identity fixture'),('user.email','identity@example.invalid'),
                ('core.autocrlf','false'),('maintenance.autoDetach','false'),('gc.autoDetach','false')]:git('config',name,value)
        def commit(message):
            git('add','-A');git('commit','-qm',message);return git('rev-parse','HEAD')
        def act(operation,**options):
            base=dict(title='Identity task',description='Real approved identity',contract=seed.contract,depends_on=[])
            return journal.mutate(root,operation,'TASK-001',base|options)
        return SimpleNamespace(root=root,approved=seed.approved,contract=seed.contract,
            git=git,commit=commit,act=act,algorithm=algorithm)

    def created(self,algorithm='sha1'):
        p=self.project(algorithm);p.act('create');return p

    def alias(self,p):
        value='f'*(64 if p.algorithm=='sha1' else 40)
        p.git('update-ref','refs/heads/'+value,p.approved)
        return value

    def rejected(self,p,reference):
        before=p.git('rev-parse','HEAD')
        branches=p.git('for-each-ref','--format=%(refname)','refs/heads')
        with self.assertRaisesRegex(TaskError,'TASK_APPROVAL'):
            p.act('ready',approved_ref=reference)
        self.assertEqual(p.git('rev-parse','HEAD'),before)
        self.assertEqual(p.git('for-each-ref','--format=%(refname)','refs/heads'),branches)
        self.assertEqual(journal.read_tasks(p.root)['TASK-001']['status'],'backlog')
        self.assertEqual(p.git('status','--porcelain'),'')

    def finish_valid(self,p):
        p.act('ready',approved_ref=p.approved)
        p.act('start',assignee='developer')
        p.git('switch','-q','task/TASK-001')
        (p.root/'src/value.py').write_text('def value():\n return 7 # actual implementation\n',encoding='utf-8')
        p.commit('implement approved product')
        p.git('switch','-q','main');p.git('merge','--no-ff','-qm','integrate task','task/TASK-001')
        return p.act('finish')

class ApprovalIdentity(GitFixture):
    def test_rejects_sha256_width_branch_in_sha1_before_commit(self):
        p=self.created();self.rejected(p,self.alias(p))

    def test_rejects_sha1_width_branch_in_sha256_before_commit(self):
        p=self.created('sha256');self.rejected(p,self.alias(p))

    def test_accepts_native_sha1_commit(self):
        p=self.created();r=p.act('ready',approved_ref=p.approved)
        self.assertEqual(r['task']['approved_ref'],p.approved)
        self.assertEqual(r['task']['status'],'ready')

    def test_accepts_native_sha256_commit(self):
        p=self.created('sha256');r=p.act('ready',approved_ref=p.approved)
        self.assertEqual(len(r['task']['approved_ref']),64)
        self.assertEqual(r['task']['approved_ref'],p.approved)

    def test_rejects_annotated_tag_oid_sha1(self):
        p=self.created();p.git('tag','-a','review','-m','tag identity',p.approved)
        self.rejected(p,p.git('rev-parse','review'))

    def test_rejects_annotated_tag_oid_sha256(self):
        p=self.created('sha256');p.git('tag','-a','review','-m','tag identity',p.approved)
        self.rejected(p,p.git('rev-parse','review'))

    def test_rejects_native_tree_oid(self):
        p=self.created();self.rejected(p,p.git('rev-parse',p.approved+'^{tree}'))

    def test_rejects_abbreviated_and_symbolic_names(self):
        p=self.created()
        for reference in [p.approved[:12],'HEAD','main']:
            with self.subTest(reference=reference):self.rejected(p,reference)

    def test_rejects_missing_commit(self):
        p=self.created();self.rejected(p,'a'*40)

    def test_rejects_nonancestor_commit(self):
        p=self.created();tree=p.git('rev-parse',p.approved+'^{tree}')
        reference=p.git('commit-tree',tree,'-m','independent history')
        self.rejected(p,reference)

    def malformed_ready(self,algorithm):
        p=self.created(algorithm)
        data,body=journal.read_nodes(p.root)['TASK-001']
        data.update(status='ready',approved_ref=self.alias(p),reason='synthetic legacy alias')
        (p.root/'knowledge/tasks/TASK-001.md').write_text(render_task(data,body),encoding='utf-8')
        p.commit('malformed legacy ready')
        self.assertTrue(any('TASK_APPROVAL' in finding for finding in validate_snapshot(p.root,'main')))
        return p

    def test_snapshot_rejects_persisted_ready_alias_sha1(self):self.malformed_ready('sha1')
    def test_snapshot_rejects_persisted_ready_alias_sha256(self):self.malformed_ready('sha256')

    def test_start_rejects_persisted_mobile_approval_without_branch(self):
        p=self.created();data,body=journal.read_nodes(p.root)['TASK-001']
        data.update(status='ready',approved_ref=self.alias(p),reason='legacy alias')
        (p.root/'knowledge/tasks/TASK-001.md').write_text(render_task(data,body),encoding='utf-8')
        before=p.commit('legacy node')
        with self.assertRaisesRegex(TaskError,'TASK_APPROVAL'):p.act('start',assignee='developer')
        self.assertEqual(p.git('rev-parse','HEAD'),before)
        self.assertNotIn('refs/heads/task/TASK-001',p.git('for-each-ref','--format=%(refname)'))

    def test_done_snapshot_rejects_consistently_resealed_mobile_approval(self):
        p=self.created();done=self.finish_valid(p);alias=self.alias(p)
        data,body=journal.read_nodes(p.root)['TASK-001']
        file=p.root/data['evidence'];evidence=json.loads(file.read_text(encoding='utf-8'))
        evidence['approved_ref']=alias
        content=json.dumps(evidence,sort_keys=True,indent=2)+'\n';file.write_text(content,encoding='utf-8')
        data.update(approved_ref=alias,evidence_sha256=hashlib.sha256(content.encode()).hexdigest())
        (p.root/'knowledge/tasks/TASK-001.md').write_text(render_task(data,body),encoding='utf-8')
        p.commit('coherent but invalid legacy approval')
        self.assertEqual(done['task']['status'],'done')
        self.assertTrue(any('TASK_APPROVAL' in f for f in validate_snapshot(p.root,'main')))

    def test_complete_flow_sha1_keeps_approved_oid_and_history(self):
        p=self.created();done=self.finish_valid(p)
        self.assertEqual(done['task']['approved_ref'],p.approved)
        self.assertEqual(validate_range(p.root,p.approved,'main'),[])
        self.assertGreater(json.loads((p.root/done['task']['evidence']).read_text())['passed_tests'],0)

    def test_complete_flow_sha256_keeps_approved_oid_and_history(self):
        p=self.created('sha256');done=self.finish_valid(p)
        self.assertEqual(done['task']['status'],'done')
        self.assertEqual(len(done['commit']),64)
        self.assertEqual(validate_range(p.root,p.approved,'main'),[])

if __name__=='__main__':unittest.main()
