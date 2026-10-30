import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { TaskStore } from '../src/task-store.ts';
import { executeTaskTest } from '../src/test-runner.ts';

test('HTTP validates runtime types and only fulfills real answers or saved credentials', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-input-audit-'));
  process.env.KDD_PROJECT_DIR = root;
  const {createServer} = await import('../src/server.ts');
  const server = createServer('regression-token');
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const request = async (route: string, body: unknown, method = 'POST') => {
    const response = await fetch(base + route, {method, headers: {Authorization: 'Bearer regression-token', 'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    return {status: response.status, body: await response.json() as any};
  };
  try {
    for (const body of [null, [], {title: 12}, {title: 'x', assignee: 'human"><img src=x onerror=alert(1)>'}]) {
      assert.equal((await request('/api/tasks', body)).status, 400);
    }
    const created = await request('/api/tasks', {title: 'safe'});
    assert.equal(created.status, 201);
    const route = `/api/tasks/${created.body.id}`;
    assert.equal((await request(route + '/assign', {assignee: 'other'}, 'PATCH')).status, 400);
    assert.equal((await request(route + '/requirements', {fieldKey: 'KEY', label: 'Key', description: '', isSecret: 'false);alert(1);//'})).status, 400);
    assert.equal((await request(route + '/requirements', {fieldKey: 'KEY', label: 'Key', description: '', isSecret: true})).status, 200);
    for (const body of [{fieldKey: 'KEY'}, {fieldKey: 'KEY', value: 'fake'}, {fieldKey: 'KEY', secretValue: ' '}]) {
      assert.equal((await request(route + '/fulfill', body)).status, 400);
    }
    assert.equal((await request(route + '/fulfill', {fieldKey: 'UNKNOWN', secretValue: 'canary'})).status, 400);
    assert.equal(fs.existsSync(path.join(root, '.env.local')), false);
    const fulfilled = await request(route + '/fulfill', {fieldKey: 'KEY', secretValue: 'fictional-secret'});
    assert.equal(fulfilled.status, 200);
    assert.equal(fulfilled.body.task.status, 'ready');
    assert.equal(fulfilled.body.task.requirements[0].isSatisfied, true);
    assert.ok(!JSON.stringify(fulfilled.body).includes('fictional-secret'));
    await request(route + '/requirements', {fieldKey: 'ANSWER', label: 'Answer', description: '', isSecret: false});
    assert.equal((await request(route + '/fulfill', {fieldKey: 'ANSWER', value: ' '})).status, 400);
    assert.equal((await request('/api/vault', {key: 'ANSWER', value: 'not-an-answer'})).status, 200);
    const listed = await fetch(base + '/api/tasks', {headers: {Authorization: 'Bearer regression-token'}}).then(r => r.json()) as any[];
    assert.equal(listed.find(t => t.id === created.body.id).requirements.find((r: any) => r.fieldKey === 'ANSWER').isSatisfied, false);
    assert.equal((await request(route + '/fulfill', {fieldKey: 'ANSWER', value: 'accepted'})).status, 200);
    await request('/api/vault/KEY', undefined, 'DELETE');
    const afterDelete = await fetch(base + '/api/tasks', {headers: {Authorization: 'Bearer regression-token'}}).then(r => r.json()) as any[];
    assert.equal(afterDelete.find(t => t.id === created.body.id).requirements.find((r: any) => r.fieldKey === 'KEY').isSatisfied, false);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
    delete process.env.KDD_PROJECT_DIR;
    fs.rmSync(root, {recursive: true, force: true});
  }
});

test('malformed persisted tasks fail closed without overwriting the file', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-storage-audit-'));
  try {
    const file = path.join(root, 'tasks.json');
    const store = new TaskStore(file);
    const task = store.createTask({title: 'safe', description: ''});
    const safe = JSON.stringify([task]);
    for (const tampered of [{...task, assignee: '<img src=x>'}, {...task, requirements: [{fieldKey: 'KEY', label: 'Key', description: '', isSecret: 'alert(1)', isSatisfied: false}]}]) {
      const content = JSON.stringify([tampered]);
      fs.writeFileSync(file, content);
      assert.throws(() => new TaskStore(file), /Invalid task storage/);
      assert.equal(fs.readFileSync(file, 'utf8'), content);
    }
    fs.writeFileSync(file, safe);
    assert.equal(new TaskStore(file).getTask(task.id)?.title, 'safe');
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('runner distinguishes PASS, FAIL, SKIP and TIMEOUT', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-status-audit-'));
  try {
    const oracle = path.join(root, 'oracle.cjs');
    fs.writeFileSync(oracle, "require('node:test').test('works', () => {});");
    const pass = await executeTaskTest('node --test oracle.cjs', root, {}, oracle);
    assert.equal((pass as any).status, 'PASS');
    fs.writeFileSync(oracle, "require('node:test').test('skipped', {skip:true}, () => {});");
    assert.equal((await executeTaskTest('node --test oracle.cjs', root, {}, oracle) as any).status, 'SKIP');
    fs.writeFileSync(oracle, "require('node:test').test('fails', () => {throw Error('expected')});");
    assert.equal((await executeTaskTest('node --test oracle.cjs', root, {}, oracle) as any).status, 'FAIL');
    fs.writeFileSync(oracle, "require('node:test').test('hangs', async () => {await new Promise(r=>setTimeout(r,10000))});");
    const timed = await (executeTaskTest as any)('node --test oracle.cjs', root, {}, oracle, 50);
    assert.equal(timed.status, 'TIMEOUT');
    assert.equal(timed.success, false);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

function browserFixture() {
  const nodes = new Map<string, any>();
  let renders = 0;
  const node = (id: string) => {
    if (!nodes.has(id)) {
      const element: any = {value: '', textContent: '', dataset: {}, style: {}, children: [], classList: {add(){}, remove(){}, toggle(){}}, addEventListener(){}, appendChild(child: any){this.children.push(child)}};
      element.contains = (target: any) => id === 'workspace-container' && [...nodes.entries()].some(([key, n]) => key.startsWith('workspace-') && n === target);
      element.querySelectorAll = () => id === 'workspace-container' ? [...nodes.entries()].filter(([key]) => key.startsWith('workspace-input-req-')).map(([, n]) => n) : [];
      Object.defineProperty(element, 'innerHTML', {get: () => element.html || '', set: (html) => {
        element.html = html;
        if (id === 'workspace-container') {
          renders++;
          for (const key of [...nodes.keys()].filter(k => k.startsWith('workspace-input-req-'))) nodes.delete(key);
        }
      }});
      nodes.set(id, element);
    }
    return nodes.get(id);
  };
  const context: any = vm.createContext({document: {getElementById: node, querySelectorAll: () => [], addEventListener(){}, createElement: () => ({innerHTML:'', className:''}), activeElement: null}, location: {hash:'', pathname:'/', search:''}, sessionStorage: {getItem:()=>'',setItem(){throw Error('Do not persist drafts')}}, URLSearchParams, Headers, console, setInterval:()=>0, fetch:async()=>({ok:true,json:async()=>[]})});
  context.window = context;
  vm.runInContext(fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8'), context);
  return {context, node, nodes, renders: () => renders};
}

test('polling preserves the focused draft and safely renders legacy values', async () => {
  const {context, node, nodes} = browserFixture();
  const task = {id:'task-safe', title:'Safe', description:'', assignee:'human', priority:'medium', status:'needs_human_input', updatedAt:'now', comments:[], requirements:[{fieldKey:'KEY',label:'Key',description:'',isSecret:true,isSatisfied:false}]};
  context.auditTask = task;
  await new Promise(resolve => setImmediate(resolve));
  vm.runInContext("currentTasks=[auditTask];selectedTaskId=auditTask.id;activeView='task';renderTaskWorkspace(auditTask.id)", context);
  const input = node('workspace-input-req-KEY');
  input.value = 'draft-canary';
  input.selectionStart = 3;
  context.document.activeElement = input;
  context.fetch = async (url: string) => ({ok:true,json:async()=>url==='/api/tasks'?[task]:[]});
  await vm.runInContext('loadTasks()', context);
  assert.equal(node('workspace-input-req-KEY'), input, 'focused input must survive polling');
  assert.equal(input.value, 'draft-canary');
  assert.equal(input.selectionStart, 3);
  const app = fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8');
  assert.ok(!app.includes('onclick='), 'event handlers must treat identifiers as data');
  assert.ok(![...nodes.values()].some(n => n.innerHTML.includes('draft-canary')));
  task.assignee = 'human"><img src=x onerror=alert(1)>';
  task.requirements[0].isSecret = 'false);alert(1);//' as any;
  context.document.activeElement = null;
  vm.runInContext('renderTaskWorkspace(auditTask.id)', context);
  assert.ok(![...nodes.values()].some(n => n.innerHTML.includes('<img src=x')));
  assert.ok(![...nodes.values()].some(n => /onclick=/.test(n.innerHTML)));
});

test('the task workspace explicitly displays all verification states', async () => {
  const {context, nodes} = browserFixture();
  await new Promise(resolve => setImmediate(resolve));
  for (const status of ['PASS', 'FAIL', 'SKIP', 'TIMEOUT']) {
    context.auditTask = {id:'task-safe',title:'Safe',description:'',assignee:'human',priority:'medium',status:'ready',updatedAt:'now',comments:[],requirements:[],testReport:{status,success:status==='PASS'||status==='SKIP',passedTests:status==='PASS'?1:0,failedTests:0,durationMs:1,lastRun:'2026-09-29',output:''}};
    vm.runInContext('currentTasks=[auditTask];renderTaskWorkspace(auditTask.id)', context);
    assert.ok([...nodes.values()].some(n => n.innerHTML.includes(status)), status);
  }
});

