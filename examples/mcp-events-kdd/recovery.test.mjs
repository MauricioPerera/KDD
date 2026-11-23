import assert from 'node:assert/strict';
import childProcess, { spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { PassThrough } from 'node:stream';
import { mock, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { openRun } from './state.mjs';
import { delegate } from './delegation.mjs';
import { followReceiver } from './events.mjs';

const eventId = number => 'evt_' + number.toString(16).padStart(32, '0');

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

test('a new process replays the journal and sends one Goldfish request on the saved thread', async context => {
  const directory = mkdtempSync(join(tmpdir(), 'kdd-events-restart-'));
  context.after(() => {
    assert.equal(resolve(directory, '..'), resolve(tmpdir()));
    rmSync(directory, { recursive: true });
  });
  const evidence = join(directory, 'evidence.json');
  const checkpoint = spawnSync(process.execPath, [
    fileURLToPath(new URL('./recovery-checkpoint.mjs', import.meta.url)), evidence,
  ], { encoding: 'utf8', timeout: 10000 });
  assert.equal(checkpoint.error, undefined);
  assert.equal(checkpoint.status, 17, checkpoint.stderr);

  const resumed = openRun(evidence);
  const { report, save } = resumed;
  const original = structuredClone(report.executor);
  const threadId = report.threadId;
  const journalProcess = new EventEmitter();
  journalProcess.stdout = new PassThrough();
  journalProcess.kill = () => journalProcess.stdout.end();
  const transport = mock.method(childProcess, 'spawn', (command, args) => {
    assert.equal(command, 'ssh');
    assert.match(args.at(-1), /--after-cursor="executor-reply"/);
    return journalProcess;
  });
  syncBuiltinESMExports();
  let journal;

  function append(event, cursor) {
    const row = { _SYSTEMD_UNIT: 'agent-mcp-federation-receiver.service',
      __CURSOR: cursor, MESSAGE: JSON.stringify({ ...event, threadId }) };
    journalProcess.stdout.write(JSON.stringify(row) + '\n');
  }

  try {
    journal = followReceiver('test.invalid', threadId, (event, cursor) => {
      report.events.push(event);
      report.cursor = cursor;
      save();
    }, process.env, { cursor: report.cursor, history: report.events });
    append({ event: 'event.received', name: 'task.replied', eventId: original.replyEventId,
      agent: 'beta', peerId: 'alpha', taskId: original.taskId, duplicate: true }, 'executor-replay');
    append({ event: 'agent.completed', eventId: original.inboundEventId,
      agent: 'alpha', runtime: 'codex', tools: ['reply_task'] }, 'executor-completed');

    const services = { report, save, journal, sender: 'beta', replyTimeoutMs: 2000,
      async mcp(name, args, replyEventId) {
        assert.equal(args.peerId, 'delta');
        const { taskId } = args;
        const identity = { taskId, threadId };
        report.calls.push({ name, taskId });
        if (name === 'send_task') {
          assert.equal(args.threadId, threadId);
          append({ event: 'event.received', name: 'task.received', eventId: eventId(3),
            agent: 'delta', peerId: 'beta', taskId, duplicate: false }, 'goldfish-admitted');
          const reply = { event: 'event.received', name: 'task.replied',
            eventId: eventId(4), agent: 'beta', peerId: 'delta', taskId };
          append({ ...reply, duplicate: true }, 'goldfish-replay');
          append({ ...reply, eventId: eventId(5), duplicate: false }, 'goldfish-reply');
          append({ event: 'runner.ack', eventId: eventId(3),
            agent: 'delta', status: 'completed' }, 'goldfish-completed');
          return { task: identity };
        }
        assert.equal(name, 'get_task_result');
        assert.equal(replyEventId, eventId(5));
        return { ...identity, status: 'replied', reply: 'PASS' };
      },
    };

    assert.equal(await delegate(services, 'executor', 'alpha', 'original'), original.reply);
    assert.equal(await delegate(services, 'goldfish', 'delta', 'review'), 'PASS');
    assert.equal(await delegate(services, 'goldfish', 'delta', 'review'), 'PASS');
    assert.deepEqual(report.executor, original);
    assert.equal(report.threadId, 'thread-1');
    assert.ok(report.events.some(row => row.eventId === original.replyEventId && row.duplicate));
    assert.equal(report.cursor, 'goldfish-completed');
    assert.deepEqual(report.calls.map(({ name }) => name),
      ['send_task', 'get_task_result', 'send_task', 'get_task_result']);
    assert.deepEqual(report.calls.map(({ taskId }) => taskId),
      [original.taskId, original.taskId, report.goldfish.taskId, report.goldfish.taskId]);
  } finally {
    journal?.close();
    transport.mock.restore();
    syncBuiltinESMExports();
    resumed.close();
  }
});
