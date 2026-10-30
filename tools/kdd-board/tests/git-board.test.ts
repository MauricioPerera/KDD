import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createWebMcpMock} from 'fastwebmcp';
import {projectFixture} from './project-fixture.ts';
import {GitTaskStore} from '../src/git-task-store.ts';
import {createGitBridge} from '../src/git-bridge.ts';

const cli = fileURLToPath(new URL('../../../scripts/tasks.py', import.meta.url));
const validator = fileURLToPath(new URL('../../../scripts/validate_tasks.py', import.meta.url));
function fixture(t: any) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-board-git-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  projectFixture(root);
  fs.writeFileSync(path.join(root, 'knowledge/index.md'), '[Contracts](contracts/)\n');
  fs.writeFileSync(path.join(root, '.gitignore'), '__pycache__/\n*.pyc\n.env.local\n.kdd-board/\n');
  const git = (...args: string[]) => execFileSync('git', ['-C', root, ...args], {encoding:'utf8', stdio:['ignore','pipe','pipe']}).trim();
  git('init', '-q', '-b', 'main');
  git('config', 'user.name', 'Board integration test');
  git('config', 'user.email', 'board@example.test');
  git('config', 'core.autocrlf', 'false');
  const commit = (message: string) => {git('add', '-A'); git('commit', '-qm', message); return git('rev-parse', 'HEAD');};
  const approved = commit('approved contract and oracle');
  const act = (...args: string[]) => JSON.parse(execFileSync(process.env.KDD_PYTHON || 'python', [cli, '--repo-root', root, ...args, '--json'], {encoding:'utf8'}));
  const input = {task_id:'TASK-001', title:'Board integration', description:'Verify canonical commits', contract:'knowledge/contracts/sample_task.md', depends_on:[]};
  const store = new GitTaskStore(root);
  return {root, git, commit, approved, act, input, store};
}

test('Git projection is live from main and ignores legacy JSON and branch edits', async t => {
  const f = fixture(t);
  fs.mkdirSync(path.join(f.root, '.kdd-board'));
  fs.writeFileSync(path.join(f.root, '.kdd-board/tasks.json'), '{broken legacy data');
  assert.deepEqual(await f.store.list(), []);
  f.act('create', 'TASK-001', '--title', 'Canonical', '--description', 'Main source', '--contract', f.input.contract);
  f.git('switch', '-qc', 'task/local-edit');
  const node = path.join(f.root, 'knowledge/tasks/TASK-001.md');
  fs.writeFileSync(node, fs.readFileSync(node, 'utf8').replace('Canonical', 'Uncommitted branch title'));
  const tasks = await f.store.list();
  assert.equal(tasks.length, 1);
  assert.equal(tasks[0].id, 'TASK-001');
  assert.equal(tasks[0].title, 'Canonical');
  assert.equal(tasks[0].sourceRef, 'main');
  assert.equal(tasks[0].contractId, f.input.contract);
  assert.equal(fs.readFileSync(path.join(f.root, '.kdd-board/tasks.json'), 'utf8'), '{broken legacy data');
  assert.ok((await f.store.contracts()).some(c => c.id === f.input.contract));
});

test('create and every permitted edge publish commits, branch and durable finish evidence', async t => {
  const f = fixture(t);
  const created = await f.store.create(f.input);
  assert.equal(created.commit, f.git('rev-parse', 'HEAD'));
  assert.equal(created.task.status, 'backlog');
  await f.store.transition('TASK-001', {status:'ready', approved_ref:f.approved});
  await f.store.transition('TASK-001', {status:'in_progress', assignee:'maria'});
  assert.ok(f.git('rev-parse', 'task/TASK-001'));
  await f.store.transition('TASK-001', {status:'needs_human_input', reason:'Review input'});
  await f.store.transition('TASK-001', {status:'ready', reason:'Input reviewed'});
  await f.store.transition('TASK-001', {status:'in_progress', assignee:'maria'});
  f.git('switch', '-q', 'task/TASK-001');
  fs.appendFileSync(path.join(f.root, 'src/hello.py'), '# actual implementation\n');
  f.commit('implementation');
  f.git('switch', '-q', 'main');
  f.git('merge', '--no-ff', 'task/TASK-001', '-m', 'integrate implementation');
  const tested = f.git('rev-parse', 'HEAD');
  const done = await f.store.transition('TASK-001', {status:'done'});
  assert.equal(done.task.verified_ref, tested);
  assert.equal(done.commit, f.git('rev-parse', 'main'));
  const evidence = JSON.parse(f.git('show', 'main:' + done.task.evidence));
  assert.equal(evidence.passed_tests, 1);
  const history = await f.store.history('TASK-001');
  assert.deepEqual(history.map(h => h.status), ['backlog','ready','in_progress','needs_human_input','ready','in_progress','done']);
  assert.equal((await f.store.get('TASK-001')).journal.at(-1)?.commit, done.commit);
  execFileSync(process.env.KDD_PYTHON || 'python', [validator, '--repo-root', f.root, '--base-ref', f.approved, '--head-ref', 'main'], {encoding:'utf8'});
  const count = f.git('rev-list', '--count', 'main');
  await assert.rejects(f.store.transition('TASK-001', {status:'done'}));
  assert.equal(f.git('rev-list', '--count', 'main'), count);
});

test('invalid edges, approval, dirty tree, task branch and absent integration never commit', async t => {
  const f = fixture(t);
  await f.store.create(f.input);
  const before = f.git('rev-parse', 'main');
  await assert.rejects(f.store.transition('TASK-001', {status:'done'}));
  await assert.rejects(f.store.transition('TASK-001', {status:'ready'}));
  await assert.rejects(f.store.transition('TASK-001', {status:'ready', approved_ref:'HEAD'}));
  await assert.rejects(f.store.create({...f.input, task_id:'TASK-002', contract:'../escape.md'}));
  assert.equal(f.git('rev-parse', 'main'), before);
  fs.writeFileSync(path.join(f.root, 'dirty.txt'), 'preserve');
  await assert.rejects(f.store.transition('TASK-001', {status:'ready', approved_ref:f.approved}), /TASK_DIRTY/);
  assert.equal(fs.readFileSync(path.join(f.root, 'dirty.txt'), 'utf8'), 'preserve');
  fs.unlinkSync(path.join(f.root, 'dirty.txt'));
  await f.store.transition('TASK-001', {status:'ready', approved_ref:f.approved});
  await f.store.transition('TASK-001', {status:'in_progress', assignee:'agent'});
  const started = f.git('rev-parse', 'main');
  await assert.rejects(f.store.transition('TASK-001', {status:'done'}));
  f.git('switch', '-q', 'task/TASK-001');
  await assert.rejects(f.store.transition('TASK-001', {status:'needs_human_input', reason:'blocked'}), /TASK_MAIN/);
  assert.equal(f.git('rev-parse', 'main'), started);
});

test('failed sealed tests and coordinator lock preserve in_progress', async t => {
  const f = fixture(t);
  await f.store.create(f.input);
  await f.store.transition('TASK-001', {status:'ready', approved_ref:f.approved});
  await f.store.transition('TASK-001', {status:'in_progress', assignee:'agent'});
  const lock = path.join(f.root, '.git/kdd-tasks.lock');
  fs.writeFileSync(lock, 'other coordinator');
  await assert.rejects(f.store.transition('TASK-001', {status:'needs_human_input', reason:'wait'}), /TASK_LOCK/);
  fs.unlinkSync(lock);
  f.git('switch', '-q', 'task/TASK-001');
  fs.writeFileSync(path.join(f.root, 'src/hello.py'), '# removed function\n');
  f.commit('broken implementation');
  f.git('switch', '-q', 'main');
  f.git('merge', '--no-ff', 'task/TASK-001', '-m', 'integrate broken implementation');
  const before = f.git('rev-parse', 'main');
  await assert.rejects(f.store.transition('TASK-001', {status:'done'}));
  assert.equal(f.git('rev-parse', 'main'), before);
  assert.equal((await f.store.get('TASK-001')).status, 'in_progress');
});

test('missing main and malformed nodes fail closed without JSON fallback', async t => {
  const f = fixture(t);
  f.git('branch', '-m', 'other');
  await assert.rejects(f.store.list());
  f.git('branch', '-m', 'main');
  fs.mkdirSync(path.join(f.root, 'knowledge/tasks'), {recursive:true});
  fs.writeFileSync(path.join(f.root, 'knowledge/tasks/TASK-001.md'), 'not an OKF task');
  f.commit('invalid task');
  await assert.rejects(f.store.list());
  assert.equal(fs.existsSync(path.join(f.root, '.kdd-board/tasks.json')), false);
});

test('WebMCP uses the canonical journal and explicit transition fields', async t => {
  const f = fixture(t);
  const bridge = createGitBridge(f.store);
  const mock = createWebMcpMock();
  const previous = globalThis.document;
  globalThis.document = mock.document as any;
  try {
    assert.ok(bridge.registerAll().every(Boolean));
    assert.deepEqual([...mock.registeredTools.keys()].sort(), ['create_task','get_task','list_tasks','task_history','update_task_status']);
    const created: any = await mock.invokeTool('create_task', f.input);
    assert.equal(created.commit, f.git('rev-parse', 'main'));
    await mock.invokeTool('update_task_status', {task_id:'TASK-001', status:'ready', approved_ref:f.approved});
    const ready: any = await mock.invokeTool('get_task', {task_id:'TASK-001'});
    assert.equal(ready.approved_ref, f.approved);
    const history: any = await mock.invokeTool('task_history', {task_id:'TASK-001'});
    assert.equal(history.length, 2);
    assert.equal((await mock.invokeTool('list_tasks', {status:'ready'}) as any[]).length, 1);
  } finally {globalThis.document = previous;}
});

test('authenticated HTTP and WebMCP schemas expose Git tasks with no seeded JSON store', async t => {
  const f = fixture(t);
  process.env.KDD_PROJECT_DIR = f.root;
  const {createServer} = await import('../src/server.ts');
  const server = createServer('git-test-token');
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const request = (url: string, method='GET', body?: unknown, extra={}) => fetch(base + url, {
    method, headers:{Authorization:'Bearer git-test-token','Content-Type':'application/json', ...extra},
    body:body === undefined ? undefined : JSON.stringify(body),
  });
  try {
    assert.equal((await fetch(base + '/api/tasks')).status, 401);
    assert.equal((await request('/api/tasks','GET',undefined,{Origin:'https://foreign.test'})).status,403);
    assert.equal((await (await request('/api/board')).json() as any).mode, 'git');
    assert.deepEqual(await (await request('/api/tasks')).json(), []);
    assert.equal(fs.existsSync(path.join(f.root, '.kdd-board/tasks.json')), false);
    const created = await request('/api/tasks','POST',f.input);
    assert.equal(created.status,201, await created.clone().text());
    assert.equal((await created.json() as any).commit,f.git('rev-parse','main'));
    assert.equal((await request('/api/tasks/TASK-001/status','PATCH',{status:'done'})).status,400);
    assert.equal((await request('/api/tasks/TASK-001/status','PATCH',{status:'ready'})).status,400);
    assert.equal((await request('/api/tasks/TASK-001/status','PATCH',{status:'ready',approved_ref:f.approved})).status,200);
    assert.equal((await (await request('/api/tasks/TASK-001/history')).json() as any[]).length,2);
    assert.equal((await request('/api/tasks/TASK-999')).status,404);
    assert.equal((await request('/api/tasks?status=unknown')).status,400);
    assert.equal((await request('/api/tasks/TASK-001/assign','PATCH',{assignee:'human'})).status,409);
    assert.equal((await request('/api/tasks/TASK-001/run-tests','POST')).status,409);
    fs.writeFileSync(path.join(f.root, 'dirty.txt'),'keep');
    assert.equal((await request('/api/tasks/TASK-001/status','PATCH',{status:'in_progress',assignee:'maria'})).status,409);
    fs.unlinkSync(path.join(f.root, 'dirty.txt'));
    const tools = await (await request('/api/tools')).json() as any[];
    assert.equal(tools.length,5);
    assert.ok(tools.find(x => x.name === 'update_task_status').inputSchema.properties.approved_ref);
    assert.equal((await request('/git-board.js')).status,200);
  } finally {
    await new Promise<void>((resolve,reject) => server.close(err => err ? reject(err) : resolve()));
    delete process.env.KDD_PROJECT_DIR;
  }
});
