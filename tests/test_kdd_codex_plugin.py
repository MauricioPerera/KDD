import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'kdd-codex'


class KddCodexPluginTests(unittest.TestCase):
    def test_plugin_declares_safe_local_event_delivery(self):
        manifest = json.loads((PLUGIN / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        hook_config = json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
        relay = (PLUGIN / 'scripts' / 'kdd-event-relay.py').read_text(encoding='utf-8')

        self.assertEqual(manifest['name'], 'kdd-codex')
        self.assertEqual(manifest['skills'], './skills/')
        self.assertNotIn('mcpServers', manifest)
        self.assertIn('Stop', hook_config['hooks'])
        self.assertIn('KDD_WEBHOOK_URL', relay)
        self.assertIn('KDD_WEBHOOK_SECRET', relay)
        self.assertIn('https://', relay)
        self.assertNotIn('http://', relay)


if __name__ == '__main__':
    unittest.main()
