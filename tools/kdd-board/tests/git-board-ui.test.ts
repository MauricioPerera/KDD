import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function ui() {
  const nodes = new Map<string,any>();
  const node = (id: string) => {
    if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',value:'',hidden:false,disabled:false,
      dataset:{}, style:{}, classList:{add(){},remove(){}}, closest(){return this;},
      insertAdjacentHTML(){}, addEventListener(){}, setAttribute(){}, querySelectorAll(){return [];}});
    return nodes.get(id);
  };
  const calls: any[] = [];
  const errors: string[] = [];
  const context: any = vm.createContext({document:{getElementById:node, activeElement:null,querySelectorAll:()=>[]}, console,
    alert:(message:string)=>errors.push(message), URLSearchParams, Headers});
  context.window=context;
  vm.runInContext(fs.readFileSync(new URL('../public/git-board.js',import.meta.url),'utf8'), context);
  const api = async (url: string, options?: any) => {
    calls.push({url,options});
    if(url==='/api/board') return {mode:'git',sourceRef:'main'};
    if(url==='/api/board/contracts') return [{id:'knowledge/contracts/value.md',title:'Value'}];
    if(url.endsWith('/history')) return [{commit:'a'.repeat(40),status:'backlog',reason:'Created <script>'}];
    return {commit:'b'.repeat(40),task:{status:'ready'}};
  };
  return {context,node,calls,errors,api,board:context.KddGitBoard};
}

test('Git form requires explicit ID and committed contract without legacy priority or owner fields',async()=>{
  const f=ui();
  await f.board.configure(f.api);
  assert.equal(f.node('task-id').required,true);
  assert.equal(f.node('task-contract').required,true);
  assert.match(f.node('task-contract').innerHTML,/knowledge\/contracts\/value.md/);
  f.node('task-id').value='TASK-012';
  f.node('task-dependencies').value='TASK-001, TASK-002';
  const input=f.board.createInput({title:'Value',description:'Check',contractId:'knowledge/contracts/value.md',priority:'high',assignee:'human'});
  assert.deepEqual(JSON.parse(JSON.stringify(input)),{task_id:'TASK-012',title:'Value',description:'Check',contract:'knowledge/contracts/value.md',depends_on:['TASK-001','TASK-002']});
});

test('Git workspace shows only legal edges, safely renders identity and preserves typed fields',async()=>{
  const f=ui(); await f.board.configure(f.api);
  const task={id:'TASK-001',task_id:'TASK-001',title:'<script>alert(1)</script>',description:'Check',status:'backlog',assignee:'maria',branch:'task/TASK-001',contract:'knowledge/contracts/value.md',approved_ref:'',depends_on:[],journal:[]};
  await f.board.render(task,f.api,async()=>{});
  const html=f.node('workspace-container').innerHTML;
  assert.ok(!html.includes('<script>'));
  assert.match(html,/task\/TASK-001/);
  assert.match(html,/value.md/);
  assert.match(html,/value="ready"/);
  assert.doesNotMatch(html,/value="done"/);
  f.node('git-approved-ref').value='user is typing';
  f.context.document.activeElement=f.node('git-approved-ref');
  f.node('workspace-container').innerHTML='preserved form';
  await f.board.render(task,f.api,async()=>{});
  assert.equal(f.node('workspace-container').innerHTML,'preserved form');
});

test('transition sends explicit approval and refreshes only after commit; errors stay visible',async()=>{
  const f=ui(); await f.board.configure(f.api);
  const task={id:'TASK-001',status:'backlog',branch:'task/TASK-001',contract:'knowledge/contracts/value.md',title:'Task',depends_on:[],journal:[]};
  let refreshes=0;
  await f.board.render(task,f.api,async()=>{refreshes++;});
  f.node('git-next-status').value='ready';
  f.node('git-approved-ref').value='c'.repeat(40);
  await f.node('git-transition-form').onsubmit({preventDefault(){}});
  const call=f.calls.find(c=>c.options?.method==='PATCH');
  assert.equal(call.url,'/api/tasks/TASK-001/status');
  assert.equal(JSON.parse(call.options.body).approved_ref,'c'.repeat(40));
  assert.equal(refreshes,1);
  await f.board.render(task,async()=>{throw new Error('TASK_DIRTY: preserve changes');},async()=>{refreshes++;});
  await f.node('git-transition-form').onsubmit({preventDefault(){}});
  assert.match(f.node('git-action-result').textContent,/TASK_DIRTY/);
  assert.equal(refreshes,1);
});

test('browser registers Git WebMCP arguments and preserves explicit transition payloads',async()=>{
  const f=ui();
  const registered:any[]=[];
  f.context.document.addEventListener=()=>{};
  f.context.document.createElement=()=>({innerHTML:''});
  f.context.document.modelContext={registerTool:(tool:any)=>registered.push(tool)};
  f.context.location={hash:'',pathname:'/',search:''};
  f.context.sessionStorage={getItem:()=> 'test-token'};
  f.context.setInterval=()=>0;
  const tools=['list_tasks','get_task','create_task','update_task_status','task_history'];
  f.context.fetch=async(url:string,options:any)=>({ok:true,json:async()=>{
    if(url==='/api/tools') return tools.map(name=>({name,inputSchema:{type:'object'}}));
    if(options){f.calls.push({url,options});return {commit:'d'.repeat(40)};}
    if(url==='/api/docs'||url==='/api/tasks') return [];
    return f.api(url,options);
  }});
  vm.runInContext(fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8'),f.context);
  await vm.runInContext('registerWebMcpTools()',f.context);
  assert.deepEqual(registered.map(x=>x.name).sort(),tools.sort());
  await registered.find(x=>x.name==='update_task_status').execute({task_id:'TASK-001',status:'ready',approved_ref:'e'.repeat(40)});
  assert.equal(JSON.parse(f.calls.at(-1).options.body).approved_ref,'e'.repeat(40));
  await registered.find(x=>x.name==='create_task').execute({task_id:'TASK-002',title:'Test',description:'Check',contract:'knowledge/contracts/value.md'});
  assert.equal(JSON.parse(f.calls.at(-1).options.body).task_id,'TASK-002');
});
