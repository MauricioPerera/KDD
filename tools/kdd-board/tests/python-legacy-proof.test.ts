import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {digest, evidenceCurrent} from '../src/task-execution.ts';
import {TaskStore} from '../src/task-store.ts';
import {executeTaskTest} from '../src/test-runner.ts';

test('persisted Python summary evidence expires and instrumented reruns survive reload', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-legacy-proof-'));
  try {
    const oracle = path.join(root, 'oracle.py');
    const contract = path.join(root, 'contract.md');
    const storage = path.join(root, 'tasks.json');
    fs.writeFileSync(oracle, 'import unittest\nclass Oracle(unittest.TestCase):\n def test_value(self): self.assertEqual(1,1)\n');
    fs.writeFileSync(contract, 'approved contract');
    const command = 'python -m unittest oracle.py';
    const store = new TaskStore(storage);
    const task = store.createTask({title:'Proof', description:'', contractId:'app-proof.md', testCommand:command});
    task.status = 'done';
    task.testReport = {lastRun:new Date().toISOString(), success:true, status:'PASS', verifiedOracle:true,
      durationMs:1, passedTests:1, failedTests:0, output:'Ran 1 test, OK', command,
      cwd:root, contractId:task.contractId, evidence:{[oracle]:digest(oracle), [contract]:digest(contract)}};
    fs.writeFileSync(storage, JSON.stringify([task]));
    assert.equal(evidenceCurrent(task), false);
    const restored = new TaskStore(storage).getTask(task.id)!;
    assert.equal(restored.status, 'ready');
    assert.equal(restored.testReport!.status, 'SKIP');
    const report = await executeTaskTest(command, root, {}, oracle);
    Object.assign(report, {command, cwd:root, contractId:task.contractId, evidence:task.testReport.evidence});
    const reopened = new TaskStore(storage);
    reopened.recordTestReport(task.id, report);
    assert.equal(evidenceCurrent(new TaskStore(storage).getTask(task.id)!), true);
  } finally { fs.rmSync(root, {recursive:true, force:true}); }
});
