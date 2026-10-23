import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

function harness() {
  const nodes = new Map<string,any>();
  const node=(id:string)=>{
    if(!nodes.has(id)) nodes.set(id,{id,innerHTML:'',textContent:'',value:'',hidden:false,dataset:{},style:{},
      classList:{add(){},remove(){},toggle(){}},addEventListener(){},appendChild(){},closest(){return this;}});
    return nodes.get(id);
  };
  const calls:any[]=[];
  const errors:any[]=[];
  const task={id:'TASK-001',task_id:'TASK-001',title:'Canonical',status:'backlog',branch:'task/TASK-001',contract:'knowledge/contracts/value.md',sourceRef:'main',depends_on:[]};
  const context:any=vm.createContext({document:{activeElement:null,getElementById:node,querySelectorAll:()=>[],addEventListener(){},createElement:()=>({})},
    location:{hash:'',pathname:'/',search:''},sessionStorage:{getItem:()=> 'fixture-token'},URLSearchParams,Headers,setInterval:()=>0,
    console:{error:(...args:any[])=>errors.push(args),warn(){}}});
  context.window=context;
  const api=async(url:string,options?:any)=>{
    calls.push({url,options});
    if(url==='/api/board')return {mode:'git'};
    if(url==='/api/board/contracts')return [{id:task.contract,title:'Value'}];
    if(url==='/api/docs')return [{id:'app-value.md',filename:'value.md',title:'Value',isContract:true}];
    if(url==='/api/tools')return ['list_tasks','get_task','create_task','update_task_status','task_history'].map(name=>({name,inputSchema:{type:'object'}}));
    if(url==='/api/tasks')return [task];
    if(url==='/api/tasks/TASK-001')return {...task,journal:[{commit:'a'.repeat(40),status:'backlog',reason:'Created'}]};
    return {commit:'b'.repeat(40),task};
  };
  context.fetch=async(url:string,options?:any)=>({ok:true,json:()=>api(url,options)});
  vm.runInContext(fs.readFileSync(new URL('../public/git-board.js',import.meta.url),'utf8'),context);
  return {context,node,calls,errors,task,api,board:context.KddGitBoard};
}

test('a pending Git read cannot erase a field focused after the read began',async()=>{
  const f=harness();
  let resolveRead: (value:any)=>void=()=>{};
  const rendering=f.board.render(f.task,()=>new Promise(resolve=>{resolveRead=resolve;}),async()=>{});
  f.node('workspace-container').innerHTML='active form';
  f.node('git-approved-ref').value='a'.repeat(40);
  f.context.document.activeElement=f.node('git-approved-ref');
  resolveRead({...f.task,journal:[]});
  await rendering;
  assert.equal(f.node('workspace-container').innerHTML,'active form');
  assert.equal(f.node('git-approved-ref').value,'a'.repeat(40));
});

test('visiting docs preserves canonical contract paths for task creation',async()=>{
  const f=harness();
  vm.runInContext(fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8'),f.context);
  await vm.runInContext('loadTasks()',f.context);
  const choices=f.node('task-contract').innerHTML;
  await vm.runInContext('loadContractCatalog()',f.context);
  assert.equal(f.node('task-contract').innerHTML,choices);
  f.context.createTaskForContract('app-value.md');
  assert.equal(f.node('task-contract').value,'knowledge/contracts/value.md');
  assert.equal(f.errors.length,0,JSON.stringify(f.errors));
});

test('real browser tool registration uses Git task details and never invents approval',async()=>{
  const f=harness();const registered:any[]=[];
  f.context.document.modelContext={registerTool:(tool:any)=>registered.push(tool)};
  vm.runInContext(fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8'),f.context);
  await vm.runInContext('loadTasks()',f.context);
  await vm.runInContext('registerWebMcpTools()',f.context);
  const detail=await registered.find(t=>t.name==='get_task').execute({task_id:'TASK-001'});
  assert.equal(detail.journal[0].commit,'a'.repeat(40));
  await registered.find(t=>t.name==='update_task_status').execute({task_id:'TASK-001',status:'ready'});
  const payload=JSON.parse(f.calls.at(-1).options.body);
  assert.equal(Object.hasOwn(payload,'approved_ref'),false);
  assert.equal(f.errors.length,0,JSON.stringify(f.errors));
});

test('Git summary counts named owners and historical evidence without JSON test reports',async()=>{
  const f=harness();
  vm.runInContext(fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8'),f.context);
  await vm.runInContext('loadTasks()',f.context);
  await vm.runInContext("currentTasks=[{id:'TASK-001',status:'done',assignee:'maria',verified_ref:'abc',evidence:'proof.json'},{id:'TASK-002',status:'backlog',assignee:''}]; renderDashboard()",f.context);
  assert.equal(f.node('dash-kpi-workload').textContent,'1 / 1');
  assert.equal(f.node('dash-workload-label').textContent,'Asignadas / sin asignar');
  assert.equal(f.node('dash-kpi-tests').textContent,'50%');
  assert.equal(f.node('dash-tests-label').textContent,'Tareas con evidencia Git');
});
