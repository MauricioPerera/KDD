import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';

const repo = fileURLToPath(new URL('../../..', import.meta.url));
const boardPath = 'tools/kdd-board';
const pilotPath = boardPath + '/browser-pilot';
const pilot = path.join(repo, pilotPath);
const configFile = 'e2e.config.mjs';
const caseFile = 'tests/handoff.e2e.ts';
const paths = [
  'knowledge/contracts/board-browser-pilot.md',
  boardPath + '/package-lock.json',
  boardPath + '/tests/project-fixture.ts',
  boardPath + '/tests/browser-pilot-receipt.test.mjs',
  ...['package.json', 'package-lock.json', 'pins.json', configFile, caseFile,
    'tests/fixture.mjs', 'tests/pilot-live.test.mjs', 'tests/report-v1-pilot.json']
    .map(name => pilotPath + '/' + name),
];
const ids = ['missing evidence stays pending', 'ready candidate requires human approval']
  .map(title => caseFile + '::' + encodeURIComponent(title));
const commitId = /^[0-9a-f]{40}$/;
const runId = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const totals = {discovered: 2, selected: 2, executed: 2, passed: 2,
  failed: 0, interrupted: 0, flaky: 0, skipped: 0};
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const lf = bytes => bytes.toString('utf8').replaceAll('\r\n', '\n');

function readSmall(file) {
  const stat = fs.lstatSync(file);
  assert.ok(stat.isFile() && stat.size <= 4 * 1024 * 1024, 'Expected a bounded regular file');
  return fs.readFileSync(file);
}

const json = file => JSON.parse(readSmall(file));
const empty = value => Array.isArray(value) && value.length === 0;

function verifyAttempt(attempt, pins, window) {
  assert.equal(attempt.index, 0, 'Unexpected attempt index');
  assert.equal(attempt.status, 'passed', 'Nonpassing attempt');
  assert.match(attempt.id, runId, 'Invalid attempt ID');
  assert.equal(attempt.environment.browser, 'chromium ' + pins.browser_version,
    'Unexpected Chromium version');
  assert.ok(empty(attempt.secondaryErrors) && attempt.cleanup === 'complete', 'Attempt cleanup failed');
  const start = Date.parse(attempt.startedAt);
  assert.ok(window.start <= start && start <= window.end, 'Invalid attempt date');
  assert.ok(Number.isSafeInteger(attempt.durationMs) && attempt.durationMs >= 0, 'Invalid attempt duration');
}

function verifyResult(result, pins, window) {
  assert.equal(result.kind, 'test', 'Expected a test result');
  assert.equal(result.file, caseFile, 'Unexpected test file');
  assert.equal(result.targetId, 'web', 'Unexpected test target');
  assert.equal(result.repeat, 0, 'Unexpected repetition');
  assert.ok(result.selected === true && result.status === 'passed', 'Case did not pass');
  assert.equal(result.attempts.length, 1, 'Expected one attempt');
  verifyAttempt(result.attempts[0], pins, window);
}

function verifyRun(run, pins, previous) {
  assert.match(run.id, runId, 'Invalid run ID');
  assert.notEqual(run.id, previous, 'Run ID was already seen');
  assert.equal(run.status, 'passed', 'Run did not pass');
  assert.equal(run.exitCode, 0, 'Nonzero exit in report');
  assert.equal(run.runner.name, 'e2e', 'Unexpected runner');
  assert.equal(run.runner.version, pins.e2e, 'Unexpected e2e version');
  assert.equal(run.environment.runtime, 'node v' + pins.node, 'Unexpected Node version');
  assert.equal(run.targets.length, 1, 'Expected one target');
  const target = run.targets[0];
  assert.ok(target.id === 'web' && target.platform === 'web', 'Unexpected target');
  assert.equal(target.engine.name, 'web', 'Unexpected engine');
  assert.equal(target.engine.version, pins.web, 'Unexpected web version');
  assert.ok(empty(run.errors) && empty(run.serialGroups), 'Run has errors or serial groups');
  assert.equal(run.usage.modelTokens, 0, 'Report used model tokens');
  assert.equal(run.usage.maxModelCallsInStep, 0, 'Report used model calls');
}

function verifyReport(file, exitCode, {pins, previous}) {
  assert.equal(exitCode, 0, 'Browser process exited with code ' + exitCode);
  const raw = readSmall(file);
  const report = JSON.parse(raw);
  assert.equal(report.schemaVersion, 'report-1', 'Expected report-1');
  const run = report.run;
  verifyRun(run, pins, previous);
  assert.deepEqual(run.summary, totals, 'Unexpected case counts');
  const window = {start: Date.parse(run.startedAt), end: Date.parse(run.finishedAt)};
  assert.ok(window.start <= window.end, 'Invalid run dates');
  assert.deepEqual(run.results.map(result => result.testId).sort(), ids, 'Unexpected case inventory');
  for (const result of run.results) verifyResult(result, pins, window);
  return {raw, run, window};
}

function localEnv() {
  const names = /^(PATH|PATHEXT|HOME|USERPROFILE|SYSTEMROOT|WINDIR|SYSTEMDRIVE|COMSPEC|LOCALAPPDATA|APPDATA|XDG_CACHE_HOME|PLAYWRIGHT_BROWSERS_PATH|TMP|TEMP|TMPDIR|LANG|LC_ALL)$/i;
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => names.test(key)));
  return {...env, CI: '1', GIT_OPTIONAL_LOCKS: '0', GIT_CONFIG_NOSYSTEM: '1',
    GIT_CONFIG_GLOBAL: process.platform === 'win32' ? 'NUL' : '/dev/null',
    GIT_TERMINAL_PROMPT: '0', GIT_NO_LAZY_FETCH: '1', PYTHONUTF8: '1',
    PYTHONDONTWRITEBYTECODE: '1', E2E_TELEMETRY_DISABLED: '1'};
}

function command(file, args, options) {
  const result = spawnSync(file, args, {timeout: 30000, maxBuffer: 32 * 1024 * 1024,
    windowsHide: true, ...options});
  if (result.error) throw result.error;
  return result;
}

function checked(result, label) {
  assert.equal(result.status, 0, label + ': ' + String(result.stderr).slice(-4000));
  return result.stdout;
}

function git(args, cwd, env) {
  return checked(command('git', ['--no-replace-objects', '--literal-pathspecs', ...args],
    {cwd, env}), 'Git ' + args[0]);
}

function tree(ref, env) {
  const rows = git(['ls-tree', '-rz', ref, '--', ...paths], repo, env).toString().split('\0');
  const blobs = Object.fromEntries(rows.filter(Boolean).map(row => {
    const match = /^100(?:644|755) blob ([a-f0-9]{40})\t(.+)$/.exec(row);
    assert.ok(match, 'An approved input is not a regular Git blob');
    return [match[2], match[1]];
  }));
  assert.equal(Object.keys(blobs).length, paths.length, 'Reference lacks approved browser inputs');
  return blobs;
}

function resolveRef(ref, env) {
  return git(['rev-parse', '--verify', ref + '^{commit}'], repo, env).toString().trim();
}

function checkoutFor(approved, env) {
  assert.match(approved ?? '', commitId, 'Use a full baseline commit');
  assert.equal(resolveRef(approved, env), approved, 'Invalid baseline commit');
  const head = resolveRef('HEAD', env);
  assert.match(head, commitId, 'Invalid checkout commit');
  git(['merge-base', '--is-ancestor', approved, head], repo, env);
  assert.deepEqual(tree(approved, env), tree(head, env), 'Checkout and approved input blobs differ');
  return head;
}

function outside(directory, root) {
  const rel = path.relative(root, directory);
  return path.isAbsolute(rel) || rel.split(path.sep)[0] === '..';
}

function destination(given) {
  const requested = path.resolve(given);
  const output = path.join(fs.realpathSync(path.dirname(requested)), path.basename(requested));
  assert.ok(outside(output, fs.realpathSync(repo)), 'Output must be outside KDD');
  assert.equal(fs.lstatSync(output, {throwIfNoEntry: false}), undefined, 'Output already exists');
  return output;
}

const unpack = [
  'import sys, tarfile',
  'with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as archive:',
  '    for member in archive:',
  '        if not (member.isfile() or member.isdir()):',
  '            raise ValueError("The source snapshot must contain regular files and directories")',
  '        archive.extract(member, path=sys.argv[1], filter="data")',
].join('\n');

function snapshot(head, scope) {
  const {env, source, python} = scope;
  const archive = git(['archive', '--format=tar', head, '--', 'scripts', boardPath,
    'knowledge/contracts/board-browser-pilot.md'], repo, env);
  fs.mkdirSync(source);
  checked(command(python, ['-I', '-B', '-c', unpack, source],
    {input: archive, cwd: source, env}), 'Extract source snapshot');
  return Object.fromEntries([...paths, pilotPath + '/run.mjs'].map(name => {
    const bytes = readSmall(path.join(repo, name));
    const committed = readSmall(path.join(source, name));
    assert.equal(lf(bytes), lf(committed), 'Modified input: ' + name);
    return [name, sha256(bytes)];
  }));
}

function installedPackages(pins) {
  const modules = path.join(pilot, 'node_modules');
  for (const [name, version] of Object.entries({'e2e': pins.e2e, '@e2e-dev/core': pins.core,
    '@e2e-dev/web': pins.web, 'playwright-core': pins.playwright})) {
    assert.equal(json(path.join(modules, name, 'package.json')).version, version,
      'Unexpected installed version for ' + name);
  }
  return modules;
}

const browserExecutable = [
  'const { registry: { registry } } = require(process.argv[1]);',
  'process.stdout.write(registry.findExecutable(process.argv[2]).executablePath());',
].join('\n');

async function installedBrowser(scope, pins, modules) {
  const playwright = path.join(modules, 'playwright-core');
  const declared = json(path.join(playwright, 'browsers.json')).browsers
    .find(entry => entry.name === pins.browser);
  assert.equal(declared.revision, pins.revision, 'Unexpected Chromium revision');
  assert.equal(declared.browserVersion, pins.browser_version, 'Unexpected Chromium release');
  const executable = checked(command(process.execPath, ['-e', browserExecutable,
    path.join(playwright, 'lib/coreBundle.js'), pins.browser], {cwd: scope.source, env: scope.env}),
  'Resolve pinned Playwright executable').toString();
  const installation = path.dirname(path.dirname(executable));
  const expected = pins.browser.replaceAll('-', '_') + '-' + pins.revision;
  assert.equal(path.basename(fs.realpathSync(installation)), expected, 'Wrong Chromium cache revision');
  assert.ok(fs.statSync(path.join(installation, 'INSTALLATION_COMPLETE')).isFile(),
    'Install Chromium before running the pilot');
  assert.ok(fs.lstatSync(executable).isFile(), 'Missing regular Chromium executable');
  const digest = createHash('sha256');
  for await (const bytes of fs.createReadStream(executable)) digest.update(bytes);
  return digest.digest('hex');
}

function prepareBrowser(scope, modules) {
  fs.mkdirSync(path.join(scope.browser, 'tests'), {recursive: true});
  for (const name of [configFile, caseFile]) {
    fs.copyFileSync(path.join(scope.source, pilotPath, name), path.join(scope.browser, name));
  }
  fs.symlinkSync(path.join(repo, boardPath, 'node_modules'),
    path.join(scope.source, boardPath, 'node_modules'), 'junction');
  fs.symlinkSync(modules, path.join(scope.browser, 'node_modules'), 'junction');
}

function spawnFixture(scope) {
  return spawn(process.execPath, [path.join(scope.source, pilotPath, 'tests/fixture.mjs'),
    scope.fixture, scope.descriptor, scope.python], {cwd: scope.source, env: scope.env,
    windowsHide: true, stdio: ['ignore', 'ignore', 'pipe']});
}

async function ready(server, descriptor) {
  let diagnostics = '';
  let failure;
  server.stderr.setEncoding('utf8').on('data', chunk => {
    diagnostics = (diagnostics + chunk).slice(-4000);
  });
  server.once('error', error => { failure = error; });
  for (let count = 0; count < 300; count += 1) {
    if (failure) throw failure;
    assert.equal(server.exitCode, null, 'Board stopped before readiness: ' + diagnostics);
    if (fs.existsSync(descriptor) && fs.statSync(descriptor).size > 0) {
      const state = json(descriptor);
      assert.match(state.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/, 'Expected a loopback Board');
      assert.match(state.ready, commitId, 'Missing synthetic approval candidate');
      return state;
    }
    await delay(100);
  }
  throw new Error('Board readiness timed out: ' + diagnostics);
}

async function finish(server) {
  if (!server?.pid || server.exitCode !== null || server.signalCode !== null) return;
  const ended = once(server, 'exit');
  server.kill();
  await ended;
}

function journal(scope, state) {
  const {env, fixture} = scope;
  const read = args => sha256(git(args, fixture, env));
  const evidence = path.join(fixture, '.agents/logs/board-reviews');
  const records = ['TASK-001/selection.json', 'TASK-002/selection.json',
    'TASK-001/' + state.ready + '.json'].map(file => sha256(readSmall(path.join(evidence, file))));
  return {refs: read(['show-ref']), index: read(['ls-files', '--stage']),
    worktree: read(['status', '--porcelain=v1', '-uall']), records};
}

function browserRun(scope, pins, {modules, previous}) {
  const out = path.join(scope.browser, 'run');
  const start = Date.now();
  const result = command(process.execPath, [path.join(modules, 'e2e/dist/cli/bin.js'),
    'run', caseFile, '--config', configFile, '--workers', '1', '--retries', '0', '--no-cache', '--output', 'run'],
  {cwd: scope.browser, env: {...scope.env, KDD_BOARD_BROWSER_FIXTURE: scope.descriptor}, timeout: 55000});
  const end = Date.now();
  assert.equal(result.status, 0, 'Chromium run failed: ' + String(result.stdout).slice(-4000));
  const report = verifyReport(path.join(out, 'report.json'), result.status, {pins, previous});
  assert.ok(start <= report.window.start && report.window.end <= end, 'Run was not generated during this invocation');
  return {...report, elapsed: end - start};
}

function newScope(env) {
  const parent = fs.realpathSync(os.tmpdir());
  assert.ok(outside(parent, fs.realpathSync(repo)), 'Set a temporary directory outside KDD');
  const scratch = fs.mkdtempSync(path.join(parent, 'kdd-board-browser-'));
  const python = process.env.KDD_PYTHON || 'python';
  return {scratch, python, env, source: path.join(scratch, 'source'),
    fixture: path.join(scratch, 'repository'), browser: path.join(scratch, 'browser'),
    descriptor: path.join(scratch, 'fixture.json')};
}

async function pilotRun(args, pins) {
  const output = destination(args.output);
  assert.equal(process.versions.node, pins.node, 'Use the pinned Node version for Chromium');
  const env = localEnv();
  const head = checkoutFor(args['approved-ref'], env);
  const scope = newScope(env);
  let board;
  try {
    const inputs = snapshot(head, scope);
    const modules = installedPackages(pins);
    const executable = await installedBrowser(scope, pins, modules);
    prepareBrowser(scope, modules);
    board = spawnFixture(scope);
    const state = await ready(board, scope.descriptor);
    const before = journal(scope, state);
    const previous = json(path.join(scope.source, pilotPath, 'tests/report-v1-pilot.json')).run.id;
    const result = browserRun(scope, pins, {modules, previous});
    assert.equal(result.run.targets[0].baseOrigin, state.origin, 'Report belongs to another app');
    assert.deepEqual(journal(scope, state), before, 'Board consultation changed the journal');
    return {output, result, receipt: {checkout: head, approved_ref: args['approved-ref'],
      report_sha256: sha256(result.raw), run_id: result.run.id, exit_code: 0, ids, inputs,
      runtime: pins, chromium_executable_sha256: executable, browser_ms: result.elapsed, journal: before}};
  } finally {
    await finish(board);
    fs.rmSync(scope.scratch, {recursive: true, force: true, maxRetries: 3});
  }
}

function argumentsForRun() {
  const {values, tokens} = parseArgs({tokens: true, options: {
    'approved-ref': {type: 'string'}, output: {type: 'string'},
    'verify-report': {type: 'boolean'}, report: {type: 'string'},
    'exit-code': {type: 'string'}, 'previous-run-id': {type: 'string'},
  }});
  assert.equal(tokens.length, Object.keys(values).length, 'Repeated flag');
  return values;
}

function verifyExternal(args, pins) {
  assert.ok(args.report && /^\d+$/.test(args['exit-code'] ?? ''), 'Supply a report and process exit code');
  assert.ok(!('approved-ref' in args) && !('output' in args), 'Choose one mode');
  const previous = args['previous-run-id'];
  if (previous !== undefined) assert.match(previous, runId, 'Invalid previous run ID');
  return verifyReport(args.report, Number(args['exit-code']), {pins, previous}).run.id;
}

async function main() {
  const args = argumentsForRun();
  const pins = json(path.join(pilot, 'pins.json'));
  if (args['verify-report']) return verifyExternal(args, pins);
  assert.ok(args.output && args['approved-ref'] && Object.keys(args).length === 2,
    'Supply --approved-ref SHA --output DIR for a browser run');
  const {output, result, receipt} = await pilotRun(args, pins);
  fs.mkdirSync(output);
  fs.writeFileSync(path.join(output, 'report.json'), result.raw, {flag: 'wx'});
  fs.writeFileSync(path.join(output, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n', {flag: 'wx'});
  return receipt.run_id;
}

try {
  console.log(JSON.stringify({ok: true, ids, run_id: await main()}));
} catch (error) {
  console.log(JSON.stringify({ok: false, error: error.message || String(error)}));
  process.exitCode = 1;
}
