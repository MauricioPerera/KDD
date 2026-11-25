import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

const runner = fileURLToPath(new URL('../browser-pilot/run.mjs', import.meta.url));
const fixture = new URL('../browser-pilot/tests/report-v1-pilot.json', import.meta.url);
const known = () => JSON.parse(fs.readFileSync(fixture, 'utf8'));

function verify(t, report, exitCode = 0, previous) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-e2e-receipt-'));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const file = path.join(directory, 'report.json');
  if (report !== undefined) fs.writeFileSync(file, JSON.stringify(report));
  const args = ['--verify-report', '--report', file, '--exit-code', String(exitCode)];
  if (previous !== undefined) args.push('--previous-run-id', previous);
  const result = spawnSync(process.execPath, [runner, ...args], {encoding: 'utf8', timeout: 10000});
  assert.ifError(result.error);
  return result;
}

function rejected(t, report, exitCode = 0, previous) {
  const done = verify(t, report, exitCode, previous);
  assert.equal(done.status, 1, done.stdout + done.stderr);
  const body = JSON.parse(done.stdout);
  assert.equal(body.ok, false);
}

test('same two executed browser cases in a new passing report', t => {
  const report = known();
  const done = verify(t, report);
  assert.equal(done.status, 0, done.stdout + done.stderr);
  const verdict = JSON.parse(done.stdout);
  assert.equal(verdict.ok, true);
  assert.deepEqual(verdict.ids, report.run.results.map(row => row.testId).sort());
});

test('nonzero process rejects an otherwise green old report', t => rejected(t, known(), 2));
test('successful command still rejects the previous run identifier', t => {
  const report = known();
  rejected(t, report, 0, report.run.id);
});
test('a missing report is a failure', t => rejected(t));
test('an unsupported schema is a failure', t => {
  const report = known();
  report.schemaVersion = 'report-2';
  rejected(t, report);
});
test('an empty selection is a failure', t => {
  const report = known();
  Object.assign(report.run.summary, {selected: 0, executed: 0, passed: 0});
  report.run.results = [];
  rejected(t, report);
});
test('the runner rejects different IDs even with matching counters', t => {
  const report = known();
  report.run.results[0].testId = 'tests/other.e2e.ts::different';
  rejected(t, report);
});
test('the runner rejects duplicate IDs', t => {
  const report = known();
  report.run.results[1].testId = report.run.results[0].testId;
  rejected(t, report);
});
test('a case marked unselected cannot appear in a passing receipt', t => {
  const report = known();
  report.run.results[0].selected = false;
  rejected(t, report);
});
test('an old retry success cannot hide a previous failed attempt', t => {
  const report = known();
  const attempt = structuredClone(report.run.results[0].attempts[0]);
  attempt.status = 'failed';
  report.run.results[0].attempts.unshift(attempt);
  rejected(t, report);
});
test('a nonpassing attempt fails independently of the final counter', t => {
  const report = known();
  report.run.results[0].attempts[0].status = 'timed-out';
  rejected(t, report);
});
test('run-level errors are not counted as successes', t => {
  const report = known();
  report.run.errors.push({code: 'APP_UNREACHABLE'});
  rejected(t, report);
});
test('model usage is outside the reviewed deterministic runner', t => {
  const report = known();
  report.run.usage.maxModelCallsInStep = 1;
  rejected(t, report);
});
test('run identity and version of the pinned e2e runner are required', t => {
  const invalid = known();
  invalid.run.id = 'not-a-run-id';
  rejected(t, invalid);
  const version = known();
  version.run.runner.version = '0.25.0';
  rejected(t, version);
});

for (const [label, mutate] of [
  ['a nonpassing run status', run => { run.status = 'failed'; }],
  ['a contradictory report exit code', run => { run.exitCode = 1; }],
  ['a nonpassing result status', run => { run.results[0].status = 'failed'; }],
  ['a nonzero token count', run => { run.usage.modelTokens = 1; }],
  ['a different Node used to produce the report', run => { run.environment.runtime = 'node v24.0.0'; }],
  ['a different web engine version', run => { run.targets[0].engine.version = '0.0.0'; }],
  ['a different Chromium version in an attempt', run => {
    run.results[0].attempts[0].environment.browser = 'chromium 158.0.0.0';
  }],
  ...['failed', 'interrupted', 'flaky', 'skipped'].map(field => [
    `a nonzero ${field} count`, run => { run.summary[field] = 1; },
  ]),
]) {
  test(`the receipt rejects ${label}`, t => {
    const report = known();
    mutate(report.run);
    rejected(t, report);
  });
}
