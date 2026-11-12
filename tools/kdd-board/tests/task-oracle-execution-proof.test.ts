import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, rmSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {digest, evidenceCurrent} from '../src/task-execution.ts';
import type {Task} from '../src/types.ts';
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

test('a persisted Node result needs recorder provenance to count as current', async () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'kdd-board-node-receipt-'));
  try {
    const oracle = path.join(root, 'oracle.mjs');
    const contract = path.join(root, 'contract.md');
    writeFileSync(oracle, "import {test} from 'node:test'; test('genuine', () => {});");
    writeFileSync(contract, 'fixture contract');
    const command = 'node --test --test-reporter=tap oracle.mjs';
    const task = {contractId: 'app-fixture.md', testCommand: command} as Task;
    const context = {command, cwd: root, contractId: task.contractId,
      evidence: {[oracle]: digest(oracle), [contract]: digest(contract)}};
    task.testReport = {...context, lastRun: new Date().toISOString(), durationMs: 1,
      status: 'PASS', success: true, verifiedOracle: true, passedTests: 1, failedTests: 0,
      output: 'historical file-only TAP'};
    assert.equal(evidenceCurrent(task), false);
    const current = await executeTaskTest(command, root, {}, oracle);
    task.testReport = {...current, ...context};
    assert.equal(current.status, 'PASS', current.output);
    assert.equal(evidenceCurrent(task), true);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
