import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createWebMcpMock} from 'fastwebmcp';
import {projectFixture} from './project-fixture.ts';
import {GitTaskStore} from '../src/git-task-store.ts';
import {createGitBridge,transitionSchema} from '../src/git-bridge.ts';

const cli=fileURLToPath(new URL('../../../scripts/tasks.py',import.meta.url));
const validator=fileURLToPath(new URL('../../../scripts/validate_tasks.py',import.meta.url));

function fixture(t:any,format:'sha1'|'sha256') {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'kdd-board-sha-formats-'));
  t.after(()=>{
    assert.equal(path.dirname(fs.realpathSync(root)),fs.realpathSync(os.tmpdir()));
    fs.rmSync(root,{recursive:true,force:true});
  });
  projectFixture(root);
  fs.writeFileSync(path.join(root,'knowledge/index.md'),'[Contracts](contracts/)\n');
  fs.writeFileSync(path.join(root,'.gitignore'),'__pycache__/\n*.pyc\n.env.local\n.kdd-board/\n');
  const git=(...args:string[])=>execFileSync('git',['-C',root,...args],{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
  git('init','-q','-b','main','--object-format='+format);
  for(const [key,value] of [['user.name','Board SHA integration'],['user.email','sha@example.invalid'],
      ['core.autocrlf','false'],['maintenance.autoDetach','false'],['gc.autoDetach','false']]) git('config',key,value);
  const commit=(message:string)=>{git('add','-A');git('commit','-qm',message);return git('rev-parse','HEAD');};
  const approved=commit('approved native contract and oracle');
  assert.equal(git('rev-parse','--show-object-format'),format);
  const act=(...args:string[])=>JSON.parse(execFileSync(process.env.KDD_PYTHON||'python',
    [cli,'--repo-root',root,...args,'--json'],{encoding:'utf8',stdio:['ignore','pipe','pipe']}));
  const input={task_id:'TASK-001',title:'Native SHA task',description:'Verify actual Git identities',
    contract:'knowledge/contracts/sample_task.md',depends_on:[]};
  return {root,git,commit,approved,act,input,store:new GitTaskStore(root)};
}

for(const format of ['sha1','sha256'] as const) {
  test(format+': schema accepts the actual native approval and rejects malformed inputs',t=>{
    const f=fixture(t,format);
    assert.equal(transitionSchema.safeParse({status:'ready',approved_ref:f.approved}).success,true);
    for(const reference of ['HEAD',f.approved.slice(1),'z'.repeat(f.approved.length)])
      assert.equal(transitionSchema.safeParse({status:'ready',approved_ref:reference}).success,false);
  });

  test(format+': Store completes every task edge with commits and real sealed evidence',async t=>{
    const f=fixture(t,format);
    const created=await f.store.create(f.input);
    assert.equal(created.commit,f.git('rev-parse','HEAD'));
    await assert.doesNotReject(f.store.transition('TASK-001',{status:'ready',approved_ref:f.approved}));
    await f.store.transition('TASK-001',{status:'in_progress',assignee:'integration'});
    await f.store.transition('TASK-001',{status:'needs_human_input',reason:'Review requested'});
    await f.store.transition('TASK-001',{status:'ready',reason:'Review completed'});
    await f.store.transition('TASK-001',{status:'in_progress',assignee:'integration'});
    f.git('switch','-q','task/TASK-001');
    fs.appendFileSync(path.join(f.root,'src/hello.py'),'# implementation integrated\n');
    f.commit('implementation');f.git('switch','-q','main');
    f.git('merge','--no-ff','task/TASK-001','-m','integrate implementation');
    const verified=f.git('rev-parse','HEAD');
    const done=await f.store.transition('TASK-001',{status:'done'});
    assert.equal(done.commit,f.git('rev-parse','main'));
    assert.equal(done.task.approved_ref,f.approved);
    assert.equal(done.task.verified_ref,verified);
    assert.equal(done.commit.length,format==='sha1'?40:64);
    assert.equal(JSON.parse(f.git('show','main:'+done.task.evidence)).passed_tests,1);
    const history=await f.store.history('TASK-001');
    assert.deepEqual(history.map(h=>h.status),['backlog','ready','in_progress','needs_human_input','ready','in_progress','done']);
    assert.equal(history.at(-1)?.commit,done.commit);
    execFileSync(process.env.KDD_PYTHON||'python',[validator,'--repo-root',f.root,'--base-ref',f.approved,'--head-ref','main'],{encoding:'utf8'});
    const before=f.git('rev-parse','HEAD');
    await assert.rejects(f.store.transition('TASK-001',{status:'done'}));
    assert.equal(f.git('rev-parse','HEAD'),before);
  });

  test(format+': authenticated HTTP preserves native approval and its confirmed commit',async t=>{
    const f=fixture(t,format);const previous=process.env.KDD_PROJECT_DIR;
    process.env.KDD_PROJECT_DIR=f.root;
    const {createServer}=await import('../src/server.ts?sha-format='+format);
    const server=createServer('sha-format-token');
    await new Promise<void>(resolve=>server.listen(0,'127.0.0.1',resolve));
    const base=`http://127.0.0.1:${(server.address() as any).port}`;
    const request=(url:string,method='GET',body?:unknown)=>fetch(base+url,{method,
      headers:{Authorization:'Bearer sha-format-token','Content-Type':'application/json'},
      body:body===undefined?undefined:JSON.stringify(body)});
    try {
      assert.equal((await fetch(base+'/api/tasks')).status,401);
      assert.equal((await request('/api/tasks','POST',f.input)).status,201);
      const ready=await request('/api/tasks/TASK-001/status','PATCH',{status:'ready',approved_ref:f.approved});
      assert.equal(ready.status,200,await ready.clone().text());
      const result:any=await ready.json();
      assert.equal(result.commit,f.git('rev-parse','main'));
      assert.equal(result.task.approved_ref,f.approved);
      const history:any=await (await request('/api/tasks/TASK-001/history')).json();
      assert.equal(history.at(-1).commit,result.commit);
      const before=f.git('rev-parse','HEAD');
      assert.equal((await request('/api/tasks/TASK-001/status','PATCH',{status:'done'})).status,400);
      assert.equal(f.git('rev-parse','HEAD'),before);
    } finally {
      server.closeIdleConnections();
      await new Promise<void>((resolve,reject)=>server.close((error?:Error)=>error?reject(error):resolve()));
      if(previous===undefined)delete process.env.KDD_PROJECT_DIR;else process.env.KDD_PROJECT_DIR=previous;
    }
  });

  test(format+': WebMCP transports the native approval and journal unchanged',async t=>{
    const f=fixture(t,format);const mock=createWebMcpMock();const previous=globalThis.document;
    globalThis.document=mock.document as any;
    try {
      assert.ok(createGitBridge(f.store).registerAll().every(Boolean));
      const created:any=await mock.invokeTool('create_task',f.input);
      assert.equal(created.commit,f.git('rev-parse','main'));
      let result:any;
      await assert.doesNotReject(async()=>{
        result=await mock.invokeTool('update_task_status',{task_id:'TASK-001',status:'ready',approved_ref:f.approved});
      });
      assert.equal(result.isError,undefined,JSON.stringify(result));
      assert.equal(result.commit,f.git('rev-parse','main'));
      const task:any=await mock.invokeTool('get_task',{task_id:'TASK-001'});
      assert.equal(task.approved_ref,f.approved);
      const history:any=await mock.invokeTool('task_history',{task_id:'TASK-001'});
      assert.equal(history.at(-1).commit,result.commit);
    } finally {globalThis.document=previous;}
  });

  test(format+': controlled DOM accepts the actual native approval in its input pattern',async t=>{
    const f=fixture(t,format);const created=await f.store.create(f.input);
    const ui=controlledDom(created);await ui.board.configure(ui.api);
    await ui.board.render({...created.task,id:'TASK-001',journal:[]},ui.api,async()=>{});
    const html=ui.node('workspace-container').innerHTML;
    const pattern=/id="git-approved-ref"[^>]*pattern="([^"]+)"/.exec(html)?.[1];
    assert.ok(pattern,'the approval field must expose a browser validation pattern');
    assert.equal(new RegExp('^(?:'+pattern+')$').test(f.approved),true);
  });

  test(format+': controlled DOM confirms a real CLI commit and refreshes once',async t=>{
    const f=fixture(t,format);
    const created=await f.store.create(f.input);
    // Obtain a real canonical response independently, so the UI regression is
    // exercised even when the pre-fix Store rejects a SHA-256 approval.
    const ready=f.act('ready','TASK-001','--approved-ref',f.approved);
    const ui=controlledDom(ready);
    await ui.board.configure(ui.api);let refreshes=0;
    await ui.board.render({...created.task,id:'TASK-001',journal:[]},ui.api,async()=>{refreshes++;});
    ui.node('git-next-status').value='ready';ui.node('git-approved-ref').value=f.approved;
    await ui.node('git-transition-form').onsubmit({preventDefault(){}});
    assert.equal(JSON.parse(ui.calls.at(-1).options.body).approved_ref,f.approved);
    assert.equal(refreshes,1);
    assert.ok(ui.node('git-action-result').textContent.includes(ready.commit));
  });
}

function controlledDom(reply:any) {
  const nodes=new Map<string,any>();
  const node=(id:string)=>{
    if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,disabled:false,
      dataset:{},style:{},classList:{add(){},remove(){}},closest(){return this;}});
    return nodes.get(id);
  };
  const context:any=vm.createContext({document:{getElementById:node,activeElement:null},console});
  context.window=context;
  vm.runInContext(fs.readFileSync(new URL('../public/git-board.js',import.meta.url),'utf8'),context);
  const calls:any[]=[];
  const api=async(url:string,options?:any)=>{
    if(url==='/api/board')return {mode:'git',sourceRef:'main'};
    if(url==='/api/board/contracts')return [{id:'knowledge/contracts/sample_task.md',title:'Native contract'}];
    calls.push({url,options});return reply;
  };
  return {node,board:context.KddGitBoard,api,calls};
}

test('controlled DOM does not confirm or refresh for an invalid commit response',async()=>{
  const f=controlledDom({commit:'HEAD',task:{status:'ready'}});await f.board.configure(f.api);
  let refreshes=0;
  await f.board.render({id:'TASK-001',title:'Invalid response',status:'backlog',depends_on:[],journal:[]},f.api,async()=>{refreshes++;});
  f.node('git-next-status').value='ready';f.node('git-approved-ref').value='a'.repeat(40);
  await f.node('git-transition-form').onsubmit({preventDefault(){}});
  assert.equal(refreshes,0);
  assert.match(f.node('git-action-result').textContent,/sin commit confirmado/);
});
