import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { executeTaskTest } from '../src/test-runner.ts';
import { TaskStore } from '../src/task-store.ts';
import { BlindVault } from '../src/blind-vault.ts';
import { writeVersion } from '../src/persistence.ts';
import { runTaskTests } from '../src/task-execution.ts';
import { projectFixture } from './project-fixture.ts';

test('printed TAP totals cannot verify a task without executed tests', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-fake-tap-'));
  try {
    const printed = await executeTaskTest(`node -e "console.log('# pass 1'); console.log('# fail 0')"`, root);
    assert.equal(printed.passedTests, 0);
    fs.writeFileSync(path.join(root, 'oracle.cjs'), "console.log('# tests 1\\n# suites 0\\n# pass 1\\n# fail 0\\n# cancelled 0\\n# skipped 0\\n# todo 0\\n# duration_ms 1');");
    const oracle = path.join(root, 'oracle.cjs');
    const noTests = await executeTaskTest('node --test oracle.cjs', root, {}, oracle);
    assert.equal(noTests.passedTests, 0);
    const mismatch = await executeTaskTest(`node -e "require('node:fs').writeFileSync('ran', 'yes')"`, root, {}, oracle);
    assert.equal(mismatch.success, false);
    assert.equal(fs.existsSync(path.join(root, 'ran')), false);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('a sealed oracle that only prints TAP cannot complete a task', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-fake-oracle-'));
  try {
    projectFixture(root);
    const fake = "console.log('# pass 1\\n# fail 0');";
    fs.writeFileSync(path.join(root, 'oracle.cjs'), fake);
    const contractPath = path.join(root, 'knowledge/contracts/sample_task.md');
    const contract = fs.readFileSync(contractPath, 'utf8').replace(/tests_sha256: '[a-f0-9]+'/, `tests_sha256: '${crypto.createHash('sha256').update(fake).digest('hex')}'`);
    fs.writeFileSync(contractPath, contract);
    const store = new TaskStore(path.join(root, 'tasks.json'));
    const task = store.createTask({title: 'fake result', description: '', contractId: 'app-sample_task.md'});
    const {report} = await runTaskTests(store, new BlindVault(path.join(root, '.env.local')), root, task.id);
    assert.equal(report.passedTests, 0);
    assert.throws(() => store.updateTaskStatus(task.id, 'done'), /evidence/i);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('reports saved before runner verification cannot complete a task', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-old-report-'));
  try {
    projectFixture(root);
    const store = new TaskStore(path.join(root, 'tasks.json'));
    const task = store.createTask({title: 'old evidence', description: '', contractId: 'app-sample_task.md'});
    const {report} = await runTaskTests(store, new BlindVault(path.join(root, '.env.local')), root, task.id);
    assert.equal(report.verifiedOracle, true);
    report.verifiedOracle = undefined;
    store.recordTestReport(task.id, report);
    assert.throws(() => store.updateTaskStatus(task.id, 'done'), /evidence/i);
  } finally { fs.rmSync(root, {recursive: true, force: true}); }
});

test('priority is validated by the store and authenticated HTTP API', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-priority-'));
  projectFixture(root);
  const store = new TaskStore(path.join(root, 'local-tasks.json'));
  const payload = `<img src=x onerror=alert(1)>`;
  assert.throws(() => store.createTask({title: 'bad', description: '', priority: payload as any}), /priority/i);
  process.env.KDD_PROJECT_DIR = root;
  const {createServer} = await import('../src/server.ts');
  const server = createServer('priority-test-token');
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address() as {port: number};
  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/api/tasks`, {
      method: 'POST', headers: {Authorization: 'Bearer priority-test-token', 'Content-Type': 'application/json'},
      body: JSON.stringify({title: 'bad', priority: payload}),
    });
    assert.equal(response.status, 400);
  } finally {
    await new Promise<void>((resolve, reject) => server.close(err => err ? reject(err) : resolve()));
    fs.rmSync(root, {recursive: true, force: true});
    delete process.env.KDD_PROJECT_DIR;
  }
});

test('a legacy malformed priority renders as safe text in both views', async () => {
  const nodes = new Map<string, any>();
  const node = (id: string) => {
    if (!nodes.has(id)) nodes.set(id, {
      innerHTML: '', children: [] as any[], textContent: '', value: '', dataset: {}, style: {},
      classList: {add(){}, remove(){}, toggle(){}}, addEventListener(){}, appendChild(child: any) {this.children.push(child);},
    });
    return nodes.get(id);
  };
  const task = {id: 'task-1', title: 'legacy', description: '', priority: `<img src=x onerror=alert(1)>`, status: 'backlog', assignee: 'human', updatedAt: new Date().toISOString(), requirements: [], comments: []};
  const context: any = vm.createContext({
    document: {getElementById: node, querySelectorAll: () => [], addEventListener(){}, createElement: () => ({innerHTML: '', className: ''})},
    window: null, location: {hash: '', pathname: '/', search: ''},
    sessionStorage: {getItem: () => 'test-token', setItem(){}},
    URLSearchParams, Headers, console, setInterval: () => 0,
    fetch: async (url: string) => ({ok: true, json: async () => url === '/api/tasks' ? [task] : []}),
  });
  context.window = context;
  vm.runInContext(fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8'), context);
  await vm.runInContext('loadTasks()', context);
  const card = node('col-backlog').children.at(-1);
  assert.ok(card);
  assert.ok(!card.innerHTML.includes('<img'));
  vm.runInContext("renderTaskWorkspace('task-1')", context);
  assert.ok(!node('workspace-container').innerHTML.includes('<img'));
});

test('stale writers cannot overwrite tasks or credentials; deleted tasks stay deleted', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-regression-'));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const tasks = path.join(root, 'tasks.json');
  const a = new TaskStore(tasks), b = new TaskStore(tasks);
  const first = a.createTask({title:'first',description:''});
  assert.throws(() => b.createTask({title:'second',description:''}), /conflict/);
  assert.equal(b.getAllTasks().length, 1);
  b.createTask({title:'second',description:''});
  a.getAllTasks();
  b.deleteTask(first.id);
  assert.equal(a.getTask(first.id), undefined);
  assert.equal(a.getAllTasks().length, 1);
  const vault = path.join(root, 'vault.env');
  const x = new BlindVault(vault), y = new BlindVault(vault);
  x.setSecret('FIRST', 'dummy-one');
  assert.throws(() => y.setSecret('SECOND', 'dummy-two'), /conflict/);
  assert.equal(y.hasSecret('FIRST'), true);
  y.setSecret('SECOND', 'dummy-two');
  assert.equal(x.listSecrets().length, 2);
});

test('writer lock fails closed and corrupt task data is preserved', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-lock-'));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const file = path.join(root, 'tasks.json');
  fs.writeFileSync(file, '{broken');
  assert.throws(() => new TaskStore(file), /Invalid task storage/);
  fs.writeFileSync(file + '.lock', '');
  assert.throws(() => writeVersion(file, '{broken', '[]'), /EEXIST/);
  assert.equal(fs.readFileSync(file, 'utf8'), '{broken');
});

test('contract IDs are rejected at creation and linking', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-ids-'));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const store = new TaskStore(path.join(root, 'tasks.json'));
  const id = "x');globalThis.auditMarker=1;//";
  assert.throws(() => store.createTask({title:'bad',description:'',contractId:id}), /Invalid contract ID/);
  const task = store.createTask({title:'good',description:'',contractId:'app-sample.md'});
  assert.throws(() => store.linkContract(task.id, id), /Invalid contract ID/);
});

test('contract navigation passes hostile identifiers as data, not executable handlers', () => {
  const source = fs.readFileSync(new URL('../public/app.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /onclick="[^"\n]*(?:goToContract|loadDocItem|createTaskForContract)/);
  let listener: (event: any) => void = () => { throw new Error('listener missing'); };
  let observed = '';
  const context = {document:{addEventListener(name: string, fn: typeof listener, capture: boolean) {
    assert.equal(name, 'click'); assert.equal(capture, true); listener = fn;
  }}, window:{goToContract(id: string){observed=id;}}};
  vm.runInNewContext(source.slice(0, source.indexOf('const tokenFromLink')), context);
  const id = "x');globalThis.auditMarker=1;//";
  listener({target:{closest(){return {dataset:{contractId:id,contractAction:'go'}};}}, preventDefault(){}, stopPropagation(){}});
  assert.equal(observed, id);
  assert.equal((context as any).auditMarker, undefined);
});
