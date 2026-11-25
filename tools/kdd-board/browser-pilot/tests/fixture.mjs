import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {projectFixture} from '../../tests/project-fixture.ts';

const [repository, descriptor, python] = process.argv.slice(2);
if (!repository || !descriptor || !python) throw new Error('Expected a temporary repository, descriptor and Python');
fs.mkdirSync(repository);
projectFixture(repository);
const env = Object.fromEntries(Object.entries(process.env).filter(([name]) => !name.startsWith('GIT_')));
Object.assign(env, {GIT_CONFIG_GLOBAL: process.platform === 'win32' ? 'NUL' : '/dev/null',
  GIT_CONFIG_NOSYSTEM: '1', GIT_TERMINAL_PROMPT: '0', PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1'});
delete env.NODE_TEST_CONTEXT;
const exec = (tool, args) => execFileSync(tool, args,
  {cwd: repository, env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 30000}).trim();
const git = (...args) => exec('git', args);
const task = fileURLToPath(new URL('../../../../scripts/tasks.py', import.meta.url));
fs.writeFileSync(path.join(repository, '.gitignore'), '.agents/logs/\n.kdd-board/\n__pycache__/\n');
fs.writeFileSync(path.join(repository, 'knowledge/index.md'), '[Contracts](contracts/)\n');
git('init', '-q', '-b', 'main');
git('config', 'user.name', 'Temporary Board fixture');
git('config', 'user.email', 'board@example.test');
git('config', 'core.autocrlf', 'false');
git('config', 'commit.gpgsign', 'false');
git('add', '.');
git('commit', '-qm', 'Baseline del fixture');
const base = git('rev-parse', 'HEAD');
git('switch', '-qc', 'review');
fs.writeFileSync(path.join(repository, 'proposal.md'), 'Revision de prueba.\n');
git('add', 'proposal.md');
git('commit', '-qm', 'Candidato revisado');
const ready = git('rev-parse', 'HEAD');
const tree = git('rev-parse', 'HEAD^{tree}');
git('commit', '--allow-empty', '-qm', 'Mismo arbol con revision pendiente');
const missing = git('rev-parse', 'HEAD');
git('switch', '-q', 'main');

for (const row of [
  {id: 'TASK-001', title: 'Relevo listo', candidate: ready},
  {id: 'TASK-002', title: 'Relevo pendiente', candidate: missing},
]) {
  exec(python, ['-B', task, '--repo-root', repository, 'create', row.id, '--title', row.title,
    '--description', 'Tarea sintetica de navegador', '--contract', 'knowledge/contracts/sample_task.md', '--json']);
  const directory = path.join(repository, '.agents/logs/board-reviews', row.id);
  fs.mkdirSync(directory, {recursive: true});
  const selection = {base_commit: base, candidate_commit: row.candidate};
  fs.writeFileSync(path.join(directory, 'selection.json'), JSON.stringify({current: selection, previous: []}));
  if (row.candidate !== ready) continue;
  const v1 = {
    schema_version: 1, ...selection, candidate_tree: tree, author: 'Synthetic author',
    risk: 'medium', risk_rationale: 'Browser fixture for an API workflow', risk_factors: ['api'],
    reviews: [{id: 'review', reviewer: 'Synthetic external reviewer', kind: 'agent',
      fresh_context: true, status: 'completed', read_set: [{revision: 'candidate', path: 'proposal.md'}],
      lenses: ['simplicity', 'oracle', 'implementation'].map(name =>
        ({name, assessment: 'pass', rationale: 'Synthetic review for the Board fixture.'}))}],
    findings: [],
  };
  fs.writeFileSync(path.join(directory, ready + '.json'), JSON.stringify(v1));
}
const main = git('rev-parse', 'main');
process.env.KDD_PROJECT_DIR = repository;
process.env.KDD_PYTHON = python;
const {createServer} = await import('../../src/server.ts');
const server = createServer('synthetic-browser-pilot-token');
server.listen(0, '127.0.0.1', () => {
  const origin = 'http://127.0.0.1:' + server.address().port;
  fs.writeFileSync(descriptor, JSON.stringify({origin, main, base, ready, missing}));
});
