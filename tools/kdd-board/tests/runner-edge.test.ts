import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { executeTaskTest } from '../src/test-runner.ts';

test('skipped unittest tests and decorative checkmarks are not passes', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-skipped-'));
  try {
    fs.writeFileSync(path.join(root, 'skipped.py'), "import unittest\nclass Example(unittest.TestCase):\n @unittest.skip('not configured')\n def test_placeholder(self): self.fail()\nunittest.main()\n");
    const skipped = await executeTaskTest('python skipped.py', root);
    assert.equal(skipped.success, true);
    assert.equal(skipped.passedTests, 0);
    fs.writeFileSync(path.join(root, 'decorative.cjs'), "console.log('✔ just a message');");
    const decorative = await executeTaskTest('node decorative.cjs', root);
    assert.equal(decorative.passedTests, 0);
  } finally { fs.rmSync(root, {recursive:true, force:true}); }
});
