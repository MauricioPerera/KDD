// Real-Git oracles for consistent perimeter errors across interfaces.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {projectFixture} from './project-fixture.ts';
import {GitTaskStore} from '../src/git-task-store.ts';
import {createGitBridge} from '../src/git-bridge.ts';
import {createWebMcpMock} from 'fastwebmcp';

const root = fileURLToPath(new URL('../../../',import.meta.url));
const source = (name:string) => pathToFileURL(path.join(root, name)).href;

async function fixture(t:any, outside=true) {
  const area=fs.mkdtempSync(path.join(os.tmpdir(),'kdd-perimeter-interface-'));
  const project=path.join(area,'product'); fs.mkdirSync(project);
  t.after(()=>{
    assert.equal(path.dirname(fs.realpathSync(area)), fs.realpathSync(os.tmpdir()));
    fs.rmSync(area,{recursive:true,force:true});
  });
  projectFixture(project);
  fs.writeFileSync(path.join(project,'knowledge/index.md'),'[Contracts](contracts/)\n');
  fs.writeFileSync(path.join(project,'.gitignore'),'__pycache__/\n*.pyc\n.env.local\n.kdd-board/\n');
  const git=(...args:string[])=>execFileSync('git',['-C',project,...args],
    {encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
  git('init','-q','-b','main');
  for(const [key,value] of [['user.name','Synthetic perimeter reviewer'],
    ['user.email','fixture@example.invalid'],['core.autocrlf','false'],
    ['maintenance.autoDetach','false'],['gc.autoDetach','false']]) git('config',key,value);
  const marker=path.join(area,'oracle-ran.txt');
  const oraclePath=path.join(project,'oracle.cjs');
  const oldOracle=fs.readFileSync(oraclePath,'utf8');
  const oracle=oldOracle+"\nif(process.env.KDD_PERIMETER_PROBE)require('node:fs').writeFileSync(process.env.KDD_PERIMETER_PROBE,'executed');\n";
  fs.writeFileSync(oraclePath,oracle);
  const contract=path.join(project,'knowledge/contracts/sample_task.md');
  fs.writeFileSync(contract,fs.readFileSync(contract,'utf8')
    .replace(crypto.createHash('sha256').update(oldOracle).digest('hex'),
             crypto.createHash('sha256').update(oracle).digest('hex')));
  const commit=(message:string)=>{git('add','-A');git('commit','-qm',message);return git('rev-parse','HEAD');};
  const approved=commit('Synthetic reviewed contract and oracle');
  const previous=process.env.KDD_PERIMETER_PROBE;
  process.env.KDD_PERIMETER_PROBE=marker;
  t.after(()=>{
    if(previous===undefined) delete process.env.KDD_PERIMETER_PROBE;
    else process.env.KDD_PERIMETER_PROBE=previous;
  });
  const store=new GitTaskStore(project);
  await store.create({task_id:'TASK-001',title:'Perimeter fixture',description:'Real interface check',
                     contract:'knowledge/contracts/sample_task.md',depends_on:[]});
  await store.transition('TASK-001',{status:'ready',approved_ref:approved});
  await store.transition('TASK-001',{status:'in_progress',assignee:'synthetic worker'});
  git('switch','-q','task/TASK-001');
  fs.appendFileSync(path.join(project,'src/hello.py'),'# implemented within the approved target\n');
  if(outside) fs.writeFileSync(path.join(project,'outside-secret-canary.txt'),'scope violation\n');
  commit('Synthetic implementation');
  git('switch','-q','main');git('merge','--no-ff','task/TASK-001','-qm','Synthetic integration');
  return {area,project,git,store,marker};
}

function snapshot(f:any) {
  return [f.git('rev-parse','HEAD'),f.git('show-ref','--heads'),
          f.git('status','--porcelain'),f.git('write-tree')];
}

function unchanged(f:any, before:any) {
  assert.deepEqual(snapshot(f),before);
  assert.equal(fs.existsSync(f.marker),false,'oracle ran before perimeter rejection');
  const folder=path.join(f.project,'docs/task-evidence');
  assert.deepEqual(fs.existsSync(folder)?fs.readdirSync(folder):[],[]);
}

function safeError(value:any,f:any) {
  const output=JSON.stringify(value);
  for(const canary of [f.project,'outside-secret-canary.txt','Traceback','INTERNAL_CONTROL_SECRET'])
    assert.equal(output.includes(canary),false);
}

async function http(t:any,f:any) {
  const previous=process.env.KDD_PROJECT_DIR;
  process.env.KDD_PROJECT_DIR=f.project;
  t.after(()=>{
    if(previous===undefined) delete process.env.KDD_PROJECT_DIR;
    else process.env.KDD_PROJECT_DIR=previous;
  });
  const {createServer}=await import(source('tools/kdd-board/src/server.ts')+'?perimeter='+path.basename(f.area));
  const token='synthetic-perimeter-interface-token';
  const server=createServer(token);
  await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>new Promise<void>((resolve,reject)=>server.close((error?:Error)=>error?reject(error):resolve())));
  const address=server.address(); assert.ok(address&&typeof address==='object');
  return {base:'http://127.0.0.1:'+address.port,token};
}

test('Store preserves TASK_PERIMETER as a safe 409 domain rejection',async t=>{
  const f=await fixture(t);const before=snapshot(f);let failure:any;
  try {await f.store.transition('TASK-001',{status:'done'});} catch(error) {failure=error;}
  assert.ok(failure,'outside implementation was accepted');
  unchanged(f,before);safeError({message:failure.message},f);
  assert.equal(failure.code,'TASK_PERIMETER');assert.equal(failure.status,409);
});

test('real authenticated HTTP preserves TASK_PERIMETER and publishes no closure',async t=>{
  const f=await fixture(t);const before=snapshot(f);const {base,token}=await http(t,f);
  const result=await fetch(base+'/api/tasks/TASK-001/status',{method:'PATCH',
    headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({status:'done'})});
  const body:any=await result.json();unchanged(f,before);safeError(body,f);
  assert.equal(result.status,409);assert.equal(body.code,'TASK_PERIMETER');
  assert.equal(body.status,409);assert.equal(typeof body.error,'string');
});

test('registered WebMCP preserves the same perimeter rejection without Git effects',async t=>{
  const f=await fixture(t);const before=snapshot(f);
  const mock=createWebMcpMock();const scope=globalThis as any;const previous=scope.document;
  scope.document=mock.document;
  try {
    createGitBridge(f.store).registerAll();
    const result:any=await mock.invokeTool('update_task_status',{task_id:'TASK-001',status:'done'});
    unchanged(f,before);safeError(result,f);
    assert.equal(result.isError,true);assert.equal(result.error.code,'TASK_PERIMETER');
    assert.equal(result.error.status,409);
  } finally {scope.document=previous;}
});

test('actual browser tool registration forwards the real HTTP domain code',async t=>{
  const f=await fixture(t);const before=snapshot(f);const {base,token}=await http(t,f);
  const registered=new Map<string,any>();const storage=new Map([['kdd-token',token]]);
  const context=vm.createContext({Headers,URLSearchParams,console,
    location:{hash:'',pathname:'/',search:''},history:{replaceState(){}},window:{},
    sessionStorage:{getItem:(key:string)=>storage.get(key),setItem:(key:string,value:string)=>storage.set(key,value)},
    fetch:(url:string,init:any)=>fetch(base+url,init),
    document:{addEventListener(){},getElementById:()=>({textContent:''}),
      modelContext:{registerTool:(tool:any)=>registered.set(tool.name,tool)}},
  });
  const app=fs.readFileSync(path.join(root,'tools/kdd-board/public/app.js'),'utf8').split('let currentTasks = []')[0];
  vm.runInContext(app,context);await vm.runInContext('registerWebMcpTools()',context);
  assert.equal(registered.size,5);
  const result=await registered.get('update_task_status').execute({task_id:'TASK-001',status:'done'});
  unchanged(f,before);safeError(result,f);
  assert.equal(result.isError,true);assert.equal(result.error.code,'TASK_PERIMETER');
  assert.equal(result.error.status,409);
});

test('in-scope real HTTP closure still records a passing oracle and exact receipt',async t=>{
  const f=await fixture(t,false);const tested=f.git('rev-parse','HEAD');
  const {base,token}=await http(t,f);
  const result=await fetch(base+'/api/tasks/TASK-001/status',{method:'PATCH',
    headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({status:'done'})});
  const body:any=await result.json();assert.equal(result.status,200,JSON.stringify(body));
  assert.equal(body.task.status,'done');assert.equal(body.task.verified_ref,tested);
  const evidence=JSON.parse(f.git('show','HEAD:'+body.task.evidence));
  assert.equal(evidence.passed_tests,1);assert.equal(fs.existsSync(f.marker),true);
  assert.deepEqual(evidence.perimeter.paths,['src/hello.py']);
});

test('unknown internal failure remains a safe 503, separate from domain rejections',async t=>{
  const f=await fixture(t,false);const before=snapshot(f);
  f.store.get=async()=>{throw new Error('INTERNAL_CONTROL_SECRET private stack');};
  const spec=createGitBridge(f.store).specs.find((item:any)=>item.name==='get_task');
  assert.ok(spec);const result:any=await spec.execute({task_id:'TASK-001'});
  unchanged(f,before);safeError(result,f);
  assert.equal(result.isError,true);assert.equal(result.error.code,'TASK_UNAVAILABLE');
  assert.equal(result.error.status,503);
});
