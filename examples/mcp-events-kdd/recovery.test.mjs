import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { openRun } from './state.mjs';
import { delegate } from './delegation.mjs';

function fixture() {
  const evidence = join(mkdtempSync(join(tmpdir(), 'kdd-events-')), 'evidence.json');
  const store = openRun(evidence, {
    schema: 2, threadId: 'thread-1', tasks: {}, calls: [], events: [],
  });
  return { evidence, store };
}

function services(store, calls) {
  const { report, save } = store;
  const observations = [
    { event: 'event.received', name: 'task.received', duplicate: false, agent: 'alpha',
      eventId: 'inbound', peerId: 'beta', threadId: report.threadId },
    { event: 'event.received', name: 'task.replied', duplicate: false, agent: 'beta',
      eventId: 'reply', peerId: 'alpha', threadId: report.threadId },
    { event: 'agent.completed', eventId: 'inbound', agent: 'alpha', runtime: 'codex', tools: ['reply_task'] },
  ];
  return {
    report, save, sender: 'beta', replyTimeoutMs: 1000,
    journal: { waitFor: async predicate => {
      const row = observations.find(value => predicate({ ...value, taskId: report.tasks.executor.taskId }));
      assert.ok(row);
      return { ...row, taskId: report.tasks.executor.taskId };
    } },
    mcp: async (name, args) => {
      calls.push([name, args]);
      const identity = { taskId: args.taskId, threadId: report.threadId };
      return name === 'send_task' ? { task: identity } : { ...identity, status: 'replied', reply: 'one reply' };
    },
  };
}

test('a saved reply and completed task survive restart and a repeated callback', async () => {
  const { store, evidence } = fixture();
  const calls = [];
  const first = services(store, calls);
  first.onCheckpoint = async ({ phase }) => {
    if (phase === 'executor.reply_saved') throw Error('abort at the durable reply');
  };
  await assert.rejects(delegate(first, 'executor', 'alpha', 'original'), /durable reply/);
  assert.equal(store.report.executor.reply, 'one reply');
  assert.equal(JSON.parse(readFileSync(evidence, 'utf8')).executor.replyEventId, 'reply');
  const originalId = store.report.tasks.executor.taskId;
  store.close();
  const resumed = openRun(evidence);
  try {
    resumed.report.events.push({ event: 'event.received', eventId: 'reply', duplicate: true });
    resumed.save();
    assert.equal(await delegate(services(resumed, calls), 'executor', 'alpha', 'original'), 'one reply');
    assert.equal(await delegate(services(resumed, calls), 'executor', 'alpha', 'original'), 'one reply');
    assert.equal(resumed.report.threadId, 'thread-1');
    assert.equal(resumed.report.tasks.executor.taskId, originalId);
    assert.deepEqual(calls.map(call => call[0]), ['send_task', 'get_task_result']);
  } finally { resumed.close(); }
});

test('an ambiguous send resumes with the original task and message identity', async () => {
  const { store, evidence } = fixture();
  const calls = [];
  const first = services(store, calls);
  first.mcp = async (name, args) => {
    calls.push([name, args]);
    throw Error('lost send receipt');
  };
  await assert.rejects(delegate(first, 'executor', 'alpha', 'original'), /lost send receipt/);
  store.close();
  const resumed = openRun(evidence);
  try {
    await assert.rejects(delegate(services(resumed, calls), 'executor', 'alpha', 'changed'), /task intent/i);
    await delegate(services(resumed, calls), 'executor', 'alpha', 'original');
    assert.deepEqual(calls[0], calls[1]);
    assert.equal(calls[2][0], 'get_task_result');
  } finally { resumed.close(); }
});

test('a second process owner cannot resume while a writer is open', () => {
  const { store, evidence } = fixture();
  assert.throws(() => openRun(evidence), /locked|another orchestrator/i);
  store.close();
  const resumed = openRun(evidence);
  assert.equal(resumed.report.threadId, 'thread-1');
  resumed.close();
});
