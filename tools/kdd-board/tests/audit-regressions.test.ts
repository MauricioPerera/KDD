import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import {TaskStore} from '../src/task-store.ts';
import {BlindVault} from '../src/blind-vault.ts';
import {writeVersion} from '../src/persistence.ts';

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
