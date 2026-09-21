import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'kdd-codex'


class KddCodexPluginTests(unittest.TestCase):
    def test_public_plugin_is_skill_only_with_public_materials(self):
        manifest = json.loads((PLUGIN / '.codex-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        marketplace = json.loads((ROOT / '.agents' / 'plugins' / 'marketplace.json').read_text(encoding='utf-8'))

        self.assertEqual(manifest['name'], 'kdd-codex')
        self.assertEqual(marketplace['name'], 'kdd')
        self.assertEqual(manifest['skills'], './skills/')
        self.assertNotIn('mcpServers', manifest)
        self.assertNotIn('hooks', manifest)
        self.assertFalse((PLUGIN / 'hooks' / 'hooks.json').exists())
        self.assertFalse((PLUGIN / 'scripts' / 'kdd-event-relay.py').exists())
        for filename in ('PRIVACY.md', 'TERMS.md', 'SUPPORT.md', 'PUBLISHING.md'):
            self.assertTrue((PLUGIN / filename).is_file())
        self.assertEqual(len(manifest['interface']['defaultPrompt']), 3)


if __name__ == '__main__':
    unittest.main()
