"""Real SHA-1/SHA-256 graphs bind every approved field to its own OID."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests import test_mutation_control_evidence as support
from tests.test_fixture_preparation import configure_git

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import approval_registry as registry
from validate_baseline import validate_all_baselines


def command(root,*args):
    result=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,
        encoding='utf-8',env=dict(os.environ,GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1'),timeout=30)
    if result.returncode:raise RuntimeError('Git fixture precondition failed: '+repr(args)+'\n'+result.stderr)
    return result.stdout.strip()


class ApprovedRefIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graphs={}
        for algorithm in ['sha1','sha256']:
            fixture=support.MutationControls('test_broken_original_import_rejects_before_mutants')
            cls.addClassCleanup(fixture.doCleanups)
            root,contract,_=fixture.project()
            command(root,'init','-q','-b','main','--object-format='+algorithm)
            configure_git(root,{'user.name':'Approval fixture','user.email':'fixture@example.invalid',
                'maintenance.autoDetach':'false','gc.autoDetach':'false','core.autocrlf':'false','commit.gpgsign':'false'})
            command(root,'add','-A');command(root,'commit','-qm','Reviewed fixture A')
            approved=command(root,'rev-parse','HEAD')
            oracle=support.STRONG.replace('self.assertTrue(accept(1))','self.assertFalse(accept(1))')
            (root/'tests/test_app.py').write_text(oracle,encoding='utf-8')
            (root/'src/app.py').write_text('def accept(value):\n return False\n',encoding='utf-8')
            text=contract.read_text(encoding='utf-8').replace(hashlib.sha256(support.STRONG.encode()).hexdigest(),hashlib.sha256(oracle.encode()).hexdigest())
            contract.write_text(text,encoding='utf-8')
            command(root,'add','-A');command(root,'commit','-qm','Candidate B changes oracle')
            candidate=command(root,'rev-parse','HEAD')
            command(root,'tag','-a','review-label','-m','Annotated tag',approved)
            cls.graphs[algorithm]={'root':root,'approved':approved,'candidate':candidate,
                'tree':command(root,'rev-parse','HEAD^{tree}'),'tag':command(root,'rev-parse','review-label'),
                'blob':command(root,'rev-parse','HEAD:src/app.py')}

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kdd canonical approval ')
        self.addCleanup(self.temp.cleanup);self.area=Path(self.temp.name).resolve();self.number=0
        env=dict(os.environ,PYTHONUTF8='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_NOSYSTEM='1')
        for key in ['GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE','GIT_COMMON_DIR']:env.pop(key,None)
        settings=patch.dict(os.environ,env,clear=True);settings.start();self.addCleanup(settings.stop)

    def clone(self,algorithm):
        self.number+=1;root=self.area/str(self.number)
        command(self.area,'clone','-q','--shared','--branch','main',str(self.graphs[algorithm]['root']),str(root))
        return root,self.graphs[algorithm]

    def select(self,root,graph,mode,field,value,candidate=None):
        row={'baseline_ref':graph['approved'],'quality_ref':graph['approved']};row[field]=value
        if mode=='registry':
            raw=json.dumps({'schema_version':1,'trees':{graph['tree']:row}},sort_keys=True)
            return registry.resolve(root,candidate or graph['candidate'],raw,require_quality=True)
        return registry.resolve(root,candidate or graph['candidate'],'',
            explicit_baseline=row['baseline_ref'],explicit_quality=row['quality_ref'],require_quality=True)

    def aliases(self,mode,field,native=False):
        for algorithm in ['sha1','sha256']:
            with self.subTest(algorithm=algorithm,mode=mode,field=field,native=native):
                root,graph=self.clone(algorithm)
                width=len(graph['approved']) if native else (64 if algorithm=='sha1' else 40)
                alias='e'*width
                outcomes=[]
                for ref in [graph['approved'],graph['candidate']]:
                    command(root,'update-ref','refs/heads/'+alias,ref)
                    try:self.select(root,graph,mode,field,alias)
                    except registry.ApprovalError:outcomes.append('REJECT')
                    else:outcomes.append('ACCEPT')
                self.assertEqual(outcomes,['REJECT','REJECT'],'the same approved text must never track a movable branch')

    def test_registry_baseline_rejects_cross_format_hex_branch_before_and_after_move(self):self.aliases('registry','baseline_ref')
    def test_registry_quality_rejects_cross_format_hex_branch_before_and_after_move(self):self.aliases('registry','quality_ref')
    def test_explicit_baseline_rejects_cross_format_hex_branch_before_and_after_move(self):self.aliases('explicit','baseline_ref')
    def test_explicit_quality_rejects_cross_format_hex_branch_before_and_after_move(self):self.aliases('explicit','quality_ref')
    def test_registry_baseline_rejects_native_width_hex_branch_without_oid(self):self.aliases('registry','baseline_ref',True)
    def test_registry_quality_rejects_native_width_hex_branch_without_oid(self):self.aliases('registry','quality_ref',True)
    def test_explicit_baseline_rejects_native_width_hex_branch_without_oid(self):self.aliases('explicit','baseline_ref',True)
    def test_explicit_quality_rejects_native_width_hex_branch_without_oid(self):self.aliases('explicit','quality_ref',True)

    def test_real_native_commit_approvals_remain_valid_in_both_modes(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm)
            for mode in ['registry','explicit']:
                result=self.select(root,graph,mode,'baseline_ref',graph['approved'])
                self.assertEqual(result['baseline_ref'],graph['approved']);self.assertEqual(result['quality_ref'],graph['approved'])

    def test_uppercase_native_oids_normalize_without_becoming_aliases(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm)
            result=self.select(root,graph,'registry','baseline_ref',graph['approved'].upper())
            self.assertEqual(result['baseline_ref'],graph['approved'])

    def test_head_and_fetch_head_are_allowed_only_as_candidate_context(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm)
            command(root,'fetch','-q',str(graph['root']),'main')
            for context in ['HEAD','FETCH_HEAD']:
                result=self.select(root,graph,'registry','baseline_ref',graph['approved'],context)
                self.assertEqual(result['candidate_commit'],graph['candidate'])

    def test_tree_blob_and_annotated_tag_cannot_approve(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm)
            for kind in ['tree','blob','tag']:
                with self.subTest(algorithm=algorithm,kind=kind),self.assertRaises(registry.ApprovalError):
                    self.select(root,graph,'registry','baseline_ref',graph[kind])

    def test_missing_commit_and_abbreviation_cannot_approve(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm)
            for value in ['0'*len(graph['approved']),graph['approved'][:12]]:
                with self.subTest(algorithm=algorithm,value=value),self.assertRaises(registry.ApprovalError):
                    self.select(root,graph,'explicit','quality_ref',value)

    def test_canonical_baseline_keeps_rejecting_changed_oracle_after_alias_move(self):
        for algorithm in ['sha1','sha256']:
            root,graph=self.clone(algorithm);alias='d'*(64 if algorithm=='sha1' else 40)
            for ref in [graph['approved'],graph['candidate']]:
                command(root,'update-ref','refs/heads/'+alias,ref)
                selected=self.select(root,graph,'registry','baseline_ref',graph['approved'])
                self.assertEqual(selected['baseline_ref'],graph['approved'])
                self.assertTrue(validate_all_baselines(selected['baseline_ref'],root))

    def test_successful_selection_does_not_write_index_head_or_refs(self):
        root,graph=self.clone('sha1')
        def snapshot():return ((root/'.git/index').read_bytes(),(root/'.git/HEAD').read_bytes(),command(root,'show-ref'))
        before=snapshot();self.select(root,graph,'registry','baseline_ref',graph['approved'])
        self.assertEqual(snapshot(),before)

    def cli(self,root,graph,ref):
        raw=json.dumps({'schema_version':1,'trees':{graph['tree']:{'baseline_ref':ref}}})
        return subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/approval_registry.py'),
            '--repo-root',str(root),'--candidate-ref',graph['candidate']],capture_output=True,
            text=True,encoding='utf-8',env=dict(os.environ,KDD_APPROVAL_REGISTRY=raw),timeout=45)

    def test_cli_rejects_hexadecimal_branch_in_external_json(self):
        root,graph=self.clone('sha1');alias='c'*64
        command(root,'update-ref','refs/heads/'+alias,graph['candidate'])
        result=self.cli(root,graph,alias)
        self.assertNotEqual(result.returncode,0);self.assertIn('APPROVAL_',result.stderr)

    def test_cli_keeps_canonical_reference_and_reports_its_source(self):
        root,graph=self.clone('sha256');result=self.cli(root,graph,graph['approved'])
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=json.loads(result.stdout);self.assertEqual(data['baseline_ref'],graph['approved'])
        self.assertEqual(data['source'],'registry')
