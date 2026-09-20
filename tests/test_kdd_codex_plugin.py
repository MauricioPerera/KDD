import hashlib
import hmac
import importlib.util
import json
import os
import pathlib
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'kdd-codex'


class KddCodexPluginTests(unittest.TestCase):
    def test_plugin_declares_safe_local_event_delivery(self):
        manifest = json.loads((PLUGIN / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        marketplace = json.loads((ROOT / '.agents' / 'plugins' / 'marketplace.json').read_text(encoding='utf-8'))
        hook_config = json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
        relay = (PLUGIN / 'scripts' / 'kdd-event-relay.py').read_text(encoding='utf-8')

        self.assertEqual(manifest['name'], 'kdd-codex')
        self.assertEqual(marketplace['name'], 'kdd')
        self.assertEqual(manifest['skills'], './skills/')
        self.assertNotIn('mcpServers', manifest)
        self.assertIn('Stop', hook_config['hooks'])
        self.assertIn('KDD_WEBHOOK_URL', relay)
        self.assertIn('KDD_WEBHOOK_SECRET', relay)
        self.assertIn('https://', relay)
        self.assertNotIn('http://', relay)

    def test_relay_signs_minimal_payload_without_network(self):
        relay_path = PLUGIN / 'scripts' / 'kdd-event-relay.py'
        spec = importlib.util.spec_from_file_location('kdd_event_relay', relay_path)
        relay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(relay)
        requests = []

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False

        with patch.dict(os.environ, {'KDD_WEBHOOK_URL': 'https://relay.example/events', 'KDD_WEBHOOK_SECRET': 'test-secret'}, clear=False), \
             patch.object(relay.sys, 'stdin', __import__('io').StringIO(json.dumps({'hook_event_name': 'Stop', 'session_id': 's1', 'cwd': '/repo', 'prompt': 'secret'}))), \
             patch.object(relay.urllib.request, 'urlopen', side_effect=lambda request, timeout: requests.append((request, timeout)) or Response()):
            self.assertEqual(relay.main(), 0)

        request, timeout = requests[0]
        self.assertEqual(timeout, 5)
        self.assertEqual(json.loads(request.data), {'event': 'Stop', 'session_id': 's1', 'cwd': '/repo'})
        expected = hmac.new(b'test-secret', request.data, hashlib.sha256).hexdigest()
        self.assertEqual(request.headers['X-kdd-signature'], f'sha256={expected}')


if __name__ == '__main__':
    unittest.main()
