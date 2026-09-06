import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { TaskStore } from '../src/task-store.ts';
import { executeTaskTest } from '../src/test-runner.ts';
import { BlindVault } from '../src/blind-vault.ts';

test('completion rejects absent evidence and unknown states', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-hardening-'));
  try {
    const store = new TaskStore(path.join(dir, 'tasks.json'));
    const task = store.createTask({title: 'unverified', description: ''});
    assert.throws(() => store.updateTaskStatus(task.id, 'done'), /evidence|contract/i);
    assert.throws(() => store.updateTaskStatus(task.id, 'invalid' as any), /status/i);
    assert.equal(store.getTask(task.id)?.status, 'backlog');
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});

test('a successful process without tests never counts as a passing test', async () => {
  const report = await executeTaskTest('echo audit-no-tests', process.cwd());
  assert.equal(report.success, true);
  assert.equal(report.passedTests, 0);
  assert.equal(report.failedTests, 0);
});

test('runner recognizes TAP totals and preserves failure exit status', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-runner-'));
  try {
    fs.writeFileSync(path.join(dir, 'oracle.cjs'), "const {test}=require('node:test'); const assert=require('node:assert/strict'); test('actual oracle',()=>assert.equal(2+2,4));");
    const report = await executeTaskTest('node --test --test-reporter=tap oracle.cjs', dir);
    assert.equal(report.success, true);
    assert.equal(report.passedTests, 1);
    const failure = await executeTaskTest('node -e "process.exit(1)"', dir);
    assert.equal(failure.success, false);
    assert.equal(failure.passedTests, 0);
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});

test('vault round trips escaped values and does not resurrect deleted keys', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-vault-'));
  try {
    const file = path.join(dir, '.env.local');
    const vault = new BlindVault(file);
    const value = 'canary"with\\escape\nand newline';
    vault.setSecret('CANARY', value);
    assert.equal(new BlindVault(file).getSecretValue('CANARY'), value);
    fs.writeFileSync(file, '');
    assert.equal(vault.hasSecret('CANARY'), false);
  } finally { fs.rmSync(dir, {recursive: true, force: true}); }
});
