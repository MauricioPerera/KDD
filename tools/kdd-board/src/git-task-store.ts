import {execFile, execFileSync} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
import path from 'node:path';

const execute = promisify(execFile);
const cli = fileURLToPath(new URL('../../../scripts/tasks.py', import.meta.url));
export const transitions: Record<string, Record<string, string>> = {
  backlog: {ready:'ready'}, ready: {in_progress:'start'},
  in_progress: {needs_human_input:'block', done:'finish'}, needs_human_input: {ready:'resume'}, done: {},
};
export type GitTask = Record<string, any> & {id:string; task_id:string; status:string; sourceRef:'main'};
export type JournalEntry = {commit:string; status:string; reason:string};
type Mutation = {commit:string; task:GitTask};

export class BoardGitError extends Error {
  status: number;
  constructor(message: string, status=400) {super(message);this.status=status;}
}

// A broken/missing git executable must never select JSON for a Git checkout.
export function isGitProject(root: string): boolean {
  let cursor = path.resolve(root);
  while (true) {
    if (fs.existsSync(path.join(cursor, '.git'))) return true;
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  try {
    execFileSync('git', ['-C',root,'rev-parse','--show-toplevel'], {stdio:'pipe'});
    return true;
  } catch (error: any) {
    if (error.code === 'ENOENT') throw new BoardGitError('Git executable unavailable',503);
    return false;
  }
}

function text(value: unknown, name: string): string {
  if (typeof value !== 'string' || !value.trim() || /[\r\n\0]/.test(value)) {
    throw new BoardGitError(`Invalid ${name}: nonempty single-line string required`);
  }
  return value;
}

function identifier(value: unknown): string {
  const id = text(value,'task_id');
  if (!/^TASK-\d{3,}$/.test(id)) throw new BoardGitError('Invalid task_id');
  return id;
}

function project(data: Record<string,any>): GitTask {
  return {...data,id:data.task_id,task_id:data.task_id,status:data.status,contractId:data.contract,sourceRef:'main'};
}

export class GitTaskStore {
  readonly root: string;
  constructor(projectDir: string) {this.root = path.resolve(projectDir);}

  private async command(args: string[], binary=process.env.KDD_PYTHON || 'python'): Promise<string> {
    const env: NodeJS.ProcessEnv = {...process.env,PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1'};
    delete env.NODE_TEST_CONTEXT;
    delete env.KDD_BOARD_TOKEN;
    try {
      const {stdout} = await execute(binary,args,{cwd:this.root,encoding:'utf8',timeout:180_000,
        maxBuffer:8*1024*1024,windowsHide:true,env});
      return stdout;
    } catch (error: any) {
      const message = String(error.stderr || error.message || 'Coordinator failed').trim();
      const status = /TASK_MISSING/.test(message) ? 404 : binary === 'git' || /TASK_(MAIN|DIRTY|LOCK|RACE|BRANCH|EVIDENCE|APPROVAL|CONTRACT|DEPENDENCIES|GIT|TESTS|INTEGRATION)/.test(message) ? 409 : 400;
      throw new BoardGitError(message, error.killed || typeof error.code !== 'number' ? 503 : status);
    }
  }

  private async query(args: string[]): Promise<any> {
    return JSON.parse(await this.command([cli,'--repo-root',this.root,...args,'--json']));
  }

  private async git(...args: string[]) {return (await this.command(['--literal-pathspecs','-C',this.root,...args],'git')).trim();}

  private async stable<T>(read: () => Promise<T>): Promise<T> {
    for (let attempt=0; attempt<2; attempt++) {
      const before = await this.git('rev-parse','--verify','main^{commit}');
      const result = await read();
      if (before === await this.git('rev-parse','--verify','main^{commit}')) return result;
    }
    throw new BoardGitError('TASK_RACE: main changed during read; refresh',409);
  }

  async list(status?: string): Promise<GitTask[]> {
    if (status !== undefined && !Object.hasOwn(transitions,status)) throw new BoardGitError('Invalid status');
    return this.stable(async () => {
      const tasks = (await this.query(['list']) as any[]).map(project);
      return status ? tasks.filter(t => t.status === status) : tasks;
    });
  }

  async get(id: string): Promise<GitTask & {journal:JournalEntry[]}> {
    identifier(id);
    return this.stable(async () => ({...project(await this.query(['show',id])),journal:await this.query(['history',id])}));
  }

  async history(id: string): Promise<JournalEntry[]> {
    identifier(id);
    return this.stable(() => this.query(['history',id]));
  }

  async contracts(): Promise<{id:string; title:string}[]> {
    return this.stable(async () => {
      const files = await this.git('ls-tree','-r','--name-only','-z','main','--','knowledge/contracts');
      return files.split('\0').filter(p=>p.endsWith('.md')).map(id=>({id,title:path.posix.basename(id)}));
    });
  }

  async create(input: Record<string,any>): Promise<Mutation> {
    const args = ['create',identifier(input.task_id),'--title',text(input.title,'title'),
      '--description',text(input.description,'description'),'--contract',text(input.contract,'contract')];
    if (input.depends_on !== undefined && !Array.isArray(input.depends_on)) throw new BoardGitError('Invalid depends_on');
    for (const dependency of input.depends_on || []) args.push('--depends-on',identifier(dependency));
    const result = await this.query(args);
    return {commit:result.commit,task:project(result.task)};
  }

  async transition(id: string, input: Record<string,any>): Promise<Mutation> {
    const task = await this.get(identifier(id));
    const operation = transitions[task.status]?.[input.status];
    if (!operation) throw new BoardGitError(`Invalid transition: ${task.status} -> ${input.status}`);
    const args = [operation,id];
    if (operation === 'ready') {
      const approved = text(input.approved_ref,'approved_ref');
      if (!/^[a-f0-9]{40}$/.test(approved)) throw new BoardGitError('Explicit approved_ref SHA required');
      args.push('--approved-ref',approved);
    }
    if (operation === 'start') args.push('--assignee',text(input.assignee,'assignee'));
    if (operation === 'block' || operation === 'resume') args.push('--reason',text(input.reason,'reason'));
    const result = await this.query(args);
    return {commit:result.commit,task:project(result.task)};
  }
}
