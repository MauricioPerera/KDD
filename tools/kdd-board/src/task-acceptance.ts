import {randomUUID} from 'node:crypto';
import {BoardGitError,taskError,type GitTaskStore,type AcceptanceClosure,type AcceptanceSnapshot} from './git-task-store.ts';

type Running = {
  state: 'running';
  run_id: string;
  task_id: string;
  tested_commit: string;
  approved_ref: string;
  observed_commit: string;
  requires_acceptance: true;
};
type Failed = Omit<Running,'state'> & {state:'failed'; error_code:string};
type Done = Omit<Running,'state'> & AcceptanceClosure & {state:'done'};
type Start = {tested_commit:string; retry?:boolean};

function stale() {
  return new BoardGitError('TASK_RACE: main changed; refresh before retrying',409);
}

export class TaskAcceptance {
  private active?: Running;
  private readonly outcomes = new Map<string,Failed | Done>();

  private readonly store: GitTaskStore;

  constructor(store: GitTaskStore) {this.store = store;}

  async status(id: string) {
    while (this.active?.task_id !== id) {
      const previous = this.outcomes.get(id);
      const snapshot = await this.store.snapshotAcceptance(id);
      if (this.active?.task_id === id) return this.active;
      if (previous === this.outcomes.get(id) || snapshot.closure) return this.view(id,snapshot);
    }
    return this.active;
  }

  async start(id: string, request: Start): Promise<Running | Failed | Done> {
    const ongoing = this.runningRequest(id,request.tested_commit);
    if (ongoing) return ongoing;
    const previous = this.outcomes.get(id);
    const snapshot = await this.store.snapshotAcceptance(id);
    const started = this.runningRequest(id,request.tested_commit);
    if (started) return started;
    if (snapshot.closure) {
      if (snapshot.closure.tested_commit !== request.tested_commit) throw stale();
      return this.done(id,snapshot.observed_commit,snapshot.closure);
    }

    const latest = this.outcomes.get(id);
    if (snapshot.observed_commit !== request.tested_commit || latest?.state === 'done') throw stale();
    if (snapshot.status !== 'in_progress' || !snapshot.requires_acceptance) {
      throw new BoardGitError('TASK_TRANSITION: approved acceptance is required for an in-progress task',409);
    }
    if (latest?.state === 'failed' && latest.tested_commit === request.tested_commit &&
        (!request.retry || latest !== previous)) return latest;
    const run: Running = {state:'running', run_id:randomUUID(), task_id:id,
      tested_commit:request.tested_commit, approved_ref:snapshot.approved_ref,
      observed_commit:snapshot.observed_commit, requires_acceptance:true};
    this.active = run;
    void this.finish(run);
    return run;
  }

  private runningRequest(id: string, testedCommit: string) {
    const running = this.active;
    if (!running) return;
    if (running.task_id !== id) throw new BoardGitError('TASK_LOCK: another task is verifying acceptance',409);
    if (running.tested_commit !== testedCommit) throw stale();
    return running;
  }

  private done(id: string, observedCommit: string, closure: AcceptanceClosure): Done {
    const previous = this.outcomes.get(id);
    const attempt = previous?.state === 'done' && previous.closed_commit === closure.closed_commit ? previous.run_id
      : closure.closed_commit;
    return {...closure, state:'done', task_id:id, run_id:attempt, observed_commit:observedCommit,
      requires_acceptance:true};
  }

  private view(id: string, snapshot: AcceptanceSnapshot) {
    if (snapshot.closure) return this.done(id,snapshot.observed_commit,snapshot.closure);
    const previous = this.outcomes.get(id);
    if (snapshot.requires_acceptance && previous?.state === 'failed') {
      return {...previous, observed_commit:snapshot.observed_commit};
    }
    return {state:'idle', task_id:id, tested_commit:snapshot.observed_commit, approved_ref:snapshot.approved_ref,
      observed_commit:snapshot.observed_commit, requires_acceptance:snapshot.requires_acceptance};
  }

  private async finish(run: Running): Promise<void> {
    try {
      await this.store.finishAcceptance(run.task_id,run.tested_commit);
      const {closure, observed_commit} = await this.store.snapshotAcceptance(run.task_id);
      if (closure?.tested_commit !== run.tested_commit || closure.approved_ref !== run.approved_ref) {
        throw new BoardGitError('TASK_EVIDENCE_INVALID: acceptance receipt differs from the request',409);
      }
      this.outcomes.set(run.task_id,{...run,...closure,state:'done',observed_commit});
    } catch (error) {
      this.outcomes.set(run.task_id,{...run,state:'failed',error_code:taskError(error).code});
    } finally {
      this.active = undefined;
    }
  }
}
