import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import {createWebMcpMock} from 'fastwebmcp';
import {projectFixture} from './project-fixture.ts';
import {GitTaskStore} from '../src/git-task-store.ts';
import {createGitBridge} from '../src/git-bridge.ts';

function fixture(t: any) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kdd-structured-errors-'));
  t.after(() => fs.rmSync(root, {recursive:true,force:true}));
  projectFixture(root);
  fs.writeFileSync(path.join(root,'.gitignore'), '__pycache__/\n*.pyc\n.env.local\n.kdd-board/\n');
  fs.writeFileSync(path.join(root,'knowledge/index.md'), '[Contracts](contracts/)\n');
  const git = (...args:string[])=>execFileSync('git',['-C',root,...args],{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
  git('init','-q','-b','main');
  git('config','user.name','Structured error fixture');
  git('config','user.email','fixture@example.invalid');
  git('config','core.autocrlf','false');
  git('add','.');
  git('commit','-qm','Simulated reviewer baseline in temporary fixture');
  const approved=git('rev-parse','HEAD'), store=new GitTaskStore(root);
  const create=async(id:string,depends_on:string[]=[])=>{
    await store.create({task_id:id,title:id,description:'Real dependency guard',
      contract:'knowledge/contracts/sample_task.md',depends_on});
    await store.transition(id,{status:'ready',approved_ref:approved});
  };
  return {root,store,git,create,approved};
}

function snapshot(f:any) {
  return [f.git('rev-parse','HEAD'),f.git('show-ref','--heads'),f.git('status','--porcelain')];
}

test('registered WebMCP reports dependency details as data without mutating Git', async t=>{
  const f=fixture(t);
  await f.create('TASK-001');
  await f.create('TASK-002',['TASK-001']);
  const mock=createWebMcpMock(), previous=globalThis.document;
  globalThis.document=mock.document as any;
  try {
    createGitBridge(f.store).registerAll();
    const before=snapshot(f);
    let result:any;
    await assert.doesNotReject(async()=>{
      result=await mock.invokeTool('update_task_status',{task_id:'TASK-002',status:'in_progress',assignee:'worker'});
    });
    assert.equal(result.isError,true);
    assert.equal(result.error.code,'TASK_DEPENDENCIES');
    assert.equal(result.error.status,409);
    assert.equal(result.error.details.task_id,'TASK-002');
    assert.deepEqual(result.error.details.pending_dependencies,['TASK-001']);
    assert.deepEqual(snapshot(f),before);
    const listed:any=await mock.invokeTool('list_tasks',{});
    assert.ok(Array.isArray(listed));
    assert.equal(listed.length,2);
  } finally {globalThis.document=previous;}
});

test('missing task, illegal edge and internal exception have safe structured errors',async t=>{
  const f=fixture(t);
  await f.create('TASK-001');
  const bridge=createGitBridge(f.store), tools=bridge.specs;
  const get:any=tools.find(x=>x.name==='get_task');
  const update:any=tools.find(x=>x.name==='update_task_status');
  let missing:any;
  await assert.doesNotReject(async()=>{missing=await get.execute({task_id:'TASK-999'});});
  assert.equal(missing.error.code,'TASK_MISSING');
  assert.equal(missing.error.status,404);
  let edge:any;
  await assert.doesNotReject(async()=>{edge=await update.execute({task_id:'TASK-001',status:'done'});});
  assert.equal(edge.isError,true);
  assert.equal(edge.error.status,400);
  const before=snapshot(f);
  f.store.get=async()=>{throw new Error('INTERNAL_SECRET_CANARY private stack and process environment');};
  let internal:any;
  await assert.doesNotReject(async()=>{internal=await get.execute({task_id:'TASK-001'});});
  assert.equal(internal.isError,true);
  assert.equal(internal.error.status,503);
  assert.ok(!JSON.stringify(internal).includes('INTERNAL_SECRET_CANARY'));
  assert.deepEqual(snapshot(f),before);
});

test('real HTTP and the actual browser registration preserve the same domain code',async t=>{
  const f=fixture(t);
  await f.create('TASK-001');
  await f.create('TASK-002',['TASK-001']);
  process.env.KDD_PROJECT_DIR=f.root;
  const {createServer}=await import(new URL('../src/server.ts?structured-error-fixture',import.meta.url).href);
  const token='temporary-integration-fixture-token';
  const server=createServer(token);
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise<void>((resolve,reject)=>server.close((error?:Error)=>error?reject(error):resolve())));
  const address=server.address();
  assert.ok(address&&typeof address==='object');
  const base='http://127.0.0.1:'+address.port;
  const before=snapshot(f);
  const url=base+'/api/tasks/TASK-002/status';
  const input={status:'in_progress',assignee:'worker'};
  const http=await fetch(url,{method:'PATCH',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
    body:JSON.stringify(input)});
  assert.equal(http.status,409);
  const body:any=await http.json();
  assert.equal(typeof body.error,'string');
  assert.equal(body.code,'TASK_DEPENDENCIES');
  assert.deepEqual(body.details.pending_dependencies,['TASK-001']);

  const registered=new Map<string,any>();
  const storage=new Map([['kdd-token',token]]);
  const context=vm.createContext({
    Headers, URLSearchParams, console,
    location:{hash:'',pathname:'/',search:''},history:{replaceState(){}},window:{},
    sessionStorage:{getItem:(key:string)=>storage.get(key),setItem:(key:string,value:string)=>storage.set(key,value)},
    fetch:(url:string,init:any)=>fetch(base+url,init),
    document:{addEventListener(){},getElementById:()=>({textContent:''}),
      modelContext:{registerTool:(tool:any)=>registered.set(tool.name,tool)}},
  });
  const app=fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8').split('let currentTasks = []')[0];
  vm.runInContext(app,context);
  await vm.runInContext('registerWebMcpTools()',context);
  assert.equal(registered.size,5);
  let result:any;
  await assert.doesNotReject(async()=>{
    result=await registered.get('update_task_status').execute({task_id:'TASK-002',...input});
  });
  assert.equal(result.isError,true);
  assert.equal(result.error.code,body.code);
  assert.deepEqual(Array.from(result.error.details.pending_dependencies),['TASK-001']);
  assert.deepEqual(snapshot(f),before);
});
