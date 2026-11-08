import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createInterface} from 'node:readline';
import {tempOutsideGit} from './project-fixture.ts';

const self=fileURLToPath(import.meta.url), token='restart-test-only';
const sentinels=['restart-synthetic-value','legacy-synthetic-value','second-synthetic-value'];

if(process.argv[2]==='server-child') {
  process.env.KDD_PROJECT_DIR=process.argv[3];
  const {createServer}=await import('../src/server.ts');
  const server=createServer(token);
  server.listen(0,'127.0.0.1',()=>console.log(JSON.stringify({port:(server.address() as any).port})));
} else {
  const ownedProcesses=new Map<string,Array<()=>Promise<void>>>();
  async function boot(root:string,t:any) {
    const child=spawn(process.execPath,[self,'server-child',root],{
      cwd:path.resolve(import.meta.dirname,'..'),windowsHide:true,stdio:['ignore','pipe','pipe'],
      env:{...process.env,KDD_PROJECT_DIR:root,NODE_TEST_CONTEXT:'',PYTHONUTF8:'1'},
    });
    let stderr='',finished=false;
    child.stderr.on('data',chunk=>stderr+=chunk);
    const closed=new Promise<void>(resolve=>child.once('close',()=>{finished=true;resolve();}));
    const lines=createInterface({input:child.stdout});
    const ready=await new Promise<{started:boolean;port?:number;error?:string}>(resolve=>{
      const timer=setTimeout(()=>{child.kill();resolve({started:false,error:'startup timeout'});},30000);
      lines.on('line',line=>{try {const row=JSON.parse(line);if(row.port){clearTimeout(timer);resolve({started:true,port:row.port});}}catch {}});
      child.once('close',code=>{clearTimeout(timer);resolve({started:false,error:'exit '+code+': '+stderr});});
      child.once('error',error=>{clearTimeout(timer);resolve({started:false,error:String(error)});});
    });
    const stop=async()=>{if(!finished)child.kill();await closed;lines.close();};
    ownedProcesses.get(root)!.push(stop);
    return {...ready,stop};
  }
  function project(t:any) {
    const root=tempOutsideGit('kdd-board-secret-restart-');
    const owned=fs.realpathSync(root);
    ownedProcesses.set(root,[]);
    t.after(async()=>{
      for(const stop of ownedProcesses.get(root)!)await stop();
      assert.equal(fs.realpathSync(root),owned);
      assert(path.basename(root).startsWith('kdd-board-secret-restart-'));
      fs.rmSync(root,{recursive:true,force:true});
      ownedProcesses.delete(root);
    });
    return root;
  }
  async function api(actor:any,route:string,body?:unknown) {
    const response=await fetch('http://127.0.0.1:'+actor.port+route,{
      method:body===undefined?'GET':'POST',signal:AbortSignal.timeout(20000),
      headers:{authorization:'Bearer '+token,'content-type':'application/json'},
      body:body===undefined?undefined:JSON.stringify(body),
    });
    const raw=await response.text();assert(response.ok,raw);
    for(const sentinel of sentinels)assert(!raw.includes(sentinel),'response exposed a secret');
    return JSON.parse(raw);
  }
  async function fulfilled(actor:any,secretValue?:string) {
    assert.equal((await api(actor,'/api/board')).mode,'legacy');
    const task=await api(actor,'/api/tasks',{title:'Persist a human credential'});
    await api(actor,'/api/tasks/'+task.id+'/requirements',{
      fieldKey:'AUDIT_KEY',label:'Credential',description:'Synthetic restart control',isSecret:true,
    });
    const result=await api(actor,'/api/tasks/'+task.id+'/fulfill',{
      fieldKey:'AUDIT_KEY',...(secretValue===undefined?{}:{secretValue}),
    });
    assert.equal(result.task.requirements[0].isSatisfied,true);
    assert.equal(result.task.requirements[0].value,undefined);
    return task.id;
  }
  function bytes(file:string) {return fs.existsSync(file)?fs.readFileSync(file):null;}

  test('secret restart preserves a fulfilled requirement and blind metadata',{timeout:120000},async t=>{
    const root=project(t), first=await boot(root,t);assert(first.started,first.error);
    const id=await fulfilled(first,sentinels[0]);await first.stop();
    const tasks=path.join(root,'.kdd-board/tasks.json'),vault=path.join(root,'.kdd-board/vault.env');
    const originalTasks=bytes(tasks),originalVault=bytes(vault);
    assert(!originalTasks!.includes(Buffer.from(sentinels[0])));
    console.log('KDD_BOARD_RESTART_PHASE fulfilled_http_complete');
    const next=await boot(root,t);
    assert.deepEqual(bytes(tasks),originalTasks);assert.deepEqual(bytes(vault),originalVault);
    assert(next.started,next.error);
    const task=(await api(next,'/api/tasks')).find((row:any)=>row.id===id);
    assert.equal(task.status,'ready');assert.equal(task.requirements[0].isSatisfied,true);
    const meta=await api(next,'/api/vault');assert.equal(meta[0].maskedValue,'***');
    await next.stop();assert.deepEqual(bytes(tasks),originalTasks);assert.deepEqual(bytes(vault),originalVault);
  });

  test('secret restart invalidates a credential removed between processes',{timeout:120000},async t=>{
    const root=project(t),first=await boot(root,t);assert(first.started,first.error);
    const id=await fulfilled(first,sentinels[0]);await first.stop();
    const tasks=path.join(root,'.kdd-board/tasks.json'),vault=path.join(root,'.kdd-board/vault.env');
    const originalTasks=bytes(tasks);fs.unlinkSync(vault);
    console.log('KDD_BOARD_RESTART_PHASE removed_credential_http_complete');
    const next=await boot(root,t);assert(next.started,next.error);
    const task=(await api(next,'/api/tasks')).find((row:any)=>row.id===id);
    assert.equal(task.status,'needs_human_input');assert.equal(task.requirements[0].isSatisfied,false);
    assert.deepEqual(await api(next,'/api/vault'),[]);
    await next.stop();assert.deepEqual(bytes(tasks),originalTasks);assert.equal(bytes(vault),null);
  });

  test('secret restart preserves identified legacy dotenv and isolated migration',{timeout:120000},async t=>{
    const root=project(t),legacy=path.join(root,'.env.local');
    const original=Buffer.from('# Blind Vault managed credentials (KDD-Board)\nAUDIT_KEY="'+sentinels[1]+'"\n');
    fs.writeFileSync(legacy,original);
    const first=await boot(root,t);assert(first.started,first.error);
    const id=await fulfilled(first);await first.stop();
    const vault=path.join(root,'.kdd-board/vault.env'),tasks=path.join(root,'.kdd-board/tasks.json');
    const originalTasks=bytes(tasks);assert.equal(bytes(vault),null);
    console.log('KDD_BOARD_RESTART_PHASE legacy_http_complete');
    const next=await boot(root,t);assert(next.started,next.error);
    assert.equal((await api(next,'/api/tasks')).find((row:any)=>row.id===id).requirements[0].isSatisfied,true);
    assert.deepEqual(bytes(tasks),originalTasks);assert.deepEqual(bytes(legacy),original);
    await api(next,'/api/vault',{key:'SECOND',value:sentinels[2]});
    await next.stop();assert.deepEqual(bytes(legacy),original);assert(bytes(vault));
    const last=await boot(root,t);assert(last.started,last.error);
    const metadata=await api(last,'/api/vault');assert.equal(metadata.length,2);
    assert(metadata.every((row:any)=>row.maskedValue==='***'));
    await last.stop();assert.deepEqual(bytes(legacy),original);
  });
}
