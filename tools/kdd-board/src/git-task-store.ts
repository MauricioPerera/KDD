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
  code: string;
  details: Record<string,unknown>;
  constructor(message: string, status=400, code?:string, details:Record<string,unknown>={}) {
    super(message);this.status=status;this.details=details;
    this.code=code || message.match(/\bTASK_[A-Z_]+(?=:)/)?.[0] ||
      (message.startsWith('Invalid transition') ? 'TASK_TRANSITION' : 'TASK_REQUEST');
  }
}

export function taskError(error:unknown) {
  if (!(error instanceof BoardGitError)) {
    const invalid=error instanceof SyntaxError || (error as any)?.name === 'ZodError';
    return {code:invalid?'TASK_INPUT':'TASK_UNAVAILABLE',message:invalid?'Invalid task request':'Git coordinator unavailable',
      status:invalid?400:503,details:{} as Record<string,unknown>};
  }
  const details:Record<string,unknown>={};
  if (typeof error.details.task_id === 'string' && /^TASK-\d{3,}$/.test(error.details.task_id)) details.task_id=error.details.task_id;
  if (Array.isArray(error.details.pending_dependencies)) {
    details.pending_dependencies=error.details.pending_dependencies.filter(id=>typeof id==='string' && /^TASK-\d{3,}$/.test(id));
  }
  return {code:error.code,message:error.message,status:error.status,details};
}

const coordinatorReasons:Record<string,string>={
  TASK_DEPENDENCIES:'prerequisites are not done',TASK_MISSING:'task not found',
  TASK_MAIN:'run mutations on main',TASK_DIRTY:'commit or preserve local changes before retrying',
  TASK_LOCK:'another coordinator owns the task lock',TASK_RACE:'main changed; refresh before retrying',
  TASK_BRANCH:'task branch is missing, rewritten or already exists',TASK_EVIDENCE:'task evidence is invalid',
  TASK_APPROVAL:'an explicit approved ancestor and unchanged oracle are required',TASK_CONTRACT:'contract is invalid',
  TASK_GIT:'Git operation failed',TASK_TESTS:'contract tests failed or could not complete',
  TASK_PERIMETER:'implementation exceeds the approved scope',
  TASK_INTEGRATION:'integrate the preserved implementation first',TASK_TRANSITION:'transition is not permitted',
  TASK_ID:'expected TASK-NNN',TASK_EXISTS:'task already exists',TASK_RUNNER:'unsupported oracle runner',
  TASK_ORACLE:'oracle seal is invalid',TASK_PATH:'invalid task path',TASK_OPERATION:'unknown task operation',
};

// A broken/missing git executable must never select JSON for a Git checkout.
export function isGitProject(root: string): boolean {
  const selected = fs.realpathSync(root);
  const rejectNested = () => {
    throw new BoardGitError('TASK_PROJECT_ROOT: select the Git repository root or initialize Git in this project',409);
  };
  let cursor = selected;
  while (true) {
    if (fs.existsSync(path.join(cursor, '.git'))) {
      if (path.relative(selected, cursor)) rejectNested();
      return true;
    }
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  let top: string;
  try {
    top = execFileSync('git', ['-C',root,'rev-parse','--show-toplevel'], {encoding:'utf8',stdio:'pipe'}).trim();
  } catch (error: any) {
    if (error.code === 'ENOENT') throw new BoardGitError('Git executable unavailable',503);
    return false;
  }
  if (path.relative(selected, fs.realpathSync(top))) rejectNested();
  return true;
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
      const code = message.match(/\bTASK_[A-Z_]+(?=:)/)?.[0] || (binary === 'git' ? 'TASK_GIT' : 'TASK_UNAVAILABLE');
      const status = code === 'TASK_MISSING' ? 404 : binary === 'git' || /TASK_(MAIN|DIRTY|LOCK|RACE|BRANCH|EVIDENCE|APPROVAL|CONTRACT|DEPENDENCIES|GIT|TESTS|INTEGRATION|PERIMETER)/.test(code) ? 409 : 400;
      if (error.killed || typeof error.code !== 'number' || !coordinatorReasons[code]) {
        throw new BoardGitError('Git coordinator unavailable',503,'TASK_UNAVAILABLE');
      }
      throw new BoardGitError(code+': '+coordinatorReasons[code],status,code);
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
      if (!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(approved)) throw new BoardGitError('Explicit approved_ref SHA required');
      args.push('--approved-ref',approved);
    }
    if (operation === 'start') args.push('--assignee',text(input.assignee,'assignee'));
    if (operation === 'block' || operation === 'resume') args.push('--reason',text(input.reason,'reason'));
    try {
      const result = await this.query(args);
      return {commit:result.commit,task:project(result.task)};
    } catch (error) {
      if (error instanceof BoardGitError) {
        error.details.task_id=id;
        if (error.code === 'TASK_DEPENDENCIES') {
          const current=await this.list();
          const done=new Set(current.filter(item=>item.status==='done').map(item=>item.task_id));
          error.details.pending_dependencies=(task.depends_on || []).filter((dependency:string)=>!done.has(dependency));
        }
      }
      throw error;
    }
  }
}
