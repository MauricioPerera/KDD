import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {tempOutsideGit} from './project-fixture.ts';

const board = path.resolve(import.meta.dirname, '..');
function run(root: string, script: string) {
  const child = spawnSync(process.execPath, ['--input-type=module', '-e',
    "process.on('uncaughtException',error=>{console.error(error.stack);process.exitCode=1});\n" + script], {
    cwd: board, encoding: 'utf8', timeout: 60000,
    env: {...process.env, KDD_PROJECT_DIR: root, PYTHONUTF8: '1', NODE_TEST_CONTEXT: ''},
  });
  assert.equal(child.status, 0, `stdout: ${child.stdout}\nstderr: ${child.stderr}`);
}
function project(t: any) {
  const root = tempOutsideGit('kdd-board-runtime-');
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  return root;
}

test('vault isolates application dotenv through authenticated HTTP and restart', t => {
  const root = project(t);
  fs.writeFileSync(path.join(root, '.env.local'), '# app settings\nMULTILINE="one\ntwo"\nPLAIN=value # explanation\n');
  run(root, `
    import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path';
    import {createServer} from './src/server.ts';
    const root=process.env.KDD_PROJECT_DIR, file=path.join(root,'.env.local'), original=fs.readFileSync(file);
    const open=async()=>{const server=createServer('test-only'); await new Promise(r=>server.listen(0,'127.0.0.1',r)); return server;};
    const req=(s,p,method='GET',body)=>fetch('http://127.0.0.1:'+s.address().port+p,{method,headers:{authorization:'Bearer test-only','content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    const s=await open();
    try {assert.deepEqual(await (await req(s,'/api/vault')).json(),[]); assert.equal((await req(s,'/api/vault','POST',{key:'TEST_KEY',value:'synthetic-value'})).status,200); assert.deepEqual(fs.readFileSync(file),original);}
    finally {await new Promise(r=>s.close(r));}
    assert.ok(fs.existsSync(path.join(root,'.kdd-board','vault.env')));
  `);
  run(root, `
    import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path'; import {createServer} from './src/server.ts';
    const file=path.join(process.env.KDD_PROJECT_DIR,'.env.local'), original=fs.readFileSync(file);const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    const req=(p,method='GET')=>fetch('http://127.0.0.1:'+s.address().port+p,{method,headers:{authorization:'Bearer test-only'}});
    try {assert.equal((await (await req('/api/vault')).json())[0].key,'TEST_KEY');assert.equal((await req('/api/vault/TEST_KEY','DELETE')).status,200);assert.deepEqual(fs.readFileSync(file),original);} finally {await new Promise(r=>s.close(r));}
  `);
});

test('vault reads explicitly marked legacy data without changing it', t => {
  const root = project(t);
  const legacy = '# Blind Vault managed credentials (KDD-Board)\nPREVIOUS="synthetic-old"\n';
  fs.writeFileSync(path.join(root, '.env.local'), legacy);
  run(root, `
    import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path'; import {createServer} from './src/server.ts';
    const file=path.join(process.env.KDD_PROJECT_DIR,'.env.local'), original=fs.readFileSync(file); const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    const req=(p,method='GET',body)=>fetch('http://127.0.0.1:'+s.address().port+p,{method,headers:{authorization:'Bearer test-only','content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    try {assert.equal((await (await req('/api/vault')).json())[0].key,'PREVIOUS');assert.equal((await req('/api/vault','POST',{key:'NEXT',value:'synthetic-new'})).status,200);assert.deepEqual(fs.readFileSync(file),original);assert.deepEqual((await (await req('/api/vault')).json()).map(x=>x.key).sort(),['NEXT','PREVIOUS']);} finally {await new Promise(r=>s.close(r));}
  `);
  fs.renameSync(path.join(root, '.env.local'), path.join(root, '.env.local.saved'));
  run(root, `
    import assert from 'node:assert/strict'; import {createServer} from './src/server.ts';const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {const r=await fetch('http://127.0.0.1:'+s.address().port+'/api/vault',{headers:{authorization:'Bearer test-only'}});assert.deepEqual((await r.json()).map(x=>x.key).sort(),['NEXT','PREVIOUS']);} finally {await new Promise(r=>s.close(r));}
  `);
});

test('live catalog refreshes against real main and preserves a valid selection', t => {
  const root = project(t);
  run(root, `
    import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path'; import vm from 'node:vm'; import {execFileSync} from 'node:child_process';
    const root=process.env.KDD_PROJECT_DIR;const git=(...a)=>execFileSync('git',['-C',root,...a],{stdio:'pipe'});git('init','-q','-b','main');git('config','user.name','Test');git('config','user.email','test@example.invalid');git('config','gc.auto','0');git('config','maintenance.auto','false');fs.mkdirSync(path.join(root,'knowledge','contracts'),{recursive:true});
    const commit=(name)=>{fs.writeFileSync(path.join(root,'knowledge','contracts',name+'.md'),name);git('add','.');git('commit','-qm',name);};commit('first');
    const {createServer}=await import('./src/server.ts');const s=createServer('test-only');await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {const nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,style:{},value:'',innerHTML:'',textContent:'',closest(){return {style:{}}}});return nodes.get(id)};const document={getElementById:node},window={};vm.runInNewContext(fs.readFileSync('./public/git-board.js','utf8'),{document,window});
      const api=async p=>{const r=await fetch('http://127.0.0.1:'+s.address().port+p,{headers:{authorization:'Bearer test-only'}});assert.equal(r.status,200);return r.json();};
      await window.KddGitBoard.configure(api); assert.match(node('task-contract').innerHTML,/first\.md/);node('task-contract').value='knowledge/contracts/first.md';commit('second');await window.KddGitBoard.configure(api);
      assert.match(node('task-contract').innerHTML,/second\.md/);assert.equal(node('task-contract').value,'knowledge/contracts/first.md');
    } finally {await new Promise(r=>s.close(r));}
  `);
});

test('task polling retains last good data and displays real HTTP error then recovers', t => {
  const root = project(t);
  run(root, `
    import assert from 'node:assert/strict'; import fs from 'node:fs'; import vm from 'node:vm'; import http from 'node:http';
    let state='ok';const s=http.createServer((req,res)=>{res.setHeader('content-type','application/json');res.statusCode=state==='error'?503:200;res.end(JSON.stringify(state==='error'?{error:'Git coordinator unavailable',code:'TASK_UNAVAILABLE'}:state==='invalid'?{unexpected:true}:[{id:'TASK-001',status:'backlog',title:'preserved',sourceRef:'main'}]));});await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {const source=fs.readFileSync('./public/app.js','utf8');const helper=source.slice(source.indexOf('async function apiFetch('),source.indexOf('function escapeJsArgument'));const snippet=source.slice(source.indexOf('async function fetchTasks()'),source.indexOf('// 2. Create Task'));const notice={hidden:true,textContent:''};const column={innerHTML:'',children:[],appendChild(x){this.children.push(x)}};const base='http://127.0.0.1:'+s.address().port;const context={window:{KddGitBoard:{mode:'git',configure:async()=>{}}},apiJson:()=>{},fetch:(p,o)=>fetch(base+p,o),Headers,sessionStorage:{getItem:()=> 'test-only'},currentTasks:[],cols:{backlog:column},counts:{backlog:{textContent:''}},safePriority:()=>'',escapeHtml:x=>String(x??''),document:{getElementById:()=>notice,createElement:()=>({})},activeView:'board',console:{error(){}}};vm.createContext(context);vm.runInContext(helper+snippet,context);
      await context.fetchTasks();assert.equal(context.currentTasks[0].id,'TASK-001');column.innerHTML='last good card';state='error';await context.fetchTasks();assert.ok(Array.isArray(context.currentTasks));assert.equal(context.currentTasks[0].id,'TASK-001');assert.equal(column.innerHTML,'last good card');assert.match(notice.textContent,/Git coordinator unavailable/);state='ok';await context.fetchTasks();assert.equal(context.currentTasks[0].id,'TASK-001');assert.ok(notice.hidden || !notice.textContent.includes('unavailable'));column.innerHTML='last good card';state='invalid';await context.fetchTasks();assert.ok(Array.isArray(context.currentTasks));assert.equal(context.currentTasks[0].id,'TASK-001');assert.equal(column.innerHTML,'last good card');state='ok';await context.fetchTasks();assert.equal(context.currentTasks[0].id,'TASK-001');
    } finally {await new Promise(r=>s.close(r));}
  `);
});

test('task polling rejects a successful response with a non-list body', t => {
  const root = project(t);
  run(root, `
    import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';import http from 'node:http';
    const s=http.createServer((req,res)=>{res.setHeader('content-type','application/json');res.end(JSON.stringify({unexpected:true}));});await new Promise(r=>s.listen(0,'127.0.0.1',r));
    try {const source=fs.readFileSync('./public/app.js','utf8');const helper=source.slice(source.indexOf('async function apiFetch('),source.indexOf('function escapeJsArgument'));const snippet=source.slice(source.indexOf('async function fetchTasks()'),source.indexOf('// 2. Create Task'));const notice={hidden:true,textContent:''},column={innerHTML:'last good card'};const context={window:{KddGitBoard:{mode:'git',configure:async()=>{}}},apiJson:()=>{},fetch:(p,o)=>fetch('http://127.0.0.1:'+s.address().port+p,o),Headers,sessionStorage:{getItem:()=> 'test-only'},currentTasks:[{id:'TASK-001'}],cols:{backlog:column},document:{getElementById:()=>notice},activeView:'board',console:{error(){}}};vm.createContext(context);vm.runInContext(helper+snippet,context);await context.fetchTasks();assert.ok(Array.isArray(context.currentTasks));assert.equal(context.currentTasks[0].id,'TASK-001');assert.equal(column.innerHTML,'last good card');assert.ok(notice.textContent);}
    finally {await new Promise(r=>s.close(r));}
  `);
});
