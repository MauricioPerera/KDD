import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import type {AddressInfo} from 'node:net';
import path from 'node:path';
import {test, type TestContext} from 'node:test';
import {fileURLToPath} from 'node:url';
import {projectFixture, tempOutsideGit} from './project-fixture.ts';

const here = fileURLToPath(new URL('../../../', import.meta.url));
const cli = path.join(here, 'scripts/tasks.py');
const evidenceDir = new URL('fixtures/board-evidence/', import.meta.url);
// Exercise git-api.ts through the actual authenticated Board server.
const snapshot = '/api/tasks/TASK-001/evidence';
const pilot = '/api/board/evidence/browser-pilot';
const contract = 'knowledge/contracts/sample_task.md';
const token = 'board-evidence-integration-test';
const auth = {Authorization: 'Bearer ' + token};
const sha = (data: string | Buffer) => createHash('sha256').update(data).digest('hex');
const taskDigest = (data: string) => sha(data.replace(/\r\n?/g,'\n'));
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_') && key !== 'NODE_TEST_CONTEXT'));
Object.assign(env, {GIT_CONFIG_GLOBAL:process.platform === 'win32' ? 'NUL' : '/dev/null',
  GIT_CONFIG_NOSYSTEM:'1', GIT_TERMINAL_PROMPT:'0', PYTHONUTF8:'1', PYTHONDONTWRITEBYTECODE:'1'});

function git(cwd: string, ...args: string[]) {
  return execFileSync('git',['--no-replace-objects', ...args],{cwd,env,encoding:'utf8',stdio:'pipe',timeout:20000});
}

function temporary(t: TestContext) {
  const root = tempOutsideGit('kdd-board-evidence-');
  t.after(() => fs.rmSync(root,{force:true,recursive:true,maxRetries:4}));
  return root;
}

function init(root: string) {
  git(root,'init','-q','-b','main');
  for (const [key,value] of [['user.name','Board test fixture'],['user.email','board@example.test'],
    ['core.autocrlf','false'],['commit.gpgsign','false']]) git(root,'config',key,value);
}

function historical(t: TestContext) {
  const root = temporary(t);
  init(root);
  const objects = git(here,'rev-parse','--path-format=absolute','--git-path','objects').trim();
  fs.writeFileSync(path.join(root,'.git/objects/info/alternates'),objects.replaceAll('\\','/')+'\n');
  const observed = git(here,'rev-parse','HEAD').trim();
  git(root,'update-ref','refs/heads/main',observed);
  return {root,observed};
}

let serverNumber = 0;
async function serve(t: TestContext, root: string, settings: Record<string,string> = {}) {
  const keys = new Set(['KDD_PROJECT_DIR','KDD_BOARD_BROWSER_EVIDENCE_DIR','KDD_BOARD_BROWSER_EVIDENCE_PIN',
    ...Object.keys(process.env).filter(key=>key.startsWith('GIT_')), 'GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM']);
  const old = new Map([...keys].map(key=>[key,process.env[key]]));
  for (const key of keys) delete process.env[key];
  Object.assign(process.env,{KDD_PROJECT_DIR:root,GIT_CONFIG_GLOBAL:env.GIT_CONFIG_GLOBAL,
    GIT_CONFIG_NOSYSTEM:'1',...settings});
  const source = new URL('../src/server.ts', import.meta.url);
  source.searchParams.set('board-test-evidence',String(++serverNumber));
  try {
    const {createServer} = await import(source.href);
    const server = createServer(token);
    t.after(async () => {
      await new Promise<void>(resolve=>server.close(()=>resolve()));
      for (const [key,value] of old) {
        if (value === undefined) delete process.env[key];
        else process.env[key] = value;
      }
    });
    server.listen(0,'127.0.0.1');
    await once(server,'listening');
    const origin = 'http://127.0.0.1:'+(server.address() as AddressInfo).port;
    // Git subprocesses block this fixture between requests. Use a fresh socket.
    return (url:string,headers:Record<string,string>=auth) =>
      fetch(origin+url,{headers:{...headers,Connection:'close'}});
  } catch(error) {
    for (const [key,value] of old) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    throw error;
  }
}

test('real historical task v1 returns only its attested run-level evidence', async t => {
  const {root,observed} = historical(t);
  const request = await serve(t,root);
  const file = 'docs/task-evidence/TASK-001-b9654fbcb1f759c9196edfd64819f8dd1cde435f.json';
  const raw = git(root,'show',observed+':'+file);
  const history = JSON.parse(raw);
  const res = await request(snapshot);
  assert.equal(res.status,200);
  const body = await res.json();
  assert.equal(body.status,'available');
  assert.equal(body.observed_commit,observed);
  assert.equal(body.task_id,'TASK-001');
  assert.equal(body.tested_commit,history.tested_commit);
  assert.equal(body.approved_ref,history.approved_ref);
  assert.deepEqual(body.artifact,{path:file,sha256:taskDigest(raw)});
  assert.deepEqual(body.receipt,{version:1,runner:history.runner,total:history.passed_tests,granularity:'run',files:[]});
  assert.ok(!JSON.stringify(body).includes('"stdout"') && !JSON.stringify(body).includes('"stderr"'));
  assert.equal(git(root,'rev-parse','refs/heads/main').trim(),observed);
});

test('an unconfigured pilot does not claim that tests ran', async t => {
  const {root} = historical(t);
  const request = await serve(t,root);
  const res = await request(pilot);
  assert.equal(res.status,200);
  const body = await res.json();
  assert.equal(body.status,'unavailable');
  assert.ok(!Object.hasOwn(body,'cases'));
});

test('real v2 closure returns per-file counts and rejects inconsistent proof', {timeout:140000}, async t => {
  const root = temporary(t);
  projectFixture(root);
  fs.writeFileSync(path.join(root,'knowledge/index.md'),'[Contracts](contracts/)\n');
  init(root);
  const gitHere = (...args:string[]) => git(root,...args);
  const commit = (note:string) => {gitHere('add','-A'); gitHere('commit','-qm',note);};
  commit('Original contract');
  const approved = gitHere('rev-parse','HEAD').trim();
  const act = (...args:string[]) => JSON.parse(execFileSync(process.env.KDD_PYTHON || 'python',
    ['-B',cli,'--repo-root',root,...args,'--json'],{cwd:root,env,encoding:'utf8',stdio:'pipe',timeout:65000}));
  act('create','TASK-001','--title','Evidence','--description','Real Node oracle','--contract',contract);
  const request = await serve(t,root);
  await t.test('pending and missing tasks cannot produce receipts', async () => {
    const pending = await request(snapshot);
    assert.equal(pending.status,200);
    const body = await pending.json();
    assert.equal(body.status,'pending');
    assert.ok(!Object.hasOwn(body,'receipt'));
    assert.equal((await request('/api/tasks/TASK-999/evidence')).status,404);
  });
  await t.test('an unauthenticated caller cannot read evidence', async () => {
    assert.equal((await request(snapshot,{})).status,401);
  });
  act('ready','TASK-001','--approved-ref',approved);
  act('start','TASK-001','--assignee','fixture');
  gitHere('switch','-q','task/TASK-001');
  fs.appendFileSync(path.join(root,'src/hello.py'),'# Actual change\n');
  commit('Change product');
  gitHere('switch','-q','main');
  gitHere('merge','--no-ff','task/TASK-001','-m','Integrate product');
  const done = act('finish','TASK-001');
  assert.equal(done.task.status,'done');
  const file = done.task.evidence;
  const committed = gitHere('show','HEAD:'+file);
  const exact = JSON.parse(committed);
  assert.equal(exact.schema_version,2);
  assert.equal(exact.oracle_results['oracle.cjs'].executed,1);
  const index = fs.readFileSync(path.join(root,'.git/index'));
  const refs = gitHere('show-ref');
  fs.writeFileSync(path.join(root,file),'working-tree draft');
  await t.test('shows the observed Git closure, ignoring a local receipt with the same path', async () => {
    const res = await request(snapshot);
    assert.equal(res.status,200);
    const body = await res.json();
    assert.equal(body.status,'available');
    assert.equal(body.observed_commit,done.commit);
    assert.equal(body.approved_ref,approved);
    assert.equal(body.tested_commit,exact.tested_commit);
    assert.deepEqual(body.artifact,{path:file,sha256:taskDigest(committed)});
    assert.deepEqual(body.receipt,{version:2,runner:exact.runner,total:1,granularity:'file',
      files:[{path:'oracle.cjs',executed:1,skipped:0,ok:true}]});
    assert.ok(!JSON.stringify(body).includes('"stdout"') && !JSON.stringify(body).includes('"stderr"'));
  });
  assert.equal(gitHere('show-ref'),refs);
  assert.deepEqual(fs.readFileSync(path.join(root,'.git/index')),index);
  assert.equal(fs.readFileSync(path.join(root,file),'utf8'),'working-tree draft');

  const node = path.join(root,'knowledge/tasks/TASK-001.md');
  const text = fs.readFileSync(node,'utf8');
  assert.ok(text.includes(done.task.evidence_sha256));
  const variants = [
    {name:'task identity',change:{task_id:'TASK-999'}},
    {name:'tested commit',change:{tested_commit:approved}},
    {name:'instrumented total',change:{passed_tests:2}},
  ];
  for (const probe of variants) {
    const invalid = JSON.stringify({...exact,...probe.change})+'\n';
    fs.writeFileSync(path.join(root,file),invalid);
    fs.writeFileSync(node,text.replace(done.task.evidence_sha256,taskDigest(invalid)));
    commit('Synthetic inconsistent '+probe.name+' with a matching digest');
    await t.test('rejects a mismatched '+probe.name+' even with a matching digest', async () => {
      const res = await request(snapshot);
      assert.equal(res.status,409);
      const body = await res.json();
      assert.equal(body.code,'TASK_EVIDENCE_INVALID');
      assert.ok(!Object.hasOwn(body,'receipt'));
    });
  }
});

test('real Chromium bundle preserves case and attempt identity', async t => {
  const root = temporary(t);
  init(root);
  fs.writeFileSync(path.join(root,'README.md'),'Independent project fixture\n');
  git(root,'add','README.md');
  git(root,'commit','-qm','Unrelated consumer project');
  const dir = temporary(t);
  const receipt = fs.readFileSync(new URL('receipt.json',evidenceDir));
  const report = fs.readFileSync(new URL('report.json',evidenceDir));
  const recorded = JSON.parse(receipt.toString('utf8'));
  const run = JSON.parse(report.toString('utf8')).run;
  assert.equal(sha(report),recorded.report_sha256);
  assert.equal(run.id,recorded.run_id);
  assert.equal(run.results.length,2);
  assert.throws(()=>git(root,'cat-file','-e',recorded.checkout),/Command failed/);
  fs.writeFileSync(path.join(dir,'receipt.json'),receipt);
  fs.writeFileSync(path.join(dir,'report.json'),report);
  const request = await serve(t,root,{KDD_BOARD_BROWSER_EVIDENCE_DIR:dir,
    KDD_BOARD_BROWSER_EVIDENCE_PIN:recorded.checkout+':'+sha(receipt)});
  await t.test('opens the pinned local report with two real cases and no manufactured files', async () => {
    const res = await request(pilot);
    assert.equal(res.status,200);
    const body = await res.json();
    assert.equal(body.status,'available');
    assert.equal(body.source,'local_bundle');
    assert.equal(body.checkout,recorded.checkout);
    assert.equal(body.approved_ref,recorded.approved_ref);
    assert.equal(body.run_id,recorded.run_id);
    assert.equal(body.receipt_sha256,sha(receipt));
    assert.equal(body.report_sha256,sha(report));
    assert.deepEqual(body.cases,run.results.map((result:any)=>({id:result.testId,status:result.status,
      attempt:result.attempts[0].index,duration_ms:result.attempts[0].durationMs,artifacts:[]})));
    assert.ok(!Object.hasOwn(body,'task_id'));
    assert.ok(!JSON.stringify(body).includes('synthetic-browser-pilot-token'));
  });
  assert.deepEqual(fs.readFileSync(path.join(dir,'receipt.json')),receipt);
  const changed = Buffer.concat([report,Buffer.from('\n')]);
  fs.writeFileSync(path.join(dir,'report.json'),changed);
  await t.test('rejects different report bytes', async () => {
    const res = await request(pilot);
    assert.equal(res.status,409);
    const body = await res.json();
    assert.equal(body.code,'BROWSER_EVIDENCE_INVALID');
    assert.ok(!Object.hasOwn(body,'cases'));
  });
  fs.writeFileSync(path.join(dir,'receipt.json'),JSON.stringify({...recorded,report_sha256:sha(changed)}));
  await t.test('rejects a replaced bundle pair even when their hashes agree internally', async () => {
    const res = await request(pilot);
    assert.equal(res.status,409);
    const body = await res.json();
    assert.equal(body.code,'BROWSER_EVIDENCE_INVALID');
    assert.ok(!Object.hasOwn(body,'cases'));
  });
  await t.test('uncredentialed and static requests cannot expose the local bundle', async () => {
    assert.equal((await request(pilot,{})).status,401);
    assert.equal((await request('/report.json',{})).status,404);
  });
});

test('pin coherence cannot replace the original Chromium verification', async t => {
  const {root,observed} = historical(t);
  const receipt = fs.readFileSync(new URL('receipt.json',evidenceDir));
  const report = fs.readFileSync(new URL('report.json',evidenceDir));
  const recorded = JSON.parse(receipt.toString('utf8'));
  const invalidCase = JSON.parse(report.toString('utf8'));
  invalidCase.run.results[0].testId = 'tests/handoff.e2e.ts::unexpected';
  const changedCase = Buffer.from(JSON.stringify(invalidCase));
  const invalidAttachment = JSON.parse(report.toString('utf8'));
  invalidAttachment.run.results[0].attempts[0].artifacts = [{kind:'file',path:'sample.png'}];
  const changedAttachment = Buffer.from(JSON.stringify(invalidAttachment));
  const invalidStepAttachment = JSON.parse(report.toString('utf8'));
  invalidStepAttachment.run.results[0].attempts[0].steps[0].artifacts = [{kind:'file',path:'sample.png'}];
  const changedStepAttachment = Buffer.from(JSON.stringify(invalidStepAttachment));
  const cases = [
    {name:'the authentic bytes at a linked directory',
      proof:recorded, report, linked:true},
    {name:'a different checkout even with an externally matching digest',
      proof:{...recorded,checkout:recorded.approved_ref}, report},
    {name:'an approved ref outside the recorded checkout ancestry',
      proof:{...recorded,approved_ref:observed}, report},
    {name:'an inconsistent run identity', proof:{...recorded,run_id:'01a20000-0000-7000-8000-000000000000'},report},
    {name:'a digest-consistent report with the wrong case inventory',
      proof:{...recorded,report_sha256:sha(changedCase),
        ids:invalidCase.run.results.map((item:any)=>item.testId).sort()}, report:changedCase},
    {name:'an attachment outside the supported pilot format',
      proof:{...recorded,report_sha256:sha(changedAttachment)}, report:changedAttachment},
    {name:'a step attachment outside the supported pilot format',
      proof:{...recorded,report_sha256:sha(changedStepAttachment)}, report:changedStepAttachment},
  ];
  for (const probe of cases) {
    await t.test('rejects '+probe.name, async scope=>{
      const dir = temporary(scope);
      const real = path.join(dir,'real');
      const configured = path.join(dir,'configured');
      fs.mkdirSync(real);
      const pinned = probe.linked ? receipt : Buffer.from(JSON.stringify(probe.proof));
      fs.writeFileSync(path.join(real,'receipt.json'),pinned);
      fs.writeFileSync(path.join(real,'report.json'),probe.report);
      if (probe.linked) fs.symlinkSync(real,configured,process.platform==='win32'?'junction':'dir');
      const request = await serve(scope,root,{KDD_BOARD_BROWSER_EVIDENCE_DIR:probe.linked?configured:real,
        KDD_BOARD_BROWSER_EVIDENCE_PIN:recorded.checkout+':'+sha(pinned)});
      const res = await request(pilot);
      assert.equal(res.status,409);
      const body = await res.json();
      assert.equal(body.code,'BROWSER_EVIDENCE_INVALID');
      assert.ok(!Object.hasOwn(body,'cases'));
    });
  }
});
