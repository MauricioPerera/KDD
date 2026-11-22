import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { isAbsolute, relative, resolve } from 'node:path';
import { callbackMatch, followReceiver } from './events.mjs';

const task = 'commit-message-length-config';
const contract = `knowledge/contracts/${task}.md`;
const target = 'scripts/validate_commit_message.py';
const oracle = 'tests/test_commit_message_length_config.py';
const previousOracle = 'tests/test_validate_commit_message.py';
const previousContract = 'knowledge/contracts/commit-message-gate.md';
const [host, endpoint, sender, evidenceArg] = process.argv.slice(2);
const python = process.env.KDD_PYTHON || 'python';
const { KDD_MCP_OWNER_TOKEN: token, ...childEnv } = process.env;
assert.match(host ?? '', /^[A-Za-z0-9][A-Za-z0-9_.-]*$/);
assert.match(sender ?? '', /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
const url = new URL(endpoint);
assert.equal(url.protocol, 'https:');
assert.equal(url.pathname, '/agent/mcp');
assert.ok(!url.username && !url.password && !url.search && !url.hash && token);
const evidence = resolve(evidenceArg);
assert.ok(relative(process.cwd(), evidence).startsWith('..') && isAbsolute(evidenceArg),
  'Use an absolute evidence path outside the candidate worktree.');

const threadId = randomUUID();
const report = { schema: 1, task, threadId, status: 'running', events: [], calls: [], checks: [] };
writeFileSync(evidence, '', { flag: 'wx' });
function save() {
  writeFileSync(evidence, JSON.stringify(report, null, 2) + '\n');
}
function command(exe, args, input) {
  const result = spawnSync(exe, args, { env: childEnv, input, encoding: 'utf8', timeout: 150_000,
    maxBuffer: 4 * 1024 * 1024, windowsHide: true });
  if (result.error) throw result.error;
  return { exe, args, exit: result.status, stdout: result.stdout, stderr: result.stderr };
}
function check(exe, args, expected = 0, input) {
  const result = command(exe, args, input);
  report.checks.push(result);
  save();
  assert.equal(result.exit, expected, `${exe} ${args.join(' ')}`);
  return result.stdout;
}
function git(...args) {
  const result = command('git', args);
  assert.equal(result.exit, 0, result.stderr);
  return result.stdout;
}
function digest(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}
async function mcp(name, args, eventId) {
  const entry = { name, ...args, ...(eventId && { eventId }) };
  report.calls.push(entry);
  save();
  const response = await fetch(url, {
    method: 'POST', redirect: 'error', signal: AbortSignal.timeout(20_000),
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream' },
    body: JSON.stringify({ jsonrpc: '2.0', id: report.calls.length, method: 'tools/call',
      params: { name, arguments: args } }),
  });
  assert.ok(response.ok, `Owner MCP returned HTTP ${response.status} for ${name}`);
  const body = await response.json();
  assert.ok(!body.error && !body.result?.isError && body.result?.structuredContent,
    'Owner MCP call failed: ' + name);
  return body.result.structuredContent;
}
function replyJson(reply) {
  assert.equal(typeof reply, 'string');
  const clean = reply.trim().replace(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i, '$1');
  const value = JSON.parse(clean);
  assert.equal(Object.getPrototypeOf(value), Object.prototype);
  return value;
}
function proposalPrompt(base) {
  const source = readFileSync(target, 'utf8').replace(/\r\n/g, '\n');
  const start = source.indexOf('    required_keys =');
  const end = source.indexOf('    # Determine message source', start);
  assert.ok(start > 0 && end > start);
  return [
    `KDD task ${task}, base ${base}. Propose the missing CLI guard.`,
    'Current code immediately before reading the message:',
    source.slice(start, end),
    'The insertion point is after required key checks. A local variable length contains the configured value.',
    'A valid value is an integer greater than or equal to zero. Booleans, floats, strings, null, lists, dicts and negatives are invalid.',
    'Return one JSON object with exactly two keys: guard (single-line Python expression true for invalid values) and diagnostic (plain ASCII, mentioning max_subject_length).',
    'You can use length, type(length), int, comparison operators and short-circuit boolean operators. The caller emits CONFIG_INVALID and exit 1 if your expression is true.',
  ].join('\n');
}
function reviewPrompt(base, diff) {
  return [
    `Act as a fresh, read-only KDD Goldfish. Task ${task}, base ${base}.`,
    'Review the candidate source below against the approved interface of the existing CLI:',
    'max_subject_length accepts nonnegative integers including zero. Boolean, null, string, float, negative, list and dictionary inputs must report CONFIG_INVALID and exit 1.',
    'Zero may emit SUBJECT_TOO_LONG, which is a non-blocking warning. Existing missing-key behavior stays the same.',
    'The frozen regression checks every invalid type above and valid values 0 and 72.',
    'Return one JSON object with verdict ("pass" or "finding"), case (a concrete input and expected outcome) and reason (why the candidate passes or fails that case). Review just the supplied material.',
    diff,
  ].join('\n');
}
async function dispatch(journal, peerId, message, role) {
  const taskId = randomUUID();
  assert.ok(message.length <= 4000);
  const sent = await mcp('send_task', { peerId, taskId, threadId, message });
  assert.equal(sent.task.taskId, taskId);
  assert.equal(sent.task.threadId, threadId);
  const inbound = await journal.waitFor(callbackMatch({ agent: peerId, peerId: sender, taskId, threadId },
    'task.received'), role + ' admission');
  const notification = await journal.waitFor(callbackMatch({ agent: sender, peerId, taskId, threadId },
    'task.replied'), role + ' response');
  const result = await mcp('get_task_result', { peerId, taskId }, notification.eventId);
  assert.equal(result.taskId, taskId);
  assert.equal(result.threadId, threadId);
  assert.equal(result.status, 'replied');
  report[role] = { peerId, taskId, inboundEventId: inbound.eventId,
    replyEventId: notification.eventId, reply: result.reply };
  const terminal = await journal.waitFor(row => row.agent === peerId && row.eventId === inbound.eventId &&
    (role === 'executor' ? ['agent.completed', 'agent.failed'].includes(row.event) : row.event === 'runner.ack'),
  role + ' completion');
  if (role === 'executor') {
    assert.equal(terminal.event, 'agent.completed');
    assert.equal(terminal.runtime, 'codex');
    assert.ok(terminal.tools.includes('reply_task'));
  } else assert.equal(terminal.status, 'completed');
  save();
  return result.reply;
}

let journal;
try {
  const base = git('rev-parse', 'HEAD').trim();
  assert.match(git('branch', '--show-current').trim(), /^codex\/kdd-mcp-events-goldfish(?:[-/].*)?$/);
  assert.equal(git('status', '--porcelain'), '', 'Start in a clean pilot worktree.');
  const protectedPaths = [contract, oracle, previousOracle, previousContract];
  const fingerprints = Object.fromEntries(protectedPaths.map(path => [path, digest(path)]));
  Object.assign(report, { base, fingerprints });
  check(python, ['scripts/validate_contracts.py', 'knowledge/contracts']);
  check(python, ['scripts/assemble_context.py', 'ccdd/context.json',
    'Validate max_subject_length at the CLI boundary under commit-message-length-config.']);
  check(python, ['-m', 'unittest', previousOracle]);
  check(python, ['-m', 'unittest', oracle], 1);
  assert.match(report.checks.at(-1).stderr, /test_rejects_invalid_lengths_without_raising/);

  journal = followReceiver(host, threadId, row => {
    report.events.push(row);
    save();
  });
  await journal.waitFor(row => row.event === 'journal.ready', 'SSH journal', 15_000);
  console.log(JSON.stringify({ task, threadId, base, status: 'waiting_for_events' }));
  const proposal = replyJson(await dispatch(journal, 'alpha', proposalPrompt(base), 'executor'));
  check(python, ['examples/mcp-events-kdd/candidate.py'], 0, JSON.stringify(proposal));
  assert.equal(git('rev-parse', 'HEAD').trim(), base);
  assert.equal(git('status', '--porcelain').trimEnd(), ' M ' + target);
  const diff = git('diff', '--', target);
  const candidate = digest(target);
  report.candidate = { sha256: candidate, diff };
  const review = replyJson(await dispatch(journal, 'delta', reviewPrompt(base, diff), 'goldfish'));
  assert.deepEqual(Object.keys(review).sort(), ['case', 'reason', 'verdict']);
  assert.ok(typeof review.case === 'string' && review.case.trim() &&
    typeof review.reason === 'string' && review.reason.trim());
  assert.ok(['pass', 'finding'].includes(review.verdict));
  report.review = review;
  save();

  check(python, ['scripts/validate_perimeter.py', contract, '--changed', target]);
  check(python, ['scripts/validate_contracts.py', 'knowledge/contracts']);
  for (let pass = 0; pass < 2; pass++) check(python, ['-m', 'unittest', previousOracle, oracle]);
  check('git', ['diff', '--check']);
  assert.equal(digest(target), candidate);
  assert.equal(git('rev-parse', 'HEAD').trim(), base);
  assert.equal(git('status', '--porcelain').trimEnd(), ' M ' + target);
  assert.deepEqual(Object.fromEntries(protectedPaths.map(path => [path, digest(path)])), fingerprints);
  report.status = review.verdict === 'pass' ? 'verified' : 'review_has_finding';
  console.log(JSON.stringify({ task, threadId, status: report.status, executor: report.executor.taskId,
    goldfish: report.goldfish.taskId, evidence }));
  if (report.status !== 'verified') process.exitCode = 1;
} catch (error) {
  report.status = 'failed';
  report.error = String(error);
  console.error(report.error);
  process.exitCode = 1;
} finally {
  journal?.close();
  save();
}
