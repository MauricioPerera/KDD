import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs';
import { isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { delegate } from './delegation.mjs';
import { followReceiver } from './events.mjs';
import { openRun } from './state.mjs';

const task = 'commit-message-length-config';
const contract = `knowledge/contracts/${task}.md`;
const target = 'scripts/validate_commit_message.py';
const oracle = 'tests/test_commit_message_length_config.py';
const previousOracle = 'tests/test_validate_commit_message.py';
const previousContract = 'knowledge/contracts/commit-message-gate.md';
const candidateTool = fileURLToPath(new URL('./candidate.py', import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const digest = path => hash(readFileSync(path));
const changedTarget = ' M ' + target;
const finished = new Set(['verified', 'review_has_finding']);

function replyJson(reply) {
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

function reviewPrompt(diff) {
  const guard = diff.split('\n').find(line => line.startsWith('+    if '));
  assert.ok(guard, 'Expected an added CLI guard.');
  return 'Goldfish review. Python ' + guard.slice(5).trimEnd() + ' return CONFIG_INVALID. ' +
    'Should reject True and allow 0. Check both against this code. ' +
    'Call reply_task with one short line starting PASS or FINDING and state both results.';
}

function commands(report, save, env) {
  function command(exe, args, input) {
    const result = spawnSync(exe, args, { env, input, encoding: 'utf8', timeout: 150_000,
      maxBuffer: 4 * 1024 * 1024, windowsHide: true });
    if (result.error) throw result.error;
    return { exe, args, exit: result.status, stdout: result.stdout, stderr: result.stderr };
  }
  return {
    check(step, exe, args, expected = 0, input) {
      const saved = report.checks.find(row => row.step === step && row.exit === expected);
      if (saved) {
        assert.deepEqual([saved.exe, saved.args], [exe, args]);
        return saved;
      }
      const result = { step, ...command(exe, args, input) };
      report.checks.push(result);
      save();
      assert.equal(result.exit, expected, `${exe} ${args.join(' ')}`);
      return result;
    },
    git(...args) {
      const result = command('git', args);
      assert.equal(result.exit, 0, result.stderr);
      return result.stdout;
    },
  };
}

function verifyCheckout(report, git, save) {
  const base = git('rev-parse', 'HEAD').trim();
  const changes = git('status', '--porcelain').trimEnd();
  const protectedPaths = [contract, oracle, previousOracle, previousContract];
  const fingerprints = Object.fromEntries(protectedPaths.map(path => [path, digest(path)]));
  assert.match(git('branch', '--show-current').trim(), /^codex\/kdd-mcp-events-goldfish(?:[-/].*)?$/);
  if (!report.base) {
    assert.equal(changes, '', 'Start in a clean pilot worktree.');
    Object.assign(report, { base, fingerprints, targetBaseSha: digest(target) });
    save();
  }
  assert.equal(base, report.base, 'The base SHA changed.');
  assert.deepEqual(fingerprints, report.fingerprints);
  if (report.candidate) assert.equal(changes, changedTarget);
  else assert.ok(changes === '' || (report.candidatePlan && changes === changedTarget), 'Unexpected worktree changes.');
  const actual = digest(target);
  if (report.candidate) assert.equal(actual, report.candidate.sha256);
  else assert.ok(actual === report.targetBaseSha || actual === report.candidatePlan?.sha256, 'Unexpected target contents.');
}

function materialize(proposal, report, check, git, python, save) {
  const preview = check('candidate.preview', python, [candidateTool, '--preview'], 0, JSON.stringify(proposal)).stdout;
  const sha256 = hash(preview);
  if (!report.candidatePlan) {
    report.candidatePlan = { sha256 };
    save();
  }
  assert.equal(report.candidatePlan.sha256, sha256);
  const actual = digest(target);
  if (actual !== sha256) {
    assert.equal(actual, report.targetBaseSha);
    const directory = '.agents/logs';
    const temporary = directory + '/mcp-events-' + report.threadId + '-candidate.tmp';
    mkdirSync(directory, { recursive: true });
    writeFileSync(temporary, preview, 'utf8');
    renameSync(temporary, target);
  }
  assert.equal(digest(target), sha256);
  assert.equal(git('status', '--porcelain').trimEnd(), changedTarget);
  const diff = git('diff', '--', target);
  if (report.candidate) assert.deepEqual(report.candidate, { sha256, diff });
  else {
    report.candidate = { sha256, diff };
    save();
  }
  return diff;
}

export async function run(argv, hooks = {}) {
  const [host, endpoint, sender, evidenceArg, mode] = argv;
  const resume = mode === '--resume';
  assert.ok(argv.length === 4 || (argv.length === 5 && resume), 'Expected HOST URL OWNER EVIDENCE [--resume].');
  const python = process.env.KDD_PYTHON || 'python';
  const replyTimeoutMs = Number(process.env.KDD_MCP_REPLY_TIMEOUT_MS ?? 650_000);
  const { KDD_MCP_OWNER_TOKEN: token, ...childEnv } = process.env;
  assert.ok(Number.isInteger(replyTimeoutMs) && replyTimeoutMs >= 1_000 && replyTimeoutMs <= 700_000);
  assert.match(host ?? '', /^[A-Za-z0-9][A-Za-z0-9_.-]*$/);
  assert.match(sender ?? '', /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
  const url = new URL(endpoint);
  assert.equal(url.protocol, 'https:');
  assert.equal(url.pathname, '/agent/mcp');
  assert.ok(!url.username && !url.password && !url.search && !url.hash && token);
  const evidence = resolve(evidenceArg);
  const evidenceRelative = relative(process.cwd(), evidence);
  assert.ok(isAbsolute(evidenceArg) && (isAbsolute(evidenceRelative) || evidenceRelative.startsWith('..' + sep)),
    'Use an absolute evidence path outside the candidate worktree.');

  const identity = { task, root: realpathSync(process.cwd()), host, endpoint: url.href, sender };
  const store = openRun(evidence, resume ? undefined : {
    schema: 2, identity, task, threadId: randomUUID(), status: 'running',
    events: [], calls: [], checks: [], tasks: {}, attempts: [],
  });
  const { report, save } = store;
  const { threadId } = report;
  const { check, git } = commands(report, save, childEnv);
  let journal;
  let authorized = false;

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

  function receipt() {
    console.log(JSON.stringify({ task, threadId, status: report.status, executor: report.executor.taskId,
      goldfish: report.goldfish.taskId, evidence }));
    return report.status === 'verified' ? 0 : 1;
  }

  try {
    assert.deepEqual(report.identity, identity, 'This checkpoint belongs to a different invocation.');
    assert.match(threadId, /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/);
    verifyCheckout(report, git, save);
    if (finished.has(report.status)) return receipt();
    authorized = true;
    report.status = 'running';
    delete report.error;
    report.attempts.push({ pid: process.pid, resume, at: new Date().toISOString() });
    save();
    check('base.contracts', python, ['scripts/validate_contracts.py', 'knowledge/contracts']);
    check('base.context', python, ['scripts/assemble_context.py', 'ccdd/context.json',
      'Validate max_subject_length at the CLI boundary under commit-message-length-config.']);
    check('base.previous-oracle', python, ['-m', 'unittest', previousOracle]);
    const red = check('base.regression', python, ['-m', 'unittest', oracle], 1);
    assert.match(red.stderr, /test_rejects_invalid_lengths_without_raising/);
    journal = followReceiver(host, threadId, (row, cursor) => {
      report.events.push(row);
      if (cursor) report.cursor = cursor;
      save();
    }, childEnv, { cursor: report.cursor, history: report.events });
    await journal.waitFor(row => row.event === 'journal.ready', 'SSH journal', 15_000);
    console.log(JSON.stringify({ task, threadId, base: report.base, status: 'waiting_for_events', resume }));
    await hooks.onCheckpoint?.({ phase: 'journal.ready', threadId, resume, journal });
    const services = { report, save, journal, sender, mcp, replyTimeoutMs, onCheckpoint: hooks.onCheckpoint };
    const message = report.tasks.executor?.message ?? proposalPrompt(report.base);
    const proposal = replyJson(await delegate(services, 'executor', 'alpha', message));
    const diff = materialize(proposal, report, check, git, python, save);
    const reviewText = await delegate(services, 'goldfish', 'delta', reviewPrompt(diff));
    const verdict = /^(PASS|FINDING)\b[\s:–-]*([\s\S]+)/i.exec(reviewText.trim());
    assert.ok(verdict && verdict[2].trim(), 'Expected a Goldfish verdict with the observed cases.');
    report.review = { verdict: verdict[1].toLowerCase(), reason: verdict[2].trim() };
    save();
    check('candidate.perimeter', python, ['scripts/validate_perimeter.py', contract, '--changed', target]);
    check('candidate.contracts', python, ['scripts/validate_contracts.py', 'knowledge/contracts']);
    for (let pass = 1; pass <= 2; pass++) check('candidate.tests.' + pass, python, ['-m', 'unittest', previousOracle, oracle]);
    check('candidate.diff', 'git', ['diff', '--check']);
    verifyCheckout(report, git, save);
    report.status = report.review.verdict === 'pass' ? 'verified' : 'review_has_finding';
    save();
    return receipt();
  } catch (error) {
    if (authorized) {
      report.status = 'failed';
      report.error = String(error);
      save();
    }
    console.error(String(error));
    return 1;
  } finally {
    journal?.close();
    store.close();
  }
}

if (import.meta.main) process.exitCode = await run(process.argv.slice(2));
