import assert from 'node:assert/strict';
import {mkdtempSync, rmSync, writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {digest, evidenceCurrent} from '../src/task-execution.ts';
import {TaskStore} from '../src/task-store.ts';
import {executeTaskTest} from '../src/test-runner.ts';

test('legacy Node reports expire and recorded Node evidence survives storage reload', async () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'kdd-legacy-node-'));
  try {
    const oracle = path.join(root, 'oracle.mjs');
    const contract = path.join(root, 'contract.md');
    const storage = path.join(root, 'tasks.json');
    writeFileSync(oracle, "import {test} from 'node:test'; test('a real case', () => {});");
    writeFileSync(contract, 'reviewed fixture contract');
    const command = 'node --test --test-reporter=tap oracle.mjs';
    const store = new TaskStore(storage);
    const task = store.createTask({title: 'Node proof', description: '', contractId: 'app-proof.md',
      testCommand: command});
    const context = {command, cwd: root, contractId: task.contractId,
      evidence: {[oracle]: digest(oracle), [contract]: digest(contract)}};
    task.status = 'done';
    task.testReport = {...context, lastRun: new Date().toISOString(), durationMs: 1,
      status: 'PASS', success: true, verifiedOracle: true, passedTests: 1, failedTests: 0,
      output: 'historical file-only TAP'};
    writeFileSync(storage, JSON.stringify([task]));
    const reloaded = new TaskStore(storage);
    assert.equal(reloaded.getTask(task.id)?.status, 'ready');
    assert.equal(reloaded.getTask(task.id)?.testReport?.status, 'SKIP');
    const report = await executeTaskTest(command, root, {}, oracle);
    assert.equal(report.status, 'PASS', report.output);
    reloaded.recordTestReport(task.id, {...report, ...context});
    const restored = new TaskStore(storage).getTask(task.id);
    assert.ok(restored);
    assert.equal(restored.testReport?.status, 'PASS');
    assert.equal(evidenceCurrent(restored), true);
  } finally {
    rmSync(root, {recursive: true, force: true});
  }
});
