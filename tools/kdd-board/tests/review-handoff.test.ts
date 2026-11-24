import {after, before, test} from 'node:test';
import type {TestContext} from 'node:test';
import assert from 'node:assert/strict';
import {execFile, execFileSync, spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {once} from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {promisify} from 'node:util';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {projectFixture, tempOutsideGit} from './project-fixture.ts';

// Exercise git-api.ts through the same authenticated server used by Board.
const server = new URL('../src/server.ts', import.meta.url);
const cli = fileURLToPath(new URL('../../../scripts/tasks.py', import.meta.url));
const ui = fs.readFileSync(new URL('../public/git-board.js', import.meta.url), 'utf8');
const token = 'board-test-token';
const task = 'TASK-001';
const route = `/api/tasks/${task}/review-handoff`;
let root: string, directory: string, base: string, first: string, second: string, tree: string;
let evidence: string;

function git(...args: string[]) {
  return execFileSync('git', ['--no-optional-locks', '-C', root, ...args],
    {encoding: 'utf8', stdio: 'pipe'}).trim();
}

function act(...args: string[]) {
  const env = {...process.env};
  delete env.NODE_TEST_CONTEXT;
  return JSON.parse(execFileSync(process.env.KDD_PYTHON || 'python',
    [cli, '--repo-root', root, ...args, '--json'], {encoding:'utf8', stdio:'pipe', env}));
}

function register(id: string) {
  act('create', id, '--title', 'Review candidate', '--description', 'Real Git task for resumption',
    '--contract', 'knowledge/contracts/sample_task.md');
}

before(() => {
  root = tempOutsideGit('kdd-board-handoff-');
  projectFixture(root);
  fs.writeFileSync(path.join(root, 'knowledge/index.md'), '[Contracts](contracts/)\n');
  fs.writeFileSync(path.join(root, '.gitignore'), '.agents/logs/\n__pycache__/\n');
  git('init', '-q', '-b', 'main');
  git('config', 'user.name', 'Board review test');
  git('config', 'user.email', 'board@example.test');
  git('config', 'core.autocrlf', 'false');
  git('add', '.');
  git('commit', '-qm', 'Base');
  base = git('rev-parse', 'HEAD');
  git('switch', '-qc', 'review');
  fs.writeFileSync(path.join(root, 'proposal.md'), 'A new proposal.\n');
  git('add', 'proposal.md');
  git('commit', '-qm', 'Candidate');
  first = git('rev-parse', 'HEAD');
  tree = git('rev-parse', 'HEAD^{tree}');
  git('commit', '--allow-empty', '-qm', 'Same tree, different candidate');
  second = git('rev-parse', 'HEAD');
  git('switch', '-q', 'main');
  register(task);
  register('TASK-002');
  act('ready', 'TASK-002', '--approved-ref', base);
  act('ready', task, '--approved-ref', base);
  act('start', task, '--assignee', 'board reviewer');
  git('switch', '-q', 'task/' + task);
  fs.appendFileSync(path.join(root, 'src/hello.py'), '# completed implementation\n');
  git('add', 'src/hello.py');
  git('commit', '-qm', 'Implementation');
  git('switch', '-q', 'main');
  git('merge', '--no-ff', 'task/' + task, '-m', 'Integrate implementation');
  evidence = act('finish', task).task.evidence;
  assert.equal(typeof evidence, 'string');
  git('switch', '-qc', 'untrusted-checkout');
  const taskPath = path.join(root, 'knowledge/tasks', task + '.md');
  const altered = fs.readFileSync(taskPath, 'utf8')
    .replaceAll(base, first).replaceAll(evidence, 'forged-evidence.json');
  fs.writeFileSync(taskPath, altered);
  git('add', taskPath);
  git('commit', '-qm', 'Change the task on the selected checkout only');
  assert.notEqual(git('rev-parse', 'HEAD'), git('rev-parse', 'main'));
  directory = path.join(root, '.agents/logs/board-reviews', task);
  fs.mkdirSync(directory, {recursive:true});
});

after(() => {
  if (root) fs.rmSync(root, {recursive:true, force:true});
});

const selection = (candidate: string) => ({base_commit:base, candidate_commit:candidate});
function select(candidate: string, previous: string[] = []) {
  fs.writeFileSync(path.join(directory, 'selection.json'),
    JSON.stringify({current:selection(candidate), previous:previous.map(selection)}));
}

function record(ready = true) {
  return JSON.stringify({
    schema_version:1, ...selection(first), candidate_tree:tree, author:'Author',
    risk:'medium', risk_rationale:'API follow-up', risk_factors:['api'], findings:[],
    reviews:[{id:'review-1', reviewer:'Reviewer', kind:'agent', fresh_context:true,
      status:'completed', read_set:[{revision:'candidate', path:'proposal.md'}],
      lenses:['simplicity','oracle','implementation'].map(name => ({
        name, assessment:ready ? 'pass' : 'blocked', rationale:'PRIVATE_REVIEW_TRANSCRIPT \u00f1',
      }))}],
  }, null, 2) + '\n';
}

async function start(t: TestContext) {
  const env: NodeJS.ProcessEnv = {...process.env, KDD_PROJECT_DIR:root};
  delete env.NODE_TEST_CONTEXT;
  const script = `import {createServer} from ${JSON.stringify(server.href)};
    const s = createServer(${JSON.stringify(token)});
    s.listen(0, '127.0.0.1', () => console.log(s.address().port));`;
  const child = spawn(process.execPath, ['--input-type=module', '-e', script], {
    cwd:root, env, windowsHide:true, stdio:['ignore','pipe','pipe'],
  });
  const closed = once(child, 'close');
  const stop = async () => { child.kill(); await closed; };
  t.after(stop);
  const port = await new Promise<string>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Board startup timed out')), 20_000);
    child.once('error', reject);
    child.once('close', code => {clearTimeout(timeout); reject(new Error(`Board exited: ${code}`));});
    child.stdout.once('data', bytes => {clearTimeout(timeout); resolve(String(bytes).trim());});
  });
  assert.match(port, /^\d+$/);
  const request = (url = route, method = 'GET', authenticated = true) => fetch(
    `http://127.0.0.1:${port}${url}`,
    {method, headers:authenticated ? {Authorization:`Bearer ${token}`} : {},
      signal:AbortSignal.timeout(30_000)},
  );
  const read = async () => {
    const response = await request();
    assert.equal(response.status, 200, await response.clone().text());
    return response.json();
  };
  return {request, read, stop};
}

test('new Board process resumes exact Git task and v1 without writing', async t => {
  select(first);
  const raw = Buffer.from(record().replaceAll('\n', '\r\n'), 'utf8');
  const target = path.join(directory, first + '.json');
  fs.writeFileSync(target, raw);
  const selectionPath = path.join(directory, 'selection.json');
  const selectionBytes = fs.readFileSync(selectionPath);
  const indexPath = git('rev-parse', '--path-format=absolute', '--git-path', 'index');
  const index = fs.readFileSync(indexPath);
  const before = git('status','--porcelain=v1');
  const refs = git('show-ref');
  const localFiles = fs.readdirSync(directory).sort();
  const board = await start(t);
  const result = await board.read();
  await board.stop();
  assert.deepEqual(await (await start(t)).read(), result);
  assert.equal(result.task_id, task);
  assert.equal(result.approved_ref, base);
  assert.notEqual(result.approved_ref, result.current.candidate_commit);
  assert.equal(result.evidence, evidence);
  assert.deepEqual(result.previous, []);
  assert.deepEqual(result.current, {...selection(first), candidate_tree:tree,
    review_status:'ready', review_sha256:createHash('sha256').update(raw).digest('hex'), finding_codes:[]});
  assert.equal(git('show-ref'), refs);
  assert.equal(git('status','--porcelain=v1'), before);
  assert.deepEqual(fs.readdirSync(directory).sort(), localFiles);
  assert.deepEqual(fs.readFileSync(target), raw);
  assert.deepEqual(fs.readFileSync(selectionPath), selectionBytes);
  assert.deepEqual(fs.readFileSync(indexPath), index);
});

test('different commit on the same tree is pending and retains the historical review', async t => {
  select(second, [first]);
  fs.writeFileSync(path.join(directory, first + '.json'), record());
  assert.notEqual(first, second);
  assert.equal(git('rev-parse', second + '^{tree}'), tree);
  const result = await (await start(t)).read();
  assert.deepEqual(result.current, {...selection(second), candidate_tree:tree,
    review_status:'missing', review_sha256:null, finding_codes:[]});
  assert.equal(result.previous.length, 1);
  assert.equal(result.previous[0].candidate_commit, first);
  assert.equal(result.previous[0].review_status, 'ready');
  assert.equal(result.approved_ref, base);
});

test('old v1 under the new filename cannot make the candidate ready', async t => {
  select(second, [first]);
  const target = path.join(directory, second + '.json');
  fs.writeFileSync(target, record());
  t.after(() => fs.unlinkSync(target));
  const response = await (await start(t)).request();
  assert.equal(response.status, 409);
  const error = await response.json();
  assert.equal(error.code, 'REVIEW_HANDOFF_INVALID');
  assert.doesNotMatch(JSON.stringify(error), /PRIVATE_REVIEW_TRANSCRIPT|board-handoff-/);
});

test('inconclusive v1 is blocked and exposes only the check codes', async t => {
  select(first);
  const target = path.join(directory, first + '.json');
  fs.writeFileSync(target, record(false));
  const board = await start(t);
  const result = await board.read();
  assert.equal(result.current.review_status, 'blocked');
  assert.ok(result.current.finding_codes.includes('LENS_BLOCKED'));
  assert.equal(result.approved_ref, base);
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE_REVIEW_TRANSCRIPT/);
  const major = JSON.parse(record());
  major.findings.push({id:'risk-1', severity:'major', status:'open', scope:'proposal.md',
    rationale:'PRIVATE_FINDING', decided_by:null, evidence:[]});
  const raw = JSON.stringify(major);
  fs.writeFileSync(target, raw);
  assert.deepEqual(await board.read(), {task_id:task, approved_ref:base, evidence, previous:[],
    current:{...selection(first), candidate_tree:tree, review_status:'blocked',
      review_sha256:createHash('sha256').update(raw).digest('hex'), finding_codes:['OPEN_FINDING']}});
});

test('rejects duplicate selection keys and linked review files', async t => {
  const target = path.join(directory, first + '.json');
  const source = path.join(root, '.agents/logs/original-review.json');
  fs.writeFileSync(source, record());
  fs.rmSync(target, {force:true});
  fs.linkSync(source, target);
  t.after(() => fs.rmSync(target, {force:true}));
  const board = await start(t);
  select(first);
  let response = await board.request();
  assert.equal(response.status, 409);
  assert.equal((await response.json()).code, 'REVIEW_HANDOFF_INVALID');
  fs.unlinkSync(target);
  fs.writeFileSync(target, record());
  assert.equal((await board.request()).status, 200);
  fs.writeFileSync(path.join(directory, 'selection.json'),
    `{"current":${JSON.stringify(selection(first))},"previous":[],"previous":[]}`);
  response = await board.request();
  assert.equal(response.status, 409);
  assert.equal((await response.json()).code, 'REVIEW_HANDOFF_INVALID');
  assert.equal(fs.readFileSync(source, 'utf8'), record());
});

test('rejects oversized selection and invalid UTF-8 inside a review string', async t => {
  select(first);
  const reviewPath = path.join(directory, first + '.json');
  fs.writeFileSync(reviewPath, record());
  const board = await start(t);
  assert.equal((await board.request()).status, 200);
  const target = path.join(directory, 'selection.json');
  const valid = fs.readFileSync(target);
  const reject = async () => {
    const response = await board.request();
    assert.equal(response.status, 409);
    assert.equal((await response.json()).code, 'REVIEW_HANDOFF_INVALID');
  };
  fs.writeFileSync(target, Buffer.concat([valid, Buffer.alloc(256 * 1024, 32)]));
  await reject();
  fs.writeFileSync(target, valid);
  const parts = record().split('PRIVATE_REVIEW_TRANSCRIPT');
  const raw = Buffer.concat([Buffer.from(parts.shift()!), Buffer.from([0xff]),
    Buffer.from(parts.join('PRIVATE_REVIEW_TRANSCRIPT'))]);
  assert.doesNotThrow(() => JSON.parse(raw.toString('utf8')));
  fs.writeFileSync(reviewPath, raw);
  await reject();
});

test('only authenticated reads of existing tasks are supported', async t => {
  const board = await start(t);
  assert.equal((await board.request(route, 'GET', false)).status, 401);
  assert.equal((await board.request(route, 'PATCH')).status, 409);
  assert.equal((await board.request('/api/tasks/TASK-999/review-handoff')).status, 404);
  const unconfigured = await board.request('/api/tasks/TASK-002/review-handoff');
  assert.equal(unconfigured.status, 200);
  assert.deepEqual(await unconfigured.json(), {task_id:'TASK-002', approved_ref:base, evidence:null,
    current:null, previous:[]});
});

test('a linked task directory and a missing historical review are rejected', async t => {
  const board = await start(t);
  const other = path.join(path.dirname(directory), 'TASK-002');
  fs.symlinkSync(directory, other, process.platform === 'win32' ? 'junction' : 'dir');
  t.after(() => fs.unlinkSync(other));
  const linked = await board.request('/api/tasks/TASK-002/review-handoff');
  assert.equal(linked.status, 409);
  assert.equal((await linked.json()).code, 'REVIEW_HANDOFF_INVALID');
  select(second, [first]);
  fs.rmSync(path.join(directory, first + '.json'), {force:true});
  const missing = await board.request();
  assert.equal(missing.status, 409);
  assert.equal((await missing.json()).code, 'REVIEW_HANDOFF_INVALID');
});

test('rejects a linked ancestor even when the selected files are regular', async t => {
  select(first);
  fs.writeFileSync(path.join(directory, first + '.json'), record());
  const board = await start(t);
  assert.equal((await board.request()).status, 200);
  const parent = path.dirname(directory);
  const saved = parent + '-regular';
  fs.renameSync(parent, saved);
  try {
    fs.symlinkSync(saved, parent, process.platform === 'win32' ? 'junction' : 'dir');
    const response = await board.request();
    assert.equal(response.status, 409);
    assert.equal((await response.json()).code, 'REVIEW_HANDOFF_INVALID');
  } finally {
    if (fs.existsSync(parent)) fs.unlinkSync(parent);
    fs.renameSync(saved, parent);
  }
});

test('missing candidate blobs cannot trigger an implicit Git fetch', async t => {
  select(first);
  fs.writeFileSync(path.join(directory, first + '.json'), record());
  const oid = git('rev-parse', first + ':proposal.md');
  const objectPath = path.join(root, '.git/objects', oid.slice(0, 2), oid.slice(2));
  const object = fs.readFileSync(objectPath);
  let hits = 0;
  const remote = http.createServer((_request, response) => {
    hits++;
    response.writeHead(404).end();
  });
  await new Promise<void>(resolve => remote.listen(0, '127.0.0.1', resolve));
  t.after(() => remote.close());
  const address = remote.address();
  assert.ok(address && typeof address !== 'string');
  git('config', 'remote.review-probe.url', `http://127.0.0.1:${address.port}`);
  git('config', 'remote.review-probe.promisor', 'true');
  fs.unlinkSync(objectPath);
  t.after(() => {
    fs.writeFileSync(objectPath, object);
    git('config', '--remove-section', 'remote.review-probe');
  });
  const gitEnv = {...process.env, GIT_NO_LAZY_FETCH:'0', GIT_ALLOW_PROTOCOL:'http',
    GIT_TERMINAL_PROMPT:'0'};
  await assert.rejects(promisify(execFile)('git', ['-C', root, 'cat-file', 'blob', oid],
    {env:gitEnv, timeout:10_000}));
  assert.ok(hits > 0, 'control tries to fetch the missing blob');
  const controlHits = hits;
  const response = await (await start(t)).request();
  assert.equal(response.status, 409);
  assert.equal((await response.json()).code, 'REVIEW_HANDOFF_INVALID');
  assert.equal(hits, controlHits);
});

test('the Git detail queries on click and shows current and historical SHA from HTTP', async t => {
  select(second, [first]);
  fs.writeFileSync(path.join(directory, first + '.json'), record());
  const board = await start(t);
  const nodes = new Map<string, any>();
  function node(id: string) {
    if (!nodes.has(id)) {
      const item = {innerHTML:'', textContent:'', disabled:false};
      if (id === 'workspace-container') {
        let markup = '';
        Object.defineProperty(item, 'innerHTML', {
          get:() => markup,
          set:(value: string) => {
            markup = value;
            for (const key of nodes.keys()) if (key !== id) nodes.delete(key);
          },
        });
      }
      nodes.set(id, item);
    }
    return nodes.get(id);
  }
  const context = vm.createContext({document:{getElementById:node, activeElement:{}}});
  context.window = context;
  vm.runInContext(ui, context);
  let reads = 0;
  let fail = false;
  let waiting: Promise<unknown> | undefined;
  const render = (id = task) => context.KddGitBoard.render({id,status:'backlog',journal:[]}, async (url: string) => {
    reads++;
    assert.equal(url, route);
    if (waiting) return waiting;
    if (fail) throw new Error('Revision no disponible <script>');
    return board.read();
  }, async () => {});
  const html = () => node('workspace-container').innerHTML + node('git-review-result').innerHTML;
  await render();
  assert.equal(reads, 0);
  assert.match(node('workspace-container').innerHTML, /id="git-review-load"/);
  await node('git-review-load').onclick();
  assert.equal(reads, 1);
  assert.match(html(), new RegExp(first));
  assert.match(html(), new RegExp(second));
  assert.match(html(), /Pendiente de revisi[oó]n/i);
  assert.match(html(), /Hist[oó]rico|Anteriores/i);
  assert.ok(html().includes(createHash('sha256').update(record()).digest('hex')));
  assert.doesNotMatch(html(), /PRIVATE_REVIEW_TRANSCRIPT/);
  await render();
  assert.match(html(), new RegExp(first));
  assert.equal(reads, 1);
  fail = true;
  await node('git-review-load').onclick();
  const errorText = () => html() + node('git-review-result').textContent;
  assert.match(errorText(), /Revision no disponible/);
  assert.doesNotMatch(html(), /<script>/);
  await render();
  assert.match(errorText(), /Revision no disponible/);
  assert.equal(reads, 2);
  const payload = await board.read();
  let deliver!: (value: unknown) => void;
  waiting = new Promise(resolve => {deliver = resolve;});
  const click = node('git-review-load').onclick();
  await render('TASK-002');
  deliver(payload);
  await click;
  assert.doesNotMatch(html(), new RegExp(first));
  assert.doesNotMatch(html(), new RegExp(second));
});
