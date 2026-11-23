import assert from 'node:assert/strict';
import { delegate } from './delegation.mjs';
import { openRun } from './state.mjs';

function eventId(number) {
  return 'evt_' + number.toString(16).padStart(32, '0');
}

const evidence = process.argv[2];
const store = openRun(evidence, {
  schema: 2, threadId: 'thread-1', tasks: {}, calls: [], events: [],
});
const { report, save } = store;
const threadId = report.threadId;
const journal = {
  async waitFor(predicate) {
    const { taskId } = report.tasks.executor;
    const find = [
      { event: 'event.received', name: 'task.received', eventId: eventId(1),
        agent: 'alpha', peerId: 'beta', duplicate: false },
      { event: 'event.received', name: 'task.replied', eventId: eventId(2),
        agent: 'beta', peerId: 'alpha', duplicate: false },
    ].map(event => ({ ...event, threadId, taskId })).find(predicate);
    assert.ok(find);
    return find;
  },
};
await delegate({
  report, save, journal, sender: 'beta', replyTimeoutMs: 2000,
  async mcp(name, args) {
    const { taskId } = args;
    const identity = { taskId, threadId };
    report.calls.push({ name, taskId });
    if (name === 'send_task') return { task: identity };
    assert.equal(name, 'get_task_result');
    return { ...identity, status: 'replied', reply: 'one reply' };
  },
  async onCheckpoint({ phase }) {
    assert.equal(phase, 'executor.reply_saved');
    report.cursor = 'executor-reply';
    save();
    process.exit(17);
  },
}, 'executor', 'alpha', 'original');
