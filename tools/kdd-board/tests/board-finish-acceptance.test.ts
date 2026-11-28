import assert from 'node:assert/strict';
import childProcess, {execFileSync, spawnSync} from 'node:child_process';
import {createHash, randomBytes} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import {syncBuiltinESMExports} from 'node:module';
import type {AddressInfo} from 'node:net';
import path from 'node:path';
import {after, test, type TestContext} from 'node:test';
import {setTimeout as delay} from 'node:timers/promises';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';
import {tempOutsideGit} from './project-fixture.ts';

const task = '/api/tasks/TASK-001';
const acceptance = task + '/acceptance';
const cli = fileURLToPath(new URL('../../../scripts/tasks.py', import.meta.url));
const prepare = fileURLToPath(new URL('../../../tests/fixtures/board_finish_acceptance.py', import.meta.url));
const python = process.env.KDD_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
let instance = 0;

// Observe the actual process call and forward it unchanged. Preserve execFile's promisified result shape.
type Launch = {args: string[]; timeout: number};
const launches = new Map<string, Launch[]>();
const nativeFile = childProcess.execFile;
const nativeSpawn = childProcess.spawn;
const promisedFile = promisify(nativeFile);

function observe(call: any[]) {
  const [, args, options] = call;
  if (!Array.isArray(args) || !args.includes('finish') || typeof options?.cwd !== 'string') return;
  launches.get(fs.realpathSync(options.cwd))?.push({args: [...args], timeout: options.timeout ?? 0});
}

const observedFile = (...call: any[]) => {
  observe(call);
  return Reflect.apply(nativeFile, childProcess, call);
};
Object.defineProperty(observedFile, promisify.custom, {value: (...call: any[]) => {
  observe(call);
  return Reflect.apply(promisedFile, childProcess, call);
}});
childProcess.execFile = observedFile as typeof nativeFile;
childProcess.spawn = ((...call: any[]) => {
  observe(call);
  return Reflect.apply(nativeSpawn, childProcess, call);
}) as typeof nativeSpawn;
syncBuiltinESMExports();
after(() => {
  childProcess.execFile = nativeFile;
  childProcess.spawn = nativeSpawn;
  syncBuiltinESMExports();
});

async function until<T>(read: () => T | Promise<T>, ready: (value: T) => boolean): Promise<T> {
  const deadline = Date.now() + 25_000;
  while (Date.now() < deadline) {
    const value = await read();
    if (ready(value)) return value;
    await delay(50);
  }
  throw new Error('The acceptance fixture did not reach the expected state');
}

async function fixture(t: TestContext, {legacy = false, failPolicy = false, secondTask = false} = {}) {
  const area = fs.realpathSync(tempOutsideGit('kdd-board-finish-'));
  const probe = path.join(area, 'probe');
  fs.mkdirSync(probe);
  const release = () => fs.writeFileSync(path.join(probe, 'release'), '');
  const toggleFailure = (failing: boolean) => {
    const file = path.join(probe, 'fail-policy');
    if (failing) fs.writeFileSync(file, '');
    else fs.rmSync(file, {force: true});
  };
  toggleFailure(failPolicy);
  const environment = {
    KDD_PROJECT_DIR: path.join(area, 'project'), KDD_PYTHON: python,
    KDD_BOARD_FINISH_PROBES: probe, GIT_CONFIG_GLOBAL: process.platform === 'win32' ? 'NUL' : '/dev/null',
    GIT_CONFIG_NOSYSTEM: '1', GIT_NO_REPLACE_OBJECTS: '1', PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
  };
  const keys = new Set([...Object.keys(environment), ...Object.keys(process.env).filter(key => key.startsWith('GIT_'))]);
  const before = new Map([...keys].map(key => [key, process.env[key]]));
  const restore = () => {
    for (const [key, value] of before) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  let finish: (() => Promise<void>) | undefined;
  t.after(async () => {
    try {
      await finish?.();
      const resolved = fs.realpathSync(area);
      assert.equal(resolved, area);
      assert.ok(path.basename(area).startsWith('kdd-board-finish-'));
      fs.rmSync(area, {recursive: true, force: true, maxRetries: 3});
    } finally {
      restore();
    }
  });
  for (const key of keys) delete process.env[key];
  Object.assign(process.env, environment);
  const project = JSON.parse(execFileSync(python, ['-B', prepare, environment.KDD_PROJECT_DIR,
    legacy ? 'legacy' : 'acceptance', secondTask ? 'two' : 'one'],
  {encoding: 'utf8', timeout: 45_000})) as {root: string; approved_ref: string; tested_commit: string};
  const invocations: Launch[] = [];
  const key = fs.realpathSync(project.root);
  launches.set(key, invocations);
  const git = (...args: string[]) => execFileSync('git', ['--no-replace-objects', ...args],
    {cwd: project.root, encoding: 'utf8', timeout: 10_000});
  const head = () => git('rev-parse', 'main').trim();
  const runs = () => {
    const log = path.join(probe, 'runs.jsonl');
    return fs.existsSync(log) ? fs.readFileSync(log, 'utf8').trim().split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line)) : [];
  };
  // The production server mounts git-api.ts with its authentication and GitTaskStore.
  const source = new URL('../src/server.ts', import.meta.url);
  source.searchParams.set('board-finish', String(++instance));
  const {createServer} = await import(source.href);
  const token = randomBytes(24).toString('hex');
  const server = createServer(token);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const origin = 'http://127.0.0.1:' + (server.address() as AddressInfo).port;
  async function request(url: string, method = 'GET', body?: object, authenticated = true) {
    const headers = new Headers({'Content-Type': 'application/json', Connection: 'close'});
    if (authenticated) headers.set('Authorization', 'Bearer ' + token);
    const response = await fetch(origin + url, {method, headers, body: body && JSON.stringify(body),
      signal: AbortSignal.timeout(15_000)});
    return {status: response.status, data: await response.json()};
  }
  const state = () => request(acceptance);
  const start = (tested_commit = project.tested_commit, retry?: boolean) =>
    request(acceptance, 'POST', {tested_commit, ...(retry ? {retry} : {})});
  finish = async () => {
    release();
    try {
      await until(state, value => value.data.state !== 'running');
    } finally {
      launches.delete(key);
      server.closeAllConnections();
      await new Promise<void>(resolve => server.close(() => resolve()));
    }
  };
  return {project, git, head, runs, release, toggleFailure, request, state, start, invocations};
}

async function checkReceipt(f: Awaited<ReturnType<typeof fixture>>, result: any) {
  assert.equal(result.state, 'done');
  assert.equal(result.tested_commit, f.project.tested_commit);
  assert.equal(result.approved_ref, f.project.approved_ref);
  assert.equal(result.closed_commit, f.head());
  assert.equal(f.git('rev-parse', 'main^1').trim(), f.project.tested_commit);
  const {status, data} = await f.request(task + '/evidence');
  assert.equal(status, 200);
  assert.equal(data.status, 'available');
  assert.equal(data.acceptance.passes, 2);
  assert.equal(data.acceptance.checks, 6);
  assert.equal(data.tested_commit, f.project.tested_commit);
  const raw = f.git('show', result.closed_commit + ':' + data.artifact.path);
  const digest = createHash('sha256').update(raw).digest('hex');
  assert.equal(data.artifact.sha256, digest);
  assert.equal(result.receipt_sha256, digest);
  for (const row of JSON.parse(raw).acceptance.checks) {
    assert.deepEqual(row.passes.map((entry: any) => entry.iteration), [1, 2]);
    assert.equal(row.passes[0].case_ids_sha256, row.passes[1].case_ids_sha256);
    assert.equal(row.passes[0].executed, 1);
    assert.equal(row.passes[1].executed, 1);
  }
}

test('Board returns control while the real oracle waits and closes once after two passes per obligation', async t => {
  const f = await fixture(t, {secondTask: true});
  const idle = await f.state();
  assert.equal(idle.status, 200);
  assert.equal(idle.data.state, 'idle');
  assert.equal(idle.data.task_id, 'TASK-001');
  assert.equal(f.invocations.length, 0);
  assert.equal(idle.data.tested_commit, f.project.tested_commit);
  assert.equal(idle.data.approved_ref, f.project.approved_ref);
  const [started, duplicate] = await Promise.all([f.start(), f.start()]);
  assert.equal(started.status, 202);
  assert.equal(duplicate.status, 202);
  assert.equal(started.data.state, 'running');
  assert.equal(started.data.tested_commit, f.project.tested_commit);
  assert.equal(started.data.task_id, 'TASK-001');
  assert.ok(started.data.run_id);
  assert.equal(duplicate.data.run_id, started.data.run_id);
  await until(f.runs, value => value.length > 0);
  assert.deepEqual(f.runs(), [{kind: 'primary', head: f.project.tested_commit}]);
  assert.equal(f.invocations.length, 1);
  const launch = f.invocations[0];
  assert.equal(launch.timeout, 0, 'the closure worker must outlive the HTTP command timeout');
  assert.ok(launch.args.includes('--verify-acceptance'));
  const expected = launch.args.indexOf('--expected-head');
  assert.ok((expected !== -1 && launch.args[expected + 1] === f.project.tested_commit)
    || launch.args.includes('--expected-head=' + f.project.tested_commit), 'delegate the requested SHA to the real CLI');
  const blocked = await f.request('/api/tasks/TASK-002/acceptance', 'POST', {tested_commit: f.project.tested_commit});
  assert.equal(blocked.status, 409);
  assert.equal(blocked.data.code, 'TASK_LOCK');
  const stale = await f.start(f.project.approved_ref);
  assert.equal(stale.status, 409);
  assert.equal(stale.data.code, 'TASK_RACE');
  const locked = spawnSync(python, ['-B', cli, '--repo-root', f.project.root, 'finish', 'TASK-001',
    '--verify-acceptance', '--expected-head', f.project.approved_ref, '--json'],
  {encoding: 'utf8', cwd: f.project.root, timeout: 10_000});
  assert.equal(locked.error, undefined);
  assert.notEqual(locked.status, 0);
  assert.match(locked.stderr, /\bTASK_LOCK:/, 'the private SHA comparison belongs inside the task lock');
  assert.equal(f.invocations.length, 1);
  const refreshed = await f.state();
  assert.equal(refreshed.status, 200);
  assert.equal(refreshed.data.task_id, 'TASK-001');
  assert.equal(refreshed.data.state, 'running');
  assert.equal(refreshed.data.run_id, started.data.run_id);
  assert.equal((await f.request(task + '/evidence')).data.status, 'pending');
  assert.equal(f.head(), f.project.tested_commit);
  f.release();
  const result = await until(f.state, value => value.data.state !== 'running');
  assert.equal(result.status, 200);
  await checkReceipt(f, result.data);
  assert.equal(result.data.task_id, 'TASK-001');
  assert.equal(result.data.run_id, started.data.run_id);
  const runs = f.runs();
  assert.equal(runs.length, 12);
  assert.ok(runs.every(row => row.head === f.project.tested_commit));
  const repeated = await f.start();
  assert.equal(repeated.status, 200);
  assert.equal(repeated.data.state, 'done');
  assert.equal(repeated.data.run_id, started.data.run_id);
  assert.deepEqual(f.runs(), runs);
  const receiptPath = (await f.request(task + '/evidence')).data.artifact.path;
  f.git('commit', '-q', '--allow-empty', '-m', 'Advance main after an already verified closure');
  const historical = await f.state();
  assert.equal(historical.status, 200);
  assert.equal(historical.data.state, 'done');
  assert.equal(historical.data.closed_commit, result.data.closed_commit);
  assert.equal(historical.data.receipt_sha256, result.data.receipt_sha256);
  const receiptFile = path.join(f.project.root, receiptPath);
  const receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf8'));
  receipt.acceptance.tested_commit = f.project.approved_ref;
  const bad = JSON.stringify(receipt, null, 2) + '\n';
  fs.writeFileSync(receiptFile, bad, 'utf8');
  const badHash = createHash('sha256').update(bad).digest('hex');
  const nodePath = 'knowledge/tasks/TASK-001.md';
  const node = path.join(f.project.root, nodePath);
  const original = fs.readFileSync(node, 'utf8');
  assert.ok(original.includes(result.data.receipt_sha256));
  fs.writeFileSync(node, original.replace(result.data.receipt_sha256, badHash), 'utf8');
  f.git('add', '--', nodePath, receiptPath);
  f.git('commit', '-qm', 'Controlled inconsistent receipt with the matching digest');
  assert.equal((await f.request(task + '/evidence')).data.code, 'TASK_EVIDENCE_INVALID');
  const invalid = await f.state();
  assert.equal(invalid.status, 409);
  assert.equal(invalid.data.code, 'TASK_EVIDENCE_INVALID');
  assert.notEqual(invalid.data.state, 'done');
  assert.deepEqual(f.runs(), runs);
});

test('failure in a policy check keeps the task open and allows an explicit retry of the same commit', async t => {
  const f = await fixture(t, {failPolicy: true});
  f.release();
  const first = await f.start();
  assert.equal(first.status, 202);
  const rejection = await until(f.state, value => value.data.state !== 'running');
  assert.equal(rejection.status, 200);
  const failed = rejection.data;
  assert.equal(failed.state, 'failed');
  assert.equal(failed.task_id, 'TASK-001');
  assert.equal(failed.error_code, 'TASK_ACCEPTANCE');
  assert.doesNotMatch(JSON.stringify(failed), /the dependent policy check was rejected/);
  assert.equal(failed.run_id, first.data.run_id);
  assert.deepEqual(f.runs().map(row => row.kind), ['primary', 'primary', 'policy']);
  assert.equal(f.head(), f.project.tested_commit);
  assert.equal((await f.request(task)).data.status, 'in_progress');
  assert.equal((await f.request(task + '/evidence')).data.status, 'pending');
  const repeated = await f.start();
  assert.equal(repeated.data.run_id, failed.run_id);
  assert.equal(repeated.data.state, 'failed');
  f.toggleFailure(false);
  const retry = await f.start(f.project.tested_commit, true);
  assert.equal(retry.status, 202);
  assert.notEqual(retry.data.run_id, first.data.run_id);
  const result = await until(f.state, value => value.data.state !== 'running');
  assert.equal(result.status, 200);
  await checkReceipt(f, result.data);
  assert.equal(result.data.run_id, retry.data.run_id);
  assert.equal(f.invocations.length, 2);
  assert.equal(f.runs().length, 15);
});

test('Board rejects an obsolete tested SHA before launching the oracle', async t => {
  const f = await fixture(t);
  f.git('commit', '-q', '--allow-empty', '-m', 'Move main before accepting');
  const advanced = f.head();
  assert.notEqual(advanced, f.project.tested_commit);
  const stale = await f.start();
  assert.equal(stale.status, 409);
  assert.equal(stale.data.code, 'TASK_RACE');
  assert.equal(f.head(), advanced);
  assert.deepEqual(f.runs(), []);
  assert.equal((await f.request(task + '/evidence')).data.status, 'pending');
});

test('the same request cannot publish if main advances during a real oracle', async t => {
  const f = await fixture(t);
  const started = await f.start();
  assert.equal(started.status, 202);
  await until(f.runs, value => value.length > 0);
  f.git('commit', '-q', '--allow-empty', '-m', 'Move main during acceptance');
  const advanced = f.head();
  f.release();
  const failed = (await until(f.state, value => value.data.state !== 'running')).data;
  assert.equal(failed.state, 'failed');
  assert.equal(failed.error_code, 'TASK_RACE');
  assert.equal(f.head(), advanced);
  assert.equal((await f.request(task)).data.status, 'in_progress');
  assert.equal((await f.request(task + '/evidence')).data.status, 'pending');
  assert.equal(f.git('status', '--porcelain'), '');
});

test('the delegated CLI also rejects a stale expected head before starting the matrix', async t => {
  const f = await fixture(t);
  f.release();
  const result = spawnSync(python, ['-B', cli, '--repo-root', f.project.root, 'finish', 'TASK-001',
    '--verify-acceptance', '--expected-head', f.project.approved_ref, '--json'],
  {encoding: 'utf8', cwd: f.project.root, timeout: 25_000});
  assert.equal(result.error, undefined);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /\bTASK_RACE:/);
  assert.equal(f.head(), f.project.tested_commit);
  assert.deepEqual(f.runs(), []);
  assert.equal((await f.request(task + '/evidence')).data.status, 'pending');
});

test('acceptance routes require authentication and reject a supplied approval or command', async t => {
  const f = await fixture(t);
  assert.equal((await f.request(acceptance, 'GET', undefined, false)).status, 401);
  assert.equal((await f.request(acceptance, 'POST', {tested_commit: f.project.tested_commit}, false)).status, 401);
  for (const extra of [{approved_ref: f.project.approved_ref}, {command: ['unused']}, {tested_commit: 'main'}]) {
    const answer = await f.request(acceptance, 'POST', {tested_commit: f.project.tested_commit, ...extra});
    assert.equal(answer.status, 400);
    assert.equal(answer.data.code, 'TASK_INPUT');
  }
  assert.equal(f.head(), f.project.tested_commit);
  assert.deepEqual(f.runs(), []);
  assert.equal(f.invocations.length, 0);
});

test('the ordinary Board finish still closes a historical task with its original receipt', async t => {
  const f = await fixture(t, {legacy: true});
  f.release();
  const reply = await f.request(task + '/status', 'PATCH', {status: 'done'});
  assert.equal(reply.status, 200);
  assert.equal(reply.data.task.status, 'done');
  assert.equal(reply.data.task.verified_ref, f.project.tested_commit);
  const evidence = await f.request(task + '/evidence');
  assert.equal(evidence.status, 200);
  assert.equal(evidence.data.receipt.total, 1);
  assert.equal(evidence.data.acceptance, undefined);
  assert.equal(f.invocations.length, 1);
  assert.equal(f.invocations[0].timeout, 180_000);
  assert.ok(!f.invocations[0].args.includes('--verify-acceptance'));
  assert.deepEqual(f.runs(), [{kind: 'primary', head: f.project.tested_commit}]);
});

test('the existing CLI accepts the real fixture and Board reads its two-pass receipt', async t => {
  const f = await fixture(t);
  const ordinary = await f.request(task + '/status', 'PATCH', {status: 'done'});
  assert.equal(ordinary.status, 503);
  assert.equal(ordinary.data.code, 'TASK_UNAVAILABLE');
  assert.deepEqual(f.runs(), []);
  assert.equal(f.head(), f.project.tested_commit);
  f.release();
  const result = spawnSync(python, ['-B', cli, '--repo-root', f.project.root, 'finish', 'TASK-001',
    '--verify-acceptance', '--json'], {encoding: 'utf8', cwd: f.project.root, timeout: 45_000});
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  const closed = JSON.parse(result.stdout);
  assert.equal(closed.task.status, 'done');
  await checkReceipt(f, {state: 'done', tested_commit: closed.task.verified_ref,
    approved_ref: closed.task.approved_ref, closed_commit: closed.commit, receipt_sha256: closed.task.evidence_sha256});
  assert.equal(f.runs().length, 12);
});
