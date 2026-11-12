import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, rmSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {executeTaskTest} from '../src/test-runner.ts';

test('only registered Node cases can verify a sealed Board oracle', async () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'kdd-board-node-oracle-'));
  const oracle = path.join(root, 'tests', 'nested', 'value.test.mjs');
  try {
    mkdirSync(path.dirname(oracle), {recursive: true});
    const command = 'node --test tests/nested/value.test.mjs';
    writeFileSync(oracle, '// This file declares no tests.\n');
    const empty = await executeTaskTest(command, root, {}, oracle);
    assert.equal(empty.verifiedOracle, false, empty.output);
    assert.equal(empty.passedTests, 0, empty.output);
    assert.notEqual(empty.status, 'PASS');

    writeFileSync(oracle, [
      "import {test} from 'node:test';",
      "test('genuine case', () => console.log(process.env.KDD_TEST_SYNTHETIC));",
    ].join('\n'));
    const actual = await executeTaskTest(command, root, {KDD_TEST_SYNTHETIC: 'fixture-only-value'}, oracle);
    assert.equal(actual.status, 'PASS', actual.output);
    assert.equal(actual.verifiedOracle, true);
    assert.equal(actual.passedTests, 1);
    assert.match(actual.output, /\[REDACTED\]/);
    assert.doesNotMatch(actual.output, /fixture-only-value/);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
