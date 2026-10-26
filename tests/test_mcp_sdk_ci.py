"""Strict evidence controls plus real SDK protocol integration when configured."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_mcp_sdk as checker

VERSION = '1.30.0'
ORACLE_HASH = '8c841369165941980755598d984556d6359007c2010caf52e42aa7126e7bfd51'
WHEEL_HASH = '666edb5009503e1047c9d60346a756f94b261f05cc2625f23d41c728ffc484d0'
NAMES = [
    'test_gate_accepts_explicit_dir_inside_repo', 'test_gate_rejects_dir_escaping_repo',
    'test_gate_rejects_list_dir_escaping_repo', 'test_lint_ascii_tool_call_end_to_end',
    'test_lists_all_expected_tools', 'test_rule_hint_tool_call_end_to_end',
    'test_rule_hint_unknown_id_falls_back_without_error', 'test_seal_tests_rejects_path_escaping_repo',
]
IDS = ['test_mcp_server_smoke.TestMcpServerSmoke.'+name for name in NAMES]
SDK_PYTHON = os.environ.get('KDD_MCP_SDK_PYTHON','')
SDK_AVAILABLE = bool(SDK_PYTHON and Path(SDK_PYTHON).is_file())


def valid_report():
    return dict(schema_version=1,ok=True,tests_run=8,expected_ids=IDS[:],executed_ids=IDS[:],
                failures=[],errors=[],skipped=[],loader_errors=[],expected_failures=[],
                unexpected_successes=[],sdk_version=VERSION,transport='in-memory')


class McpSdkEvidence(unittest.TestCase):
    def test_manifest_and_existing_oracle_bytes_are_frozen(self):
        manifest=json.loads((ROOT/'tools/mcp-sdk/pins.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['sdk_version'],VERSION)
        self.assertEqual(manifest['sdk_wheel_sha256'],WHEEL_HASH)
        self.assertEqual(manifest['oracle_path'],'tests/test_mcp_server_smoke.py')
        self.assertEqual(manifest['oracle_sha256'],ORACLE_HASH)
        self.assertEqual(manifest['expected_ids'],IDS)
        raw=(ROOT/manifest['oracle_path']).read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ORACLE_HASH)

    def test_every_dependency_is_pinned_and_hashed_in_both_platform_locks(self):
        for platform in ('ubuntu','windows'):
            rows=[line for line in (ROOT/'tools/mcp-sdk'/ (platform+'.txt')).read_text().splitlines()
                  if line and not line.startswith('#')]
            with self.subTest(platform=platform):
                self.assertGreaterEqual(len(rows),20)
                for row in rows:
                    self.assertRegex(row,r'^[a-z0-9_.-]+==[a-zA-Z0-9_.+!-]+ --hash=sha256:[0-9a-f]{64}$')
                self.assertIn('mcp=='+VERSION+' --hash=sha256:'+WHEEL_HASH,rows)
                self.assertEqual(len(rows),len({line.split('==')[0] for line in rows}))

    def test_complete_eight_case_evidence_is_accepted(self):
        try:
            result=checker.validate_report(valid_report(),IDS,VERSION)
        except checker.McpSdkError as error:
            self.fail('Complete evidence unexpectedly rejected: '+str(error))
        self.assertIsNone(result)

    def test_zero_cases_are_not_a_success(self):
        report=valid_report();report.update(tests_run=0,executed_ids=[])
        with self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
            checker.validate_report(report,IDS,VERSION)

    def test_skip_is_failure_even_if_unittest_exit_would_be_zero(self):
        report=valid_report();report['skipped']=[{'id':IDS[0],'reason':'SDK unavailable'}]
        with self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
            checker.validate_report(report,IDS,VERSION)

    def test_failures_and_errors_are_not_accepted(self):
        for field in ('failures','errors','loader_errors','expected_failures','unexpected_successes'):
            report=valid_report();report[field]=['real failure']
            with self.subTest(field=field),self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
                checker.validate_report(report,IDS,VERSION)

    def test_missing_duplicate_and_extra_ids_are_rejected(self):
        for values in (IDS[:-1],IDS[:-1]+[IDS[0]],IDS+['unexpected.case']):
            report=valid_report();report['executed_ids']=values
            with self.subTest(values=values),self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
                checker.validate_report(report,IDS,VERSION)

    def test_candidate_report_cannot_choose_a_different_expected_inventory(self):
        report=valid_report();report['expected_ids']=list(reversed(IDS))
        with self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
            checker.validate_report(report,IDS,VERSION)

    def test_incompatible_sdk_and_transport_are_rejected(self):
        for changes in ({'sdk_version':'2.3.0'},{'transport':'stdio'}):
            report=valid_report();report.update(changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
                checker.validate_report(report,IDS,VERSION)

    def test_invalid_types_or_untruthful_success_flag_are_rejected(self):
        for changes in ({'tests_run':8.0},{'tests_run':True},{'ok':False},
                        {'ok':1},{'schema_version':True},{'skipped':None}):
            report=valid_report();report.update(changes)
            with self.subTest(changes=changes),self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
                checker.validate_report(report,IDS,VERSION)

    def test_missing_fields_are_not_treated_as_empty_success(self):
        report=valid_report();report.pop('errors')
        with self.assertRaisesRegex(checker.McpSdkError,'MCP_REPORT'):
            checker.validate_report(report,IDS,VERSION)

    def test_cli_without_sdk_fails_instead_of_skipping(self):
        result=subprocess.run([sys.executable,'-I','-S',str(ROOT/'scripts/check_mcp_sdk.py'),
            '--repo-root',str(ROOT)],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertIn('MCP_SDK_MISSING',result.stdout+result.stderr)
        self.assertNotIn('SKIP:',result.stdout+result.stderr)

    def test_base_profile_still_declares_the_eight_optional_sdk_skips(self):
        code=('import io,json,sys,unittest\n'
              'sys.path.insert(0,sys.argv[1])\n'
              'suite=unittest.TestLoader().loadTestsFromName("tests.test_mcp_server_smoke")\n'
              'result=unittest.TextTestRunner(stream=io.StringIO()).run(suite)\n'
              'print(json.dumps(dict(tests=result.testsRun,skipped=[c.id() for c,_ in result.skipped],'
              'errors=len(result.errors),failures=len(result.failures))))\n')
        result=subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT)],
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['tests'],8)
        self.assertEqual(sorted(report['skipped']),['tests.'+name for name in IDS])
        self.assertEqual((report['errors'],report['failures']),(0,0))

    def test_cli_refuses_to_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory(prefix='kdd-sdk-evidence-') as directory:
            report=Path(directory)/'result.json';report.write_text('existing evidence',encoding='utf-8')
            result=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/check_mcp_sdk.py'),
                '--repo-root',str(ROOT),'--report-json',str(report)],
                capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertIn('MCP_EVIDENCE',result.stdout+result.stderr)
            self.assertEqual(report.read_text(encoding='utf-8'),'existing evidence')

    def test_workflow_requires_sdk_in_existing_validate_jobs_and_keeps_two_passes(self):
        text=(ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertIn('verify_mcp_sdk:',text)
        self.assertIn('KDD_MCP_SDK_REQUIRED:',text)
        self.assertIn('Prepare pinned MCP SDK environment',text)
        self.assertIn('Run required MCP SDK protocol smoke',text)
        self.assertIn('--require-hashes',text)
        self.assertIn('KDD_MCP_SDK_PYTHON',text)
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'),2)
        self.assertEqual(text.count('- name: Run unit tests ('),2)
        self.assertNotIn('continue-on-error:',text)

    @unittest.skipUnless(SDK_AVAILABLE,'optional SDK integration: configure KDD_MCP_SDK_PYTHON')
    def test_genuine_sdk_runs_all_existing_protocol_cases_without_skips(self):
        with tempfile.TemporaryDirectory(prefix='kdd-sdk-real-') as directory:
            report=Path(directory)/'sdk.json'
            result=subprocess.run([SDK_PYTHON,'-I',str(ROOT/'scripts/check_mcp_sdk.py'),
                '--repo-root',str(ROOT),'--report-json',str(report)],
                capture_output=True,text=True,encoding='utf-8',timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data=json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(data['tests_run'],8)
            self.assertEqual(data['expected_ids'],IDS)
            self.assertEqual(data['executed_ids'],IDS)
            self.assertEqual(data['skipped'],[])
            self.assertEqual(data['sdk_version'],VERSION)
            self.assertEqual(data['oracle_sha256'],ORACLE_HASH)
            self.assertFalse(Path(data['sdk_module_path']).resolve().is_relative_to(ROOT))

    @unittest.skipUnless(SDK_AVAILABLE,'optional SDK integration: configure KDD_MCP_SDK_PYTHON')
    def test_project_sdk_shadow_cannot_replace_the_installed_sdk(self):
        with tempfile.TemporaryDirectory(prefix='kdd-sdk-shadow-') as directory:
            root=Path(directory)/'repo';root.mkdir()
            for relative in ('scripts','tests','tools/mcp-sdk'):
                shutil.copytree(ROOT/relative,root/relative,ignore=shutil.ignore_patterns('__pycache__'))
            marker=Path(directory)/'candidate-sdk-executed'
            (root/'scripts/mcp.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("unsafe")\n',encoding='utf-8')
            report=Path(directory)/'sdk.json'
            result=subprocess.run([SDK_PYTHON,'-I',str(ROOT/'scripts/check_mcp_sdk.py'),
                '--repo-root',str(root),'--report-json',str(report)],
                capture_output=True,text=True,encoding='utf-8',timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse(marker.exists())
            data=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(data['tests_run'],8)
            self.assertEqual(data['skipped'],[])
            self.assertFalse(Path(data['sdk_module_path']).resolve().is_relative_to(root))

    @unittest.skipUnless(SDK_AVAILABLE,'optional SDK integration: configure KDD_MCP_SDK_PYTHON')
    def test_wrong_commit_context_fails_before_claiming_ci_evidence(self):
        result=subprocess.run([SDK_PYTHON,'-I',str(ROOT/'scripts/check_mcp_sdk.py'),
            '--repo-root',str(ROOT),'--expected-commit','0'*40],
            capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertIn('MCP_COMMIT',result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
