import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {executeTaskTest} from '../src/test-runner.ts';

async function run(source: string) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-python-proof-'));
  const oracle = path.join(root, 'oracle.py');
  fs.writeFileSync(oracle, source);
  try { return await executeTaskTest('python -m unittest oracle.py', root, {}, oracle); }
  finally { fs.rmSync(root, {recursive:true, force:true}); }
}

test('forged unittest summary followed by early exit is never a verified pass', async () => {
  const report = await run("import os,sys\nsys.stderr.write('Ran 1 test in 0.001s\\n\\nOK\\n')\nsys.stderr.flush()\nos._exit(0)\n");
  assert.notEqual(report.status, 'PASS');
  assert.equal(report.verifiedOracle, false);
  assert.equal(report.passedTests, 0);
});

test('a real unittest case has instrumented positive evidence', async () => {
  const report = await run('import unittest\nclass Oracle(unittest.TestCase):\n def test_value(self): self.assertEqual(1,1)\n');
  assert.equal(report.status, 'PASS');
  assert.equal(report.verifiedOracle, true);
  assert.equal(report.passedTests, 1);
});

test('zero cases and omitted cases cannot verify the Python oracle', async () => {
  for (const source of ['pass\n', "import unittest\nclass Oracle(unittest.TestCase):\n @unittest.skip('omitted')\n def test_value(self): self.fail()\n"]) {
    const report = await run(source);
    assert.notEqual(report.status, 'PASS');
    assert.equal(report.verifiedOracle, false);
    assert.equal(report.passedTests, 0);
  }
});
