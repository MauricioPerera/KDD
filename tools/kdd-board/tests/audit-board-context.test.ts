import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {tempOutsideGit} from './project-fixture.ts';

const board = path.resolve(import.meta.dirname, '..');
function run(t: any, script: string, extra: Record<string,string> = {}) {
  const root = tempOutsideGit('kdd-audit-context-');
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const child = spawnSync(process.execPath, ['--input-type=module', '-e',
    "process.on('uncaughtException',error=>{console.error(error.stack);process.exitCode=1});\n" + script], {
    cwd:board, encoding:'utf8', timeout:90000,
    env:{...process.env, ...extra, KDD_PROJECT_DIR:root, NODE_TEST_CONTEXT:''},
  });
  assert.equal(child.status, 0, `stdout: ${child.stdout}\nstderr: ${child.stderr}`);
}

const setup = `
import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=process.env.KDD_PROJECT_DIR;
const git=(...args)=>{const r=spawnSync('git',['-C',root,...args],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);return r.stdout;};
const request=(s,p,method='GET',body)=>fetch('http://127.0.0.1:'+s.address().port+p,{method,headers:{authorization:'Bearer test-only','content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
`;

test('a repository created after startup cannot silently keep legacy writes', t => {
  run(t, setup + `
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {
      assert.equal((await (await request(s,'/api/board')).json()).mode,'legacy');
      git('init','-b','main');
      const vault=await request(s,'/api/vault','POST',{key:'TEST_KEY',value:'synthetic-value'});
      assert.notEqual(vault.status,200);
      assert.equal(fs.existsSync(path.join(root,'.kdd-board','vault.env')),false);
    } finally {await new Promise(r=>s.close(r));}
  `);
});

test('initializing Git after startup prevents legacy task creation', t => {
  run(t, setup + `
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {git('init','-b','main');const created=await request(s,'/api/tasks','POST',{title:'test task'});assert.notEqual(created.status,201);assert.equal(fs.existsSync(path.join(root,'.kdd-board','tasks.json')),false);}
    finally {await new Promise(r=>s.close(r));}
  `);
});

test('vault cannot rely only on transient Git configuration', t => {
  run(t, setup + `
    git('init','-b','main');const excluded=path.join(root,'temp-excludes');fs.writeFileSync(excluded,'.kdd-board/\\n');
    process.env.GIT_CONFIG_COUNT='1';process.env.GIT_CONFIG_KEY_0='core.excludesfile';process.env.GIT_CONFIG_VALUE_0=excluded;
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {const result=await request(s,'/api/vault','POST',{key:'TEST_KEY',value:'synthetic-value'});assert.notEqual(result.status,200);assert.equal(fs.existsSync(path.join(root,'.kdd-board','vault.env')),false);}
    finally {await new Promise(r=>s.close(r));}
  `);
});

test('persistent Git exclusions allow vault writes', t => {
  run(t, setup + `
    git('init','-b','main');fs.writeFileSync(path.join(root,'.gitignore'),'.kdd-board/\\n');
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {assert.equal((await request(s,'/api/vault','POST',{key:'TEST_KEY',value:'synthetic-value'})).status,200);assert.ok(fs.existsSync(path.join(root,'.kdd-board','vault.env')));assert.doesNotMatch(git('status','--porcelain','--untracked-files=all'),/vault\\.env/);}
    finally {await new Promise(r=>s.close(r));}
  `);
});

test('legacy tasks and vault remain usable outside Git', t => {
  run(t, setup + `
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {assert.equal((await request(s,'/api/tasks','POST',{title:'ordinary task'})).status,201);assert.equal((await request(s,'/api/vault','POST',{key:'TEST_KEY',value:'synthetic-value'})).status,200);}
    finally {await new Promise(r=>s.close(r));}
  `);
});

test('duplicate legacy identifiers fail closed before any write', t => {
  run(t, setup + `
    const dir=path.join(root,'.kdd-board');fs.mkdirSync(dir,{recursive:true});const file=path.join(dir,'tasks.json');
    const task={id:'duplicate',title:'First',status:'backlog',requirements:[],comments:[],updatedAt:'2026-01-01T00:00:00Z'};
    const original=JSON.stringify([task,{...task,title:'Second'}]);fs.writeFileSync(file,original);
    try {
      const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
      try {const response=await request(s,'/api/tasks','POST',{title:'Third'});assert.notEqual(response.status,201);} finally {await new Promise(r=>s.close(r));}
    } catch (error) {assert.match(String(error),/invalid|duplicate/i);}
    assert.equal(fs.readFileSync(file,'utf8'),original);
  `);
});

test('invalid nested task fields preserve the last rendered board', t => {
  run(t, setup + `
    import vm from 'node:vm';import http from 'node:http';
    let state='ok';const s=http.createServer((req,res)=>{res.setHeader('content-type','application/json');res.end(JSON.stringify([{id:'a',title:'A',status:'backlog',requirements:state==='ok'?[]:'invalid'}]));});await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {
      const source=fs.readFileSync('./public/app.js','utf8');const helper=source.slice(source.indexOf('async function apiFetch('),source.indexOf('function escapeJsArgument'));const snippet=source.slice(source.indexOf('async function fetchTasks()'),source.indexOf('// 2. Create Task'));
      const notice={hidden:true,textContent:''};let cards=[];const column={set innerHTML(value){cards=[]},get innerHTML(){return cards.map(c=>c.innerHTML).join('')},appendChild(c){cards.push(c)}};
      const context={window:{KddGitBoard:{mode:'legacy',configure:async()=>{}}},loadContractCatalog:async()=>{},apiJson:()=>{},fetch:(p,o)=>fetch('http://127.0.0.1:'+s.address().port+p,o),Headers,sessionStorage:{getItem:()=> 'test-only'},currentTasks:[],cols:{backlog:column},counts:{backlog:{textContent:''}},safePriority:()=>'',escapeHtml:x=>String(x??''),document:{getElementById:()=>notice,createElement:()=>({})},activeView:'board',console:{error(){}}};
      vm.createContext(context);vm.runInContext(helper+snippet,context);await context.fetchTasks();assert.equal(cards.length,1);const previous=column.innerHTML;state='invalid';await context.fetchTasks();assert.equal(column.innerHTML,previous);assert.ok(Array.isArray(context.currentTasks[0].requirements));assert.ok(notice.textContent);
      state='ok';await context.fetchTasks();assert.equal(cards.length,1);
    } finally {await new Promise(r=>s.close(r));}
  `);
});
