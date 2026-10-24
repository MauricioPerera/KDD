"""Dependency lock and real bounded-memory regressions for GHSA-mrhx-c7xc-m3w5."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'tools/kdd-board'


class BoardDependencies(unittest.TestCase):
    def test_manifest_and_every_locked_zod_are_patched(self):
        package = json.loads((BOARD / 'package.json').read_text(encoding='utf-8'))
        lock = json.loads((BOARD / 'package-lock.json').read_text(encoding='utf-8'))
        minimum = package['dependencies']['zod']
        self.assertRegex(minimum, r'^\^4\.\d+\.\d+$')
        self.assertGreaterEqual(tuple(map(int, minimum[1:].split('.'))), (4, 6, 6))
        self.assertEqual(lock['packages']['']['dependencies']['zod'], minimum)
        versions = []
        for name, entry in lock['packages'].items():
            if name.endswith('node_modules/zod'):
                version = tuple(map(int, entry['version'].split('.')))
                self.assertEqual(version[0], 4, 'a major migration needs a separate contract')
                self.assertGreaterEqual(version, (4, 6, 6), name)
                self.assertTrue(entry['resolved'].startswith('https://registry.npmjs.org/zod/'))
                self.assertRegex(entry['integrity'], r'^sha512-[A-Za-z0-9+/]+=*$')
                versions.append(version)
        self.assertTrue(versions, 'the lock must resolve Zod')

    def node(self, source, *flags):
        if (not (ROOT / 'src/hello.py').is_file()
                and not (BOARD / 'node_modules/zod/package.json').is_file()):
            self.skipTest('initialized Python-only copy; Board runtime dependencies are not installed')
        return subprocess.run(['node', *flags, '--input-type=module', '-e', source],
                              cwd=BOARD, capture_output=True, text=True,
                              encoding='utf-8', timeout=30)

    def test_installed_runtime_matches_lock_and_bridge_registers(self):
        result = self.node("""
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {z} from 'zod';
import {createWebMcpMock, defineTool} from 'fastwebmcp';
const installed = JSON.parse(fs.readFileSync('node_modules/zod/package.json','utf8')).version;
const lock = JSON.parse(fs.readFileSync('package-lock.json','utf8'));
assert.equal(installed, lock.packages['node_modules/zod'].version);
assert.ok(installed.localeCompare('4.6.6',undefined,{numeric:true}) >= 0, installed);
const schema = z.object({count:z.number().int().min(1).max(3)}).strict();
assert.equal(schema.safeParse({count:2}).success,true);
assert.equal(schema.safeParse({count:'2'}).success,false);
assert.equal(schema.safeParse({count:2,extra:true}).success,false);
assert.ok(createWebMcpMock().document);
assert.equal(defineTool({name:'probe',description:'probe',inputSchema:schema,execute:async x=>x}).name,'probe');
console.log('PATCHED_RUNTIME_CONTROL');
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PATCHED_RUNTIME_CONTROL', result.stdout)

    def test_oversized_invalid_collection_completes_in_bounded_heap(self):
        result = self.node("""
import assert from 'node:assert/strict';
import {z} from 'zod';
const schema = z.array(z.number()).max(2);
assert.equal(schema.safeParse([1,2]).success,true);
assert.equal(schema.safeParse(['bad']).success,false);
const result = schema.safeParse(Array(100000).fill('bad'));
assert.equal(result.success,false);
assert.ok(result.error.issues.length < 100);
console.log('BOUNDED_COLLECTION_REJECTED');
""", '--max-old-space-size=64')
        self.assertEqual(result.returncode, 0,
                         'OOM, timeout or runtime failure is not a correct rejection:\n' +
                         (result.stdout + result.stderr)[-2500:])
        self.assertIn('BOUNDED_COLLECTION_REJECTED', result.stdout)


if __name__ == '__main__':
    unittest.main()
