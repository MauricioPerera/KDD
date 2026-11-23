import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {after, before, test} from 'node:test';
import {projectFixture, tempOutsideGit} from './project-fixture.ts';
import type {Server} from 'node:http';

let root: string;
let server: Server;
let base: string;
const token = 'fixture-board-oracle-inventory';
const helper = 'helper.cjs';

before(async () => {
  root = tempOutsideGit('kdd-legacy-inventory-');
  const prior = process.env.KDD_PROJECT_DIR;
  process.env.KDD_PROJECT_DIR = root;
  projectFixture(root);
  const oracle = [
    "const {test}=require('node:test');",
    "const assert=require('node:assert/strict');",
    "test('checks the fixture value',()=>assert.equal(require('./helper.cjs').value,1));",
    '',
  ].join('\n');
  const contract = path.join(root, 'knowledge/contracts/sample_task.md');
  fs.writeFileSync(path.join(root,'oracle.cjs'), oracle);
  fs.writeFileSync(path.join(root,helper), 'exports.value = 1;\n');
  const seal = createHash('sha256').update(oracle).digest('hex');
  fs.writeFileSync(contract, fs.readFileSync(contract,'utf8')
    .replace(/^test_command:.*$/m,
      "test_command: 'node --test oracle.cjs'\ntest_runner: node-test\noracle_files: ['oracle.cjs', 'helper.cjs']")
    .replace(/^tests_sha256:.*$/m, "tests_sha256: '" + seal + "'"));
  try {
    const {createServer} = await import('../src/server.ts');
    server = createServer(token);
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(0,'127.0.0.1', resolve);
    });
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    base = 'http://127.0.0.1:' + address.port + '/api';
  } finally {
    if (prior === undefined) delete process.env.KDD_PROJECT_DIR;
    else process.env.KDD_PROJECT_DIR = prior;
  }
});

after(async () => {
  if (server?.listening) await new Promise<void>(resolve => server.close(() => resolve()));
  if (root) fs.rmSync(root, {recursive:true, force:true});
});

async function call(method: string, route: string, data?: object) {
  const response = await fetch(base + route, {
    method,
    headers: {authorization:'Bearer ' + token, 'content-type':'application/json'},
    body: data && JSON.stringify(data),
    signal: AbortSignal.timeout(45000),
  });
  return {status:response.status, json:await response.json()};
}

async function runTask() {
  const task = await call('POST','/tasks',{title:'Verify helper inventory',contractId:'app-sample_task.md'});
  assert.equal(task.status, 201, JSON.stringify(task.json));
  const endpoint = '/tasks/' + task.json.id;
  const run = await call('POST',endpoint + '/run-tests');
  assert.equal(run.status, 200, JSON.stringify(run.json));
  assert.equal(run.json.report.status, 'PASS', JSON.stringify(run.json.report));
  return {endpoint, report:run.json.report, id:task.json.id};
}

test('legacy real HTTP receipt records the helper and permits a stable closing', async () => {
  const {endpoint, report} = await runTask();
  const proof = Object.entries(report.evidence).find(([file]) => path.basename(file) === helper);
  assert.ok(proof, JSON.stringify(report.evidence));
  assert.equal(proof[1], createHash('sha256').update(fs.readFileSync(path.join(root,helper))).digest('hex'));
  const result = await call('PATCH',endpoint + '/status',{status:'done'});
  assert.equal(result.status, 200, JSON.stringify(result.json));
  assert.equal(result.json.status, 'done');
});

test('legacy real HTTP rejects stale helper evidence before closing', async () => {
  const {endpoint, id} = await runTask();
  const file = path.join(root,helper);
  try {
    fs.writeFileSync(file, 'exports.value = 2;\n');
    const result = await call('PATCH',endpoint + '/status',{status:'done'});
    assert.ok(result.status >= 400 && result.status < 500, JSON.stringify(result));
    const current = await call('GET','/tasks');
    assert.equal(current.status, 200);
    assert.notEqual(current.json.find((item: {id:string}) => item.id === id)?.status, 'done');
    const retry = await call('POST',endpoint + '/run-tests');
    assert.equal(retry.json.report.status, 'FAIL', JSON.stringify(retry.json));
  } finally {
    fs.writeFileSync(file, 'exports.value = 1;\n');
  }
});
