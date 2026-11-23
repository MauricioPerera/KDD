import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { callbackMatch } from './events.mjs';

export async function delegate(services, role, peerId, message) {
  const { report, save, sender, journal, mcp, replyTimeoutMs, onCheckpoint } = services;
  const { threadId } = report;
  assert.ok(message.length <= 4000);
  const step = report.tasks[role] ??= { peerId, taskId: randomUUID(), message };
  assert.equal(step.peerId, peerId, 'Task intent changed.');
  assert.equal(step.message, message, 'Task intent changed.');
  const { taskId } = step;
  if (!step.sent) {
    save();
    const sent = await mcp('send_task', { peerId, taskId, threadId, message });
    assert.equal(sent.task.taskId, taskId);
    assert.equal(sent.task.threadId, threadId);
    step.sent = true;
    save();
  }
  if (!step.inboundEventId) {
    const inbound = await journal.waitFor(callbackMatch({ agent: peerId, peerId: sender, taskId, threadId },
      'task.received'), role + ' admission');
    step.inboundEventId = inbound.eventId;
    save();
  }
  const { inboundEventId } = step;
  if (!report[role]) {
    const matchesReply = callbackMatch({ agent: sender, peerId, taskId, threadId }, 'task.replied');
    const failed = row => row.agent === peerId && row.eventId === inboundEventId &&
      (row.event === 'agent.failed' || (row.event === 'runner.ack' && row.status === 'failed'));
    const notification = await journal.waitFor(row => matchesReply(row) || failed(row), role + ' response', replyTimeoutMs);
    assert.ok(matchesReply(notification), role + ' failed for ' + inboundEventId);
    const result = await mcp('get_task_result', { peerId, taskId }, notification.eventId);
    assert.equal(result.taskId, taskId);
    assert.equal(result.threadId, threadId);
    assert.equal(result.status, 'replied');
    assert.equal(typeof result.reply, 'string');
    report[role] = { peerId, taskId, inboundEventId, replyEventId: notification.eventId, reply: result.reply };
    save();
    await onCheckpoint?.({ phase: role + '.reply_saved', threadId, taskId, eventId: notification.eventId });
  }
  if (!step.completed) {
    const terminal = await journal.waitFor(row => row.agent === peerId && row.eventId === inboundEventId &&
      (role === 'executor' ? ['agent.completed', 'agent.failed'].includes(row.event) : row.event === 'runner.ack'),
    role + ' completion');
    if (role === 'executor') {
      assert.equal(terminal.event, 'agent.completed');
      assert.equal(terminal.runtime, 'codex');
      assert.ok(terminal.tools.includes('reply_task'));
    } else assert.equal(terminal.status, 'completed');
    step.completed = true;
    save();
  }
  return report[role].reply;
}
