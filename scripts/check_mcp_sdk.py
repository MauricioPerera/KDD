"""Verify the pinned, genuine SDK against every existing MCP protocol oracle."""
import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest


class McpSdkError(ValueError):
    """The configured MCP SDK profile cannot be verified."""


def validate_report(data, expected_ids, expected_version):
    """Validate independently of unittest's permissive skip/xfail exit status."""
    if not isinstance(data, dict):
        raise McpSdkError('MCP_REPORT_SCHEMA: report must be an object')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise McpSdkError('MCP_REPORT_SCHEMA: unsupported report version')
    if data.get('ok') is not True or type(data.get('tests_run')) is not int or data['tests_run'] != 8:
        raise McpSdkError('MCP_REPORT_RESULT: exactly eight successful cases are required')
    _report_inventory(data, expected_ids)
    if data.get('sdk_version') != expected_version or data.get('transport') != 'in-memory':
        raise McpSdkError('MCP_REPORT_SDK: SDK version or transport differs')


def _report_inventory(data, expected_ids):
    if (len(expected_ids) != 8 or len(set(expected_ids)) != 8
            or data.get('expected_ids') != list(expected_ids)
            or data.get('executed_ids') != list(expected_ids)):
        raise McpSdkError('MCP_REPORT_IDS: expected and executed inventories must match exactly')
    for field in ('failures','errors','skipped','loader_errors','expected_failures','unexpected_successes'):
        if field not in data or data[field] != []:
            raise McpSdkError('MCP_REPORT_RESULT: nonempty or missing ' + field)


def _manifest(root):
    try:
        data = json.loads((root/'tools/mcp-sdk/pins.json').read_text(encoding='utf-8'))
        oracle = root/data['oracle_path']
        ids = data['expected_ids']
        valid = (type(data['schema_version']) is int and data['schema_version'] == 1
                 and data['transport'] == 'in-memory' and isinstance(ids,list)
                 and len(ids) == 8 and all(isinstance(item,str) for item in ids)
                 and len(set(ids)) == 8 and ids == sorted(ids))
        if not valid or not oracle.resolve().is_relative_to(root) or oracle.is_symlink():
            raise McpSdkError('MCP_MANIFEST: invalid oracle or inventory')
        raw = oracle.read_bytes().replace(b'\r\n',b'\n')
        if hashlib.sha256(raw).hexdigest() != data['oracle_sha256']:
            raise McpSdkError('MCP_ORACLE: oracle bytes differ from the pinned manifest')
    except (OSError,KeyError,TypeError,ValueError) as error:
        if isinstance(error,McpSdkError):
            raise
        raise McpSdkError('MCP_MANIFEST: missing or invalid SDK manifest') from error
    return data, oracle


def _sdk(root, expected):
    try:
        version = importlib.metadata.version('mcp')
    except importlib.metadata.PackageNotFoundError as error:
        raise McpSdkError('MCP_SDK_MISSING: install the reviewed SDK profile') from error
    if version != expected:
        raise McpSdkError('MCP_SDK_VERSION: expected ' + expected + ', found ' + version)
    spec = importlib.util.find_spec('mcp')
    if spec is None or not spec.origin or Path(spec.origin).resolve().is_relative_to(root):
        raise McpSdkError('MCP_SDK_ORIGIN: SDK must be outside the project')
    try:
        modules = [importlib.import_module(name) for name in
                   ('mcp','mcp.types','mcp.shared.memory','mcp.server.fastmcp')]
    except ImportError as error:
        raise McpSdkError('MCP_SDK_IMPORT: the installed SDK is incompatible or incomplete') from error
    for module in modules:
        if not module.__file__ or Path(module.__file__).resolve().is_relative_to(root):
            raise McpSdkError('MCP_SDK_ORIGIN: SDK must be outside the project')
    return version, str(Path(modules[0].__file__).resolve())


class _Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_ids = []

    def startTest(self, test):
        self.executed_ids.append(test.id())
        super().startTest(test)


def _execute(oracle):
    old_path = sys.path[:]
    names = ('mcp_server','mcp_gate_dispatch','rule_hints')
    previous = {name:sys.modules.pop(name) for name in names if name in sys.modules}
    try:
        spec = importlib.util.spec_from_file_location(oracle.stem,oracle)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=_Result).run(suite)
        return result, loader.errors, stream.getvalue()
    except (ImportError,OSError,ValueError) as error:
        raise McpSdkError('MCP_DISCOVERY: could not load the SDK oracles') from error
    finally:
        sys.path[:] = old_path
        for name in names:
            sys.modules.pop(name,None)
        sys.modules.update(previous)


def _commit(root):
    result = subprocess.run(['git','-C',str(root),'rev-parse','--verify','HEAD'],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',value) else None


def _write_report(path, data):
    if path is None:
        return
    target = Path(path)
    try:
        with target.open('x',encoding='utf-8') as output:
            output.write(json.dumps(data,indent=2)+'\n')
    except OSError as error:
        raise McpSdkError('MCP_EVIDENCE: could not create fresh evidence') from error


def _require_commit(root, actual, expected):
    if expected is None:
        return
    if actual is None or actual != expected:
        raise McpSdkError('MCP_COMMIT: checkout differs from the expected commit')
    status = subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=all'],timeout=30)
    if status:
        raise McpSdkError('MCP_COMMIT: CI evidence requires a clean checkout')


def run_smoke(repo_root, *, report_path=None, expected_commit=None):
    root = Path(repo_root).resolve()
    if report_path is not None and os.path.lexists(report_path):
        raise McpSdkError('MCP_EVIDENCE: report already exists')
    commit = _commit(root)
    _require_commit(root,commit,expected_commit)
    manifest, oracle = _manifest(root)
    version, sdk_path = _sdk(root,manifest['sdk_version'])
    result, loader_errors, log = _execute(oracle)
    data = dict(schema_version=1,ok=result.wasSuccessful(),tests_run=result.testsRun,
        expected_ids=manifest['expected_ids'],executed_ids=result.executed_ids,
        failures=[(test.id(),text) for test,text in result.failures],
        errors=[(test.id(),text) for test,text in result.errors],
        skipped=[(test.id(),why) for test,why in result.skipped],loader_errors=loader_errors,
        expected_failures=[test.id() for test,_ in result.expectedFailures],
        unexpected_successes=[test.id() for test in result.unexpectedSuccesses],
        sdk_version=version,sdk_module_path=sdk_path,transport='in-memory',
        oracle_sha256=manifest['oracle_sha256'],repo_commit=commit,log=log)
    try:
        validate_report(data,manifest['expected_ids'],manifest['sdk_version'])
    except McpSdkError as error:
        data.update(ok=False,verification_error=str(error))
    _write_report(report_path,data)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',default='.')
    parser.add_argument('--report-json')
    parser.add_argument('--expected-commit')
    args = parser.parse_args(argv)
    try:
        data = run_smoke(args.repo_root,report_path=args.report_json,expected_commit=args.expected_commit)
    except (McpSdkError,OSError,subprocess.SubprocessError) as error:
        print('FAIL: '+str(error),file=sys.stderr)
        return 2
    print(json.dumps({key:data[key] for key in ('ok','tests_run','sdk_version','oracle_sha256','repo_commit','transport')}))
    if not data['ok']:
        print(data['log'],file=sys.stderr)
    return 0 if data['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
