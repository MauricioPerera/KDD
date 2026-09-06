import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { projectFixture } from './project-fixture.ts';

test('HTTP rejects anonymous and cross-origin access; runs linked project evidence', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-http-'));
  projectFixture(root);
  process.env.KDD_PROJECT_DIR = root;
  const {createServer} = await import('../src/server.ts');
  const server = createServer('test-only-access-token');
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address() as {port: number};
  const base = `http://127.0.0.1:${address.port}`;
  const request = (url: string, method = 'GET', body?: unknown) => fetch(base + url, {
    method, headers: {Authorization: 'Bearer test-only-access-token', 'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  try {
    assert.equal((await fetch(base + '/api/tasks')).status, 401);
    const foreign = await fetch(base + '/api/tasks', {headers: {Origin: 'https://example.com', Authorization: 'Bearer test-only-access-token'}});
    assert.equal(foreign.status, 403);
    assert.equal(foreign.headers.get('Access-Control-Allow-Origin'), null);
    const created = await request('/api/tasks', 'POST', {title: 'verified task', contractId: 'app-sample_task.md', testCommand: 'echo should-not-run'});
    assert.equal(created.status, 201);
    const task = await created.json() as any;
    assert.notEqual((await request(`/api/tasks/${task.id}/status`, 'PATCH', {status:'done'})).status, 200);
    await request('/api/vault', 'POST', {key:'AUDIT_CANARY', value:'canary-private-value-123456'});
    const run = await request(`/api/tasks/${task.id}/run-tests`, 'POST');
    const result = await run.json() as any;
    assert.equal(run.status, 200, JSON.stringify(result));
    assert.equal(result.report.success, true, result.report.output);
    assert.equal(result.report.cwd, fs.realpathSync(root));
    assert.equal(result.report.passedTests, 1);
    assert.ok(result.report.output.includes('[REDACTED]'));
    assert.ok(!result.report.output.includes('canary-private-value-123456'));
    assert.equal((await request(`/api/tasks/${task.id}/status`, 'PATCH', {status:'done'})).status, 200);
    const generated = await request(`/api/tasks/${task.id}/report`, 'POST');
    const report = await generated.json() as any;
    assert.equal(generated.status, 200);
    assert.ok(report.filePath.startsWith(root));
    fs.appendFileSync(path.join(root, 'src/hello.py'), '# changed after verification');
    assert.notEqual((await request(`/api/tasks/${task.id}/status`, 'PATCH', {status:'done'})).status, 200);
    assert.notEqual((await request(`/api/tasks/${task.id}/report`, 'POST')).status, 200);
  } finally {
    await new Promise<void>((resolve, reject) => server.close(err => err ? reject(err) : resolve()));
    fs.rmSync(root, {recursive:true, force:true});
    delete process.env.KDD_PROJECT_DIR;
  }
});
