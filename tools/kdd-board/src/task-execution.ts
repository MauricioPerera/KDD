import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { executeTaskTest } from './test-runner.ts';
import type { TaskStore } from './task-store.ts';
import type { BlindVault } from './blind-vault.ts';
import type { Task } from './types.ts';

const execFileAsync = promisify(execFile);
const scripts = fileURLToPath(new URL('../../../scripts/', import.meta.url));

export function digest(file: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

export function evidenceCurrent(task: Task): boolean {
  const r = task.testReport;
  if (!task.contractId || !r?.success || !r.verifiedOracle || !r.evidence || r.passedTests < 1 || r.failedTests !== 0) return false;
  if (!r.cwd || Object.keys(r.evidence).length < 2) return false;
  if (r.command !== task.testCommand || r.contractId !== task.contractId) return false;
  try { return Object.entries(r.evidence).every(([file, hash]) => digest(file) === hash); }
  catch { return false; }
}

export async function runTaskTests(store: TaskStore, vault: BlindVault, projectDir: string, id: string) {
  const task = store.getTask(id);
  if (!task) throw new Error('Task not found');
  if (!task.contractId || !/^app-[\w.-]+\.md$/.test(task.contractId)) throw new Error('A linked contract is required');
  const contractId = task.contractId;
  const root = fs.realpathSync(projectDir);
  const within = (rel: string) => {
    const file = fs.realpathSync(path.resolve(root, rel));
    const relative = path.relative(root, file);
    if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Contract path escapes project');
    return file;
  };
  const contract = within(path.join('knowledge', 'contracts', task.contractId.slice(4)));
  const contractHash = digest(contract);
  // Use the canonical Python parser and validator, never a second YAML dialect.
  const program = [
    'import sys,json',
    'sys.path.insert(0,sys.argv[1])',
    'from validate_contracts import validate_file,parse_frontmatter',
    "f=validate_file(sys.argv[2],repo_root=sys.argv[3])",
    "if any(x.level=='ERROR' for x in f): raise ValueError('Invalid contract: '+str(f))",
    "print(json.dumps(parse_frontmatter(open(sys.argv[2],encoding='utf-8').read())[0]))",
  ].join('\n');
  const parsed = await execFileAsync('python', ['-c', program, scripts, contract, root], {timeout: 30000});
  if (digest(contract) !== contractHash) throw new Error('Contract changed during validation');
  const data = JSON.parse(parsed.stdout);
  const command: string = data.test_command;
  const files = [contract, within(data.target), within(data.tests)];
  const oracleText = fs.readFileSync(files[2], 'utf8').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  if (crypto.createHash('sha256').update(oracleText).digest('hex') !== data.tests_sha256) {
    throw new Error('Oracle changed during validation');
  }
  const evidence = Object.fromEntries(files.map(file => [file, digest(file)]));
  store.setTestCommand(id, command);
  const report = await executeTaskTest(command, root, vault.environment(), files[2]);
  report.command = command;
  report.cwd = root;
  report.contractId = contractId;
  report.evidence = evidence;
  if (files.some(file => { try { return digest(file) !== evidence[file]; } catch { return true; } })) {
    report.success = false;
    report.output += '\nEvidence changed during execution; run again.';
  }
  const updated = store.recordTestReport(id, report);
  return {task: updated, report};
}
