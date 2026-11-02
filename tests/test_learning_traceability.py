"""Read-only learning links are approved externally and resolved from real Git."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_fixture_preparation import configure_git

ROOT=Path(__file__).resolve().parents[1]

def sha(raw):
    return hashlib.sha256(raw.replace(b'\r\n',b'\n').replace(b'\r',b'\n')).hexdigest()

class LearningTraceability(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='kdd-learning-links-')
        self.addCleanup(self.area.cleanup)
        self.root=Path(self.area.name)
        self.git('init','-q','-b','main')
        configure_git(self.root,{'user.name':'Synthetic reviewer','user.email':'reviewer@example.invalid','core.autocrlf':'false'},ephemeral=True)
        self.write('.gitignore','__pycache__/\n*.pyc\n')
        self.write('knowledge/finding.md',"---\ntype: 'Concept'\ntitle: 'Finding'\ndescription: 'Observed defect'\ntags: ['learning']\n---\n# Observed finding\n")
        self.write('knowledge/decision.md',"---\ntype: 'Concept'\ntitle: 'Decision'\ndescription: 'Reviewed response'\ntags: ['learning']\n---\n# Accepted decision\n")
        self.marker=self.root/'product-executed.txt'
        self.write('tests/test_fix.py',f'from pathlib import Path\nPath({str(self.marker)!r}).write_text("executed")\n')
        artifacts=self.commit('Version finding, decision and test artifacts')
        def ref(path):return {'path':path,'ref':artifacts,'sha256':sha((self.root/path).read_bytes())}
        self.entry={'id':'fix-1','status':'accepted','finding':ref('knowledge/finding.md'),'decision':ref('knowledge/decision.md'),'tests':[ref('tests/test_fix.py')]}
        self.ledger={'schema_version':1,'entries':[self.entry]}
        self.freeze()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.PIPE,text=True).strip()

    def write(self,path,content):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8',newline='\n')

    def commit(self,message):
        self.git('add','-A');self.git('commit','-qm',message);return self.git('rev-parse','HEAD')

    def freeze(self):
        self.write('knowledge/learning.json',json.dumps(self.ledger,sort_keys=True)+'\n')
        self.approved=self.commit('Synthetic external approval of declared links')
        self.observed=self.approved

    def run_validator(self,approval=True,extra=()):
        argv=[sys.executable,str(ROOT/'scripts/validate_learning.py'),'--repo-root',str(self.root),'--ledger','knowledge/learning.json','--observed-ref',self.observed]
        if approval:argv+=['--approved-ref',self.approved]
        return subprocess.run([*argv,*extra],capture_output=True,text=True,encoding='utf-8',timeout=20)

    def report(self,result):
        self.assertTrue(result.stdout.lstrip().startswith('{'),'validator must emit a real JSON receipt: '+result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['schema_version'],1)
        return report

    def reject(self,code,**kwargs):
        result=self.run_validator(**kwargs)
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn(code,result.stdout+result.stderr)
        report=self.report(result)
        self.assertEqual(report['status'],'FAIL')
        self.assertFalse(report['complete'])
        return report

    def test_approved_accepted_links_report_versions_without_claiming_test_execution(self):
        result=self.run_validator(extra=('--require-accepted',))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=self.report(result)
        self.assertEqual(report['status'],'PASS')
        self.assertTrue(report['complete'])
        self.assertEqual(report['approved_ref'],self.approved)
        self.assertEqual(report['observed_ref'],self.observed)
        self.assertEqual(report['accepted_count'],1)
        row=report['entries'][0]
        self.assertEqual(row['id'],'fix-1')
        self.assertTrue(row['approval_verified'])
        self.assertEqual(row['decision']['sha256'],self.entry['decision']['sha256'])
        self.assertEqual(row['tests'][0]['sha256'],self.entry['tests'][0]['sha256'])
        self.assertTrue(row['tests'][0]['reference_verified'])
        self.assertFalse(row['tests'][0]['execution_observed'])
        self.assertFalse(self.marker.exists(),'link validation must not import or execute linked product tests')

    def test_accepted_entry_requires_a_decision(self):
        self.entry.pop('decision');self.freeze();self.reject('LEARNING_DECISION')

    def test_accepted_entry_requires_versioned_tests(self):
        self.entry['tests']=[];self.freeze();self.reject('LEARNING_TESTS')

    def test_wrong_referenced_digest_is_rejected(self):
        self.entry['decision']['sha256']='0'*64;self.freeze();self.reject('LEARNING_HASH')

    def test_head_alias_cannot_be_used_as_external_approval(self):
        self.approved='HEAD';self.reject('LEARNING_APPROVAL')

    def test_candidate_cannot_promote_draft_to_accepted_itself(self):
        accepted=copy.deepcopy(self.entry)
        self.entry.clear();self.entry.update(id='fix-1',status='draft');self.freeze()
        self.ledger['entries']=[accepted]
        self.write('knowledge/learning.json',json.dumps(self.ledger))
        self.observed=self.commit('Candidate attempts to accept its own finding')
        self.reject('LEARNING_APPROVAL')

    def test_approver_text_is_not_an_external_approval_reference(self):
        self.ledger['approved_by']='Human reviewer'
        self.write('knowledge/learning.json',json.dumps(self.ledger))
        self.observed=self.commit('Candidate declares an approver string')
        self.reject('LEARNING_APPROVAL',approval=False)

    def test_checkout_correction_cannot_supply_a_missing_referenced_git_blob(self):
        self.entry['tests'][0]['path']='tests/not-in-git.py';self.freeze()
        self.write('tests/not-in-git.py','assert True\n')
        self.reject('LEARNING_REF')
        self.assertTrue((self.root/'tests/not-in-git.py').exists())

    def test_dirty_checkout_does_not_replace_observed_git_versions_or_get_rewritten(self):
        self.write('knowledge/decision.md','dirty local decision\n')
        self.write('tests/test_fix.py','dirty local test\n')
        before=self.git('rev-parse','HEAD'),self.git('status','--porcelain'),(self.root/'knowledge/decision.md').read_bytes()
        result=self.run_validator()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(self.report(result)['complete'])
        self.assertEqual((self.git('rev-parse','HEAD'),self.git('status','--porcelain'),(self.root/'knowledge/decision.md').read_bytes()),before)

    def test_changed_observed_decision_is_stale_against_approved_links(self):
        self.write('knowledge/decision.md','changed version\n');self.observed=self.commit('Changed accepted decision')
        self.reject('LEARNING_STALE')

    def test_changed_observed_test_is_stale_against_approved_links(self):
        self.write('tests/test_fix.py','changed test\n');self.observed=self.commit('Changed linked test')
        self.reject('LEARNING_STALE')

    def test_path_escape_is_rejected_before_artifact_access(self):
        self.entry['finding']['path']='../outside.md';self.freeze();self.reject('LEARNING_PATH')

    def test_git_symlink_mode_cannot_be_a_regular_decision_blob(self):
        process=subprocess.run(['git','-C',str(self.root),'hash-object','-w','--stdin'],input='outside.md\n',text=True,capture_output=True,check=True)
        self.git('update-index','--add','--cacheinfo','120000',process.stdout.strip(),'knowledge/link.md')
        self.git('commit','-qm','Synthetic Git symlink mode')
        ref=self.git('rev-parse','HEAD')
        self.entry['decision']={'path':'knowledge/link.md','ref':ref,'sha256':sha(b'outside.md\n')}
        self.freeze();self.reject('LEARNING_PATH')

    def test_empty_required_accepted_coverage_blocks(self):
        self.ledger['entries']=[];self.freeze();self.reject('LEARNING_COVERAGE',extra=('--require-accepted',))

    def test_draft_is_pending_and_does_not_become_complete(self):
        self.entry.clear();self.entry.update(id='pending-1',status='draft');self.freeze()
        result=self.run_validator()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=self.report(result)
        self.assertEqual(report['status'],'PENDING')
        self.assertFalse(report['complete'])
        self.assertEqual(report['accepted_count'],0)

    def test_required_mode_cannot_count_pending_entries_as_accepted(self):
        self.entry.clear();self.entry.update(id='pending-1',status='draft');self.freeze()
        self.reject('LEARNING_COVERAGE',extra=('--require-accepted',))

    def test_legacy_unlinked_record_reports_unverified_without_inventing_references(self):
        self.entry.clear();self.entry.update(id='legacy-1',status='legacy');self.freeze()
        result=self.run_validator()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=self.report(result)
        self.assertEqual(report['status'],'PENDING')
        row=report['entries'][0]
        self.assertEqual(row['status'],'LEGACY_UNVERIFIED')
        self.assertFalse(row['approval_verified'])
        self.assertFalse(report['complete'])
        self.assertNotIn('decision',row)

    def test_same_git_inputs_have_byte_identical_deterministic_receipts(self):
        first=self.run_validator();second=self.run_validator()
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        self.report(first);self.report(second)
        self.assertEqual(first.stdout,second.stdout)
        self.assertFalse(self.marker.exists())

    def test_execution_guarantee_without_supported_provenance_is_explicitly_unsupported(self):
        self.reject('LEARNING_UNSUPPORTED',extra=('--require-execution',))

    def test_duplicate_learning_identity_is_not_coverage(self):
        self.ledger['entries'].append(copy.deepcopy(self.entry));self.freeze();self.reject('LEARNING_POLICY')

    def test_referenced_commit_alias_is_not_a_version_identity(self):
        self.entry['finding']['ref']='HEAD';self.freeze();self.reject('LEARNING_REF')

    def test_accepted_entry_requires_a_finding(self):
        self.entry.pop('finding');self.freeze();self.reject('LEARNING_FINDING')

    def test_required_coverage_does_not_hide_a_pending_record_beside_an_accepted_one(self):
        self.ledger['entries'].append({'id':'pending-2','status':'draft'});self.freeze()
        self.reject('LEARNING_COVERAGE',extra=('--require-accepted',))

    def test_gitlink_cannot_be_presented_as_a_regular_test_blob(self):
        ref=self.git('rev-parse','HEAD')
        self.git('update-index','--add','--cacheinfo','160000',ref,'tests/linked-repo')
        self.git('commit','-qm','Synthetic Gitlink entry')
        linked=self.git('rev-parse','HEAD')
        self.entry['tests']=[{'path':'tests/linked-repo','ref':linked,'sha256':'0'*64}]
        self.freeze();self.reject('LEARNING_PATH')

if __name__=='__main__':unittest.main()
