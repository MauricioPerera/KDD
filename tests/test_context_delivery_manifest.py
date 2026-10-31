"""Content identities and actual delivery, without claims of comprehension."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import assemble_context as ac

def sha(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()

class ContextDeliveryManifest(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='kdd-context-manifest-')
        self.addCleanup(self.area.cleanup)
        self.root=Path(self.area.name)
        (self.root/'knowledge').mkdir()
        self.text='Reviewed source content.\n'
        (self.root/'knowledge/source.md').write_text(self.text,encoding='utf-8',newline='\n')
        self.policy={'budget':{'max_tokens':200,'output_reserve':0},'slots':[
            {'id':'source','source':'static','path':'knowledge/source.md','priority':0,'compaction':'none'}]}

    def result(self):return ac.assemble(self.policy,'Actual user task',str(self.root))

    def manifest(self,result):
        self.assertIn('manifest',result,'slot selection and a twelve-digit sign are not source/delivery identities')
        manifest=result['manifest']
        self.assertEqual(manifest['schema_version'],1)
        self.assertEqual(manifest['context_sha256'],sha(result['context']))
        return manifest

    def required_rejection(self):
        try:result=self.result()
        except ac.GuardrailAbort as error:
            self.assertIn('CONTEXT_REQUIRED',str(error))
            self.assertTrue(error.result['guardrails']['abort'])
            return
        except OSError as error:
            self.fail('required input must produce typed abort and a partial receipt: '+str(error))
        self.fail('required input was omitted or truncated while guardrails remained successful: '+repr(result['slots']))

    def test_static_source_identity_and_delivered_span_bind_actual_context(self):
        result=self.result();manifest=self.manifest(result)
        self.assertEqual(len(manifest['sources']),1)
        row=manifest['sources'][0]
        self.assertEqual(row['slot'],'source')
        self.assertEqual(row['path'],'knowledge/source.md')
        self.assertEqual(row['source_sha256'],sha(self.text))
        self.assertEqual(row['status'],'full')
        start,end=row['delivered_span']
        self.assertEqual(result['context'][start:end],self.text)
        self.assertEqual(row['delivered_sha256'],sha(result['context'][start:end]))

    def test_runtime_text_is_identified_without_an_invented_git_commit(self):
        self.policy['slots']=[{'id':'task','source':'runtime','priority':0,'compaction':'none'}]
        result=self.result();row=self.manifest(result)['sources'][0]
        self.assertEqual(row['origin'],'runtime')
        self.assertIsNone(row['path'])
        self.assertIsNone(row['git_commit'])
        self.assertEqual(row['source_sha256'],sha('Actual user task'))

    def test_required_source_omitted_by_budget_aborts(self):
        self.policy['budget']['max_tokens']=1
        self.policy['slots'][0]['required']=True
        self.required_rejection()

    def test_required_source_truncated_by_slot_cap_aborts(self):
        self.policy['slots'][0].update(required=True,max_tokens=3,compaction='truncate')
        self.required_rejection()

    def test_required_source_omitted_by_minimum_aborts(self):
        self.policy['slots'][0].update(required=True,max_tokens=2,min_tokens=3)
        self.required_rejection()

    def test_omitted_optional_input_retains_its_source_identity(self):
        self.policy['budget']['max_tokens']=1
        result=self.result();row=self.manifest(result)['sources'][0]
        self.assertEqual(row['source_sha256'],sha(self.text))
        self.assertEqual(row['status'],'omitted')
        self.assertIsNone(row['delivered_span'])
        self.assertIsNone(row['delivered_sha256'])

    def test_source_changes_outside_the_fragment_change_only_the_source_identity(self):
        self.policy['slots'][0].update(max_tokens=10,compaction='truncate')
        path=self.root/'knowledge/source.md'
        path.write_text('A'*500+'first tail',encoding='utf-8')
        first=self.result();a=self.manifest(first)['sources'][0]
        path.write_text('A'*500+'second tail',encoding='utf-8')
        second=self.result();b=self.manifest(second)['sources'][0]
        self.assertEqual(first['context'],second['context'])
        self.assertNotEqual(a['source_sha256'],b['source_sha256'])
        self.assertEqual(a['delivered_sha256'],b['delivered_sha256'])
        self.assertEqual(a['status'],'truncated')

    def test_manifest_is_deterministic_and_preserves_the_existing_context_budget(self):
        first=self.result();second=self.result()
        self.assertEqual(first,second)
        self.manifest(first)
        self.assertLessEqual(first['used'],first['available'])
        self.assertEqual(first['context'],'### slot: source\n'+self.text)

    def test_missing_required_input_has_typed_abort_and_partial_receipt(self):
        self.policy['slots'][0]['required']=True
        (self.root/'knowledge/source.md').unlink()
        self.required_rejection()

    def test_correct_pinned_source_version_is_delivered(self):
        self.policy['slots'][0].update(required=True,expected_sha256=sha(self.text))
        result=self.result()
        row=self.manifest(result)['sources'][0]
        self.assertEqual(row['status'],'full')
        self.assertEqual(row['source_sha256'],sha(self.text))

    def test_stale_pinned_version_blocks_even_when_full_content_fits(self):
        self.policy['slots'][0].update(required=True,expected_sha256='0'*64)
        self.required_rejection()

    def test_invalid_version_pin_is_not_ignored(self):
        self.policy['slots'][0]['expected_sha256']=12
        with self.assertRaisesRegex(ValueError,'expected_sha256'):
            self.result()

    def test_changed_required_source_during_assembly_cannot_claim_stable_delivery(self):
        self.policy['slots'][0]['required']=True
        original=ac._read_file
        changed=False
        def observe(base,path):
            nonlocal changed
            content=original(base,path)
            if path=='knowledge/source.md' and not changed:
                changed=True
                (self.root/path).write_text('Physical changed source after real read.\n',encoding='utf-8')
            return content
        with patch.object(ac,'_read_file',side_effect=observe):
            self.required_rejection()
        self.assertTrue(changed,'the real provider must actually have read the source')

    def test_disk_bytes_and_normalized_source_text_have_distinct_identities(self):
        (self.root/'knowledge/source.md').write_bytes(self.text.replace('\n','\r\n').encode())
        row=self.manifest(self.result())['sources'][0]
        self.assertEqual(row['source_sha256'],sha(self.text))
        self.assertEqual(row['source_hash_method'],'sha256-utf8-lf')
        self.assertEqual(row['raw_sha256'],hashlib.sha256((self.root/'knowledge/source.md').read_bytes()).hexdigest())
        self.assertIsNone(row['git_commit'],'a filesystem read alone does not identify a Git commit')

    def test_dynamic_nodes_record_full_truncated_and_omitted_actual_parts(self):
        (self.root/'knowledge/source.md').unlink()
        texts={'knowledge/a.md':'A'*40,'knowledge/b.md':'B'*100,'knowledge/c.md':'C'*80}
        for name,content in texts.items():(self.root/name).write_text(content,encoding='utf-8')
        self.policy['slots']=[{'id':'nodes','source':'dynamic','provider':'okf_nodes','priority':0,'max_tokens':25,'compaction':'truncate'}]
        result=self.result()
        rows={row['path']:row for row in self.manifest(result)['sources']}
        self.assertEqual(set(rows),set(texts))
        self.assertEqual([rows[name]['status'] for name in texts],['full','truncated','omitted'])
        for name,row in rows.items():
            self.assertEqual(row['source_sha256'],sha(texts[name]))
            if row['status']=='omitted':
                self.assertIsNone(row['delivered_span'])
            else:
                start,end=row['delivered_span']
                self.assertEqual(row['delivered_sha256'],sha(result['context'][start:end]))
                if row['status']=='full':self.assertEqual(result['context'][start:end],texts[name])

    def test_dynamic_paths_disambiguate_duplicate_node_names(self):
        (self.root/'knowledge/source.md').unlink()
        for relative in ('knowledge/a/same.md','knowledge/b/same.md'):
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(relative,encoding='utf-8')
        self.policy['slots']=[{'id':'nodes','source':'dynamic','provider':'okf_nodes','priority':0,'compaction':'none'}]
        rows=self.manifest(self.result())['sources']
        self.assertEqual({row['path'] for row in rows},{'knowledge/a/same.md','knowledge/b/same.md'})
        self.assertEqual(len(rows),2)
        self.assertEqual(len({row['source_sha256'] for row in rows}),2)

    def test_required_dynamic_selection_must_be_delivered_completely(self):
        (self.root/'knowledge/source.md').write_text('A'*800,encoding='utf-8')
        self.policy['slots']=[{'id':'nodes','source':'dynamic','provider':'okf_nodes','priority':0,'max_tokens':10,'compaction':'truncate','required':True}]
        self.required_rejection()

    def test_required_flag_requires_boolean_instead_of_truthy_text(self):
        self.policy['slots'][0]['required']='yes'
        with self.assertRaisesRegex(ValueError,'required'):
            self.result()

    def test_required_empty_dynamic_selection_is_not_complete_context(self):
        (self.root/'knowledge/source.md').unlink()
        self.policy['slots']=[{'id':'nodes','source':'dynamic','provider':'okf_nodes','priority':0,'required':True}]
        self.required_rejection()

    def test_formatted_report_exposes_the_same_deterministic_manifest(self):
        result=self.result()
        report=ac.format_report(result,'context.json','Actual user task')
        lines=[line.removeprefix('CONTEXT_MANIFEST ') for line in report.splitlines() if line.startswith('CONTEXT_MANIFEST ')]
        self.assertEqual(len(lines),1,'CLI logs need the actual source and delivery receipt')
        self.assertEqual(json.loads(lines[0]),self.manifest(result))

if __name__=='__main__':unittest.main()
