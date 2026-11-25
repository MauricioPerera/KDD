import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

const repo = fileURLToPath(new URL('../../../..', import.meta.url));
const pilot = fileURLToPath(new URL('..', import.meta.url));
const runner = path.join(pilot, 'run.mjs');
const pins = JSON.parse(fs.readFileSync(path.join(pilot, 'pins.json'), 'utf8'));
const knownReport = JSON.parse(fs.readFileSync(new URL('report-v1-pilot.json', import.meta.url), 'utf8'));
const ids = knownReport.run.results.map(result => result.testId).sort();
const sha256 = value => createHash('sha256').update(value).digest('hex');

function temporary(t, close = () => {}) {
  const parent = fs.realpathSync(os.tmpdir());
  const relative = path.relative(fs.realpathSync(repo), parent);
  assert.ok(path.isAbsolute(relative) || relative.split(path.sep)[0] === '..',
    'Set the temporary directory outside the checkout');
  const directory = fs.mkdtempSync(path.join(parent, 'kdd-board-browser-live-'));
  t.after(async () => {
    await close();
    fs.rmSync(directory, {force: true, recursive: true});
  });
  return directory;
}

function invoke(tool, args, options = {}) {
  const result = spawnSync(tool, args, {cwd: repo, encoding: 'utf8', timeout: 70000, ...options});
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return result;
}

function verdict(result, ok) {
  assert.equal(result.status, ok ? 0 : 1, result.stdout + result.stderr);
  const body = JSON.parse(result.stdout);
  assert.equal(body.ok, ok);
  return body;
}

function approvedRef() {
  const ref = process.env.KDD_PILOT_APPROVED_REF;
  assert.match(ref ?? '', /^[0-9a-f]{40}$/, 'Use a full baseline SHA to run the opt-in live tests');
  return ref;
}

function runFresh(output, approved) {
  const started = Date.now();
  const result = invoke(process.execPath, [runner, '--approved-ref', approved, '--output', output]);
  const finished = Date.now();
  assert.deepEqual(verdict(result, true).ids, ids);
  const raw = fs.readFileSync(path.join(output, 'report.json'));
  const report = JSON.parse(raw);
  const receipt = JSON.parse(fs.readFileSync(path.join(output, 'receipt.json'), 'utf8'));
  const git = invoke('git', ['rev-parse', 'HEAD']);
  assert.equal(git.status, 0, git.stderr);
  assert.equal(receipt.checkout, git.stdout.trim());
  assert.equal(receipt.approved_ref, approved);
  assert.equal(receipt.report_sha256, sha256(raw));
  assert.equal(receipt.run_id, report.run.id);
  assert.notEqual(receipt.run_id, knownReport.run.id);
  const recordedStart = Date.parse(report.run.startedAt);
  const recordedEnd = Date.parse(report.run.finishedAt);
  assert.ok(started <= recordedStart && recordedStart <= recordedEnd && recordedEnd <= finished,
    'Report must have started and finished during this invocation');
  assert.equal(receipt.exit_code, 0);
  assert.deepEqual(receipt.ids, ids);
  assert.deepEqual(receipt.runtime, pins);
  assert.deepEqual(report.run.results.map(item => item.testId).sort(), ids);
  assert.deepEqual(report.run.summary, {discovered: 2, selected: 2, executed: 2, passed: 2,
    failed: 0, interrupted: 0, flaky: 0, skipped: 0});
  for (const relative of [
    'tools/kdd-board/package-lock.json', 'tools/kdd-board/tests/project-fixture.ts',
    'tools/kdd-board/tests/browser-pilot-receipt.test.mjs',
    ...['package.json', 'package-lock.json', 'pins.json', 'e2e.config.mjs', 'tests/fixture.mjs',
      'tests/handoff.e2e.ts', 'tests/pilot-live.test.mjs', 'tests/report-v1-pilot.json']
      .map(name => `tools/kdd-board/browser-pilot/${name}`),
  ]) {
    assert.equal(receipt.inputs[relative], sha256(fs.readFileSync(path.join(repo, relative))), relative);
  }
  return receipt.run_id;
}

test('two normal invocations generate distinct fresh Chromium evidence bound to the same checkout', t => {
  const root = temporary(t);
  const approved = approvedRef();
  const first = runFresh(path.join(root, 'first'), approved);
  const second = runFresh(path.join(root, 'second'), approved);
  assert.notEqual(first, second);
});

test('the normal command rejects an existing commit without the pilot baseline', t => {
  const output = path.join(temporary(t), 'evidence');
  const history = invoke('git', ['rev-list', '--max-parents=0', 'HEAD']);
  assert.equal(history.status, 0, history.stderr);
  const root = history.stdout.trim().split(/\s+/)[0];
  const contract = 'knowledge/contracts/board-browser-pilot.md';
  assert.notEqual(invoke('git', ['cat-file', '-e', `${root}:${contract}`]).status, 0);
  verdict(invoke(process.execPath, [runner, '--approved-ref', root, '--output', output]), false);
  assert.equal(fs.existsSync(path.join(output, 'receipt.json')), false);
});

test('the normal command leaves a destination with a previous green report intact', t => {
  const output = temporary(t);
  const file = path.join(output, 'report.json');
  fs.writeFileSync(file, JSON.stringify(knownReport));
  const previous = fs.readFileSync(file);
  verdict(invoke(process.execPath, [runner, '--approved-ref', approvedRef(), '--output', output]), false);
  assert.deepEqual(fs.readFileSync(file), previous);
  assert.deepEqual(fs.readdirSync(output), ['report.json']);
});

function gitState(repository, env) {
  const read = (...args) => {
    const result = invoke('git', args, {cwd: repository, env});
    assert.equal(result.status, 0, result.stderr);
    return result.stdout;
  };
  return [read('show-ref'), read('ls-files', '--stage'), read('status', '--porcelain=v1', '-uall')];
}

async function startFixture(directory, env) {
  const fixture = path.join(directory, 'repository');
  const descriptor = path.join(directory, 'board.json');
  const python = process.env.KDD_PYTHON || 'python';
  const server = spawn(process.execPath, [path.join(pilot, 'tests/fixture.mjs'), fixture, descriptor, python],
    {cwd: pilot, env, stdio: ['ignore', 'ignore', 'pipe']});
  let errors = '';
  server.stderr.setEncoding('utf8').on('data', chunk => { errors += chunk; });
  try {
    for (let count = 0; count < 300; count += 1) {
      assert.equal(server.exitCode, null, errors);
      if (fs.existsSync(descriptor) && fs.statSync(descriptor).size > 0) {
        return {fixture, descriptor, ready: JSON.parse(fs.readFileSync(descriptor, 'utf8')).ready, server};
      }
      await delay(100);
    }
    assert.fail(`Board fixture never started: ${errors}`);
  } catch (error) {
    server.kill();
    throw error;
  }
}

test('authentic Chromium failure and empty selection cannot produce a green receipt', async t => {
  let board;
  const directory = temporary(t, async () => {
    if (!board || board.exitCode !== null || board.signalCode !== null) return;
    const ended = once(board, 'exit');
    board.kill();
    await ended;
  });
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
    /^(PATH|HOME|COMSPEC|PATHEXT|SYSTEMROOT|WINDIR|USERPROFILE|LOCALAPPDATA|APPDATA|SYSTEMDRIVE|PLAYWRIGHT_BROWSERS_PATH|TMP|TEMP)$/i.test(key)));
  Object.assign(env, {CI: '1', E2E_TELEMETRY_DISABLED: '1', GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_GLOBAL: process.platform === 'win32' ? 'NUL' : '/dev/null'});
  const {fixture, descriptor, ready, server} = await startFixture(directory, env);
  board = server;
  env.KDD_BOARD_BROWSER_FIXTURE = descriptor;
  const project = path.join(directory, 'browser');
  fs.mkdirSync(path.join(project, 'tests'), {recursive: true});
  fs.copyFileSync(path.join(pilot, 'e2e.config.mjs'), path.join(project, 'e2e.config.mjs'));
  fs.copyFileSync(path.join(pilot, 'tests/handoff.e2e.ts'), path.join(project, 'tests/handoff.e2e.ts'));
  fs.symlinkSync(path.join(pilot, 'node_modules'), path.join(project, 'node_modules'), 'junction');
  const cli = path.join(pilot, 'node_modules/e2e/dist/cli/bin.js');
  const run = (out, extra = []) => invoke(process.execPath, [cli, 'run', 'tests/handoff.e2e.ts',
    '--config', 'e2e.config.mjs', '--workers', '1', '--retries', '0', '--no-cache', '--output', out, ...extra],
  {cwd: project, env});
  const verify = (file, exitCode) => invoke(process.execPath,
    [runner, '--verify-report', '--report', file, '--exit-code', String(exitCode)]);
  const state = gitState(fixture, env);
  const evidence = path.join(fixture, '.agents/logs/board-reviews/TASK-001', `${ready}.json`);
  const originalV1 = fs.readFileSync(evidence);
  const green = run('green');
  assert.equal(green.status, 0, green.stdout + green.stderr);
  assert.deepEqual(gitState(fixture, env), state);
  assert.deepEqual(fs.readFileSync(evidence), originalV1);
  const report = path.join(project, 'green/report.json');
  const old = fs.readFileSync(report);
  const empty = run('green', ['--grep', '^no-such-pilot-case$']);
  assert.equal(empty.status, 2, empty.stdout + empty.stderr);
  assert.match(empty.stdout + empty.stderr, /NO_TESTS|No tests/i);
  assert.deepEqual(fs.readFileSync(report), old);
  fs.unlinkSync(evidence);
  const failed = run('failed');
  assert.equal(failed.status, 1, failed.stdout + failed.stderr);
  const failedReport = path.join(project, 'failed/report.json');
  const red = JSON.parse(fs.readFileSync(failedReport, 'utf8')).run;
  assert.equal(red.summary.failed, 1);
  assert.equal(red.summary.passed, 1);
  assert.equal(red.results.find(item => item.testId === knownReport.run.results[0].testId).status, 'failed');
  assert.match(failed.stdout + failed.stderr, /ASSERTION_FAILED|assertion/i);
  assert.deepEqual(gitState(fixture, env), state);
  t.diagnostic('Chromium returned 0 for both cases, 2 for NO_TESTS with the old report intact, and 1 for the assertion failure');
  const verdicts = [verify(report, empty.status), verify(failedReport, failed.status)];
  for (const result of verdicts) verdict(result, false);
});
