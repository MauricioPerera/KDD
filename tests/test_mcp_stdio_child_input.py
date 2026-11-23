"""Exercise the pinned MCP server over real pipes with disposable local contracts."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'tools/mcp-sdk/pins.json'
READ_TIMEOUT = 22


def sdk_python():
    configured = os.environ.get('KDD_MCP_SDK_PYTHON')
    if configured:
        return configured
    try:
        importlib.metadata.version('mcp')
    except importlib.metadata.PackageNotFoundError:
        if os.environ.get('KDD_MCP_SDK_REQUIRED') == '1':
            raise RuntimeError('The required pinned MCP SDK interpreter is missing')
        return None
    return sys.executable


class Stdio:
    def __init__(self, server, python, outside, cleanup):
        self.messages = queue.Queue()
        self.identifier = 0
        self.errors = tempfile.TemporaryFile()
        cleanup(self.errors.close)
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        env['PATH'] = str(Path(python).parent) + os.pathsep + env['PATH']
        self.process = subprocess.Popen(
            [python, '-I', str(server)], cwd=outside, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.errors, text=True, encoding='utf-8', env=env)
        self.reader = threading.Thread(target=self.read, daemon=True)
        cleanup(self.close)
        self.reader.start()

    def read(self):
        try:
            for line in self.process.stdout:
                self.messages.put(line)
        finally:
            self.messages.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
        self.process.stdin.flush()

    def request(self, method, params):
        self.identifier += 1
        self.send(dict(method=method, params=params, id=self.identifier))
        try:
            raw = self.messages.get(timeout=READ_TIMEOUT)
        except queue.Empty as exc:
            raise AssertionError(f'No stdio reply for {method} {params.get("name", "")}') from exc
        if raw is None:
            self.errors.seek(0)
            raise AssertionError(f'MCP stdout closed: {self.errors.read().decode(errors="replace")}')
        value = json.loads(raw)
        if value.get('id') != self.identifier or 'result' not in value:
            raise AssertionError(f'Unexpected JSON-RPC response: {value}')
        return value['result']

    def call(self, name, **arguments):
        result = self.request('tools/call', dict(name=name, arguments=arguments))
        if result.get('isError'):
            raise AssertionError(f'Tool {name} returned a protocol error: {result}')
        structured = result.get('structuredContent')
        return structured if isinstance(structured, dict) else json.loads(result['content'][0]['text'])

    def close(self):
        try:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        finally:
            self.reader.join(timeout=10)
            self.process.stdout.close()


class McpStdioTransport(unittest.TestCase):
    def setUp(self):
        python = sdk_python()
        if python is None:
            self.skipTest('Standalone project without the optional MCP SDK profile')
        check = subprocess.run([python, '-I', '-c',
                                'from importlib.metadata import version; print(version("mcp"))'],
                               capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(check.stdout.strip(), json.loads(LOCK.read_text(encoding='utf-8'))['sdk_version'])
        temp = tempfile.TemporaryDirectory(prefix='kdd-mcp-wire-')
        self.addCleanup(temp.cleanup)
        area = Path(temp.name).resolve()
        self.root = area / 'sandbox'
        self.contracts = self.root / 'contracts'
        self.contracts.mkdir(parents=True)
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts',
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.oracle = self.contracts / 'test_sample.py'
        self.oracle.write_text(
            'import unittest\nclass Sample(unittest.TestCase):\n'
            '    def test_real_case(self): self.assertEqual(2 + 2, 4)\n',
            encoding='utf-8', newline='\n')
        (self.contracts / 'sample.md').write_text(
            "---\ntest_command: 'python -m unittest test_sample.py'\n---\n",
            encoding='utf-8', newline='\n')
        self.connection = Stdio(self.root / 'scripts/mcp_server.py', python, area, self.addCleanup)
        result = self.connection.request('initialize', dict(
            protocolVersion='2025-06-18', capabilities={}, clientInfo=dict(name='kdd-integration', version='1')))
        self.assertIn('serverInfo', result)
        self.connection.send(dict(method='notifications/initialized'))

    def test_contract_gate_returns_from_real_stdio_and_channel_remains_usable(self):
        names = {tool['name'] for tool in self.connection.request('tools/list', {})['tools']}
        self.assertTrue({'validate_test_commands', 'seal_tests', 'rule_hint'} <= names)
        result = self.connection.call('validate_test_commands', contracts_dir='contracts',
                                      root='contracts', gate_timeout=10, command_timeout=7)
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('sample.md', result['stdout'])
        self.assertTrue(self.connection.call('rule_hint', rule_id='FM_TESTS_FROZEN')['known'])

    def test_seals_test_bytes_over_stdio_and_rejects_an_external_path(self):
        expected = hashlib.sha256(self.oracle.read_bytes()).hexdigest()
        answer = self.connection.call('seal_tests', tests_path='contracts/test_sample.py')
        self.assertEqual(answer['exit_code'], 0, answer)
        self.assertEqual(answer['hash'], expected, answer)
        forbidden = self.root.parent / 'unrelated.txt'
        forbidden.write_text('outside', encoding='utf-8')
        denied = self.connection.call('seal_tests', tests_path=str(forbidden))
        self.assertEqual(denied['exit_code'], 2, denied)
        self.assertIsNone(denied['hash'])


if __name__ == '__main__':
    unittest.main()
