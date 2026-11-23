import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { executeTaskTest, oracleRunnerForCommand } from './test-runner.ts';
import type { TaskStore } from './task-store.ts';
import type { BlindVault } from './blind-vault.ts';
import type { Task, TaskTestReport } from './types.ts';

const execFileAsync = promisify(execFile);
const scripts = fileURLToPath(new URL('../../../scripts/', import.meta.url));

export function digest(file: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function projectFile(root: string, relative: string): string {
  const requested = path.resolve(root, relative);
  const file = fs.realpathSync(requested);
  const local = path.relative(root, file);
  if (local === '..' || local.startsWith('..' + path.sep) || path.isAbsolute(local)) {
    throw new Error('Contract path escapes project');
  }
  if (path.relative(requested, file) || !fs.statSync(file).isFile()) {
    throw new Error('Contract evidence must be a regular project file');
  }
  return file;
}

function projectEvidence(report: TaskTestReport, contractId: string, project: string): boolean {
  if (!report.cwd || !report.evidence || !report.evidenceFiles || !/^app-[\w.-]+\.md$/.test(contractId)) {
    return false;
  }
  const root = fs.realpathSync(project);
  if (path.relative(root, fs.realpathSync(report.cwd))) return false;
  const contract = projectFile(root, path.join('knowledge', 'contracts', contractId.slice(4)));
  const expected = new Set(report.evidenceFiles.map(file => projectFile(root, file)));
  const present = Object.keys(report.evidence);
  return expected.has(contract) && expected.size === present.length && present.every(file => expected.has(file));
}

export function evidenceCurrent(task: Task, projectRoot?: string): boolean {
  const r = task.testReport;
  if (!task.contractId || !r?.success || !r.verifiedOracle || !r.evidence || r.passedTests < 1 || r.failedTests !== 0) return false;
  const runner = oracleRunnerForCommand(r.command ?? '');
  if (!runner || r.oracleRunner !== runner) return false;
  if (!r.cwd || Object.keys(r.evidence).length < 2) return false;
  if (r.command !== task.testCommand || r.contractId !== task.contractId) return false;
  try {
    const project = projectRoot ?? (r.evidenceFiles && r.cwd);
    if (project && !projectEvidence(r, task.contractId, project)) return false;
    return Object.entries(r.evidence).every(([file, hash]) => digest(file) === hash);
  } catch { return false; }
}

export async function runTaskTests(store: TaskStore, vault: BlindVault, projectDir: string, id: string) {
  const task = store.getTask(id);
  if (!task) throw new Error('Task not found');
  if (!task.contractId || !/^app-[\w.-]+\.md$/.test(task.contractId)) throw new Error('A linked contract is required');
  const contractId = task.contractId;
  const root = fs.realpathSync(projectDir);
  const contract = projectFile(root, path.join('knowledge', 'contracts', contractId.slice(4)));
  const contractHash = digest(contract);
  // Use the canonical Python parser and validator, never a second YAML dialect.
  const program = [
    'import sys,json',
    'sys.path.insert(0,sys.argv[1])',
    'from validate_contracts import validate_file,parse_frontmatter',
    'from oracle_inventory import inventory_paths',
    "f=validate_file(sys.argv[2],repo_root=sys.argv[3])",
    "if any(x.level=='ERROR' for x in f): raise ValueError('Invalid contract: '+str(f))",
    "data=parse_frontmatter(open(sys.argv[2],encoding='utf-8').read())[0]",
    'data["oracle_files"]=inventory_paths(data)',
    'print(json.dumps(data))',
  ].join('\n');
  const parsed = await execFileAsync('python', ['-c', program, scripts, contract, root], {timeout: 30000});
  if (digest(contract) !== contractHash) throw new Error('Contract changed during validation');
  const data = JSON.parse(parsed.stdout);
  const command: string = data.test_command;
  const primary = projectFile(root, data.tests);
  const oracleFiles = data.oracle_files.map((relative: string) => projectFile(root, relative));
  const files = [...new Set<string>([contract, projectFile(root, data.target), ...oracleFiles])];
  const oracleText = fs.readFileSync(primary, 'utf8').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  if (crypto.createHash('sha256').update(oracleText).digest('hex') !== data.tests_sha256) {
    throw new Error('Oracle changed during validation');
  }
  const evidence = Object.fromEntries(files.map(file => [file, digest(file)]));
  store.setTestCommand(id, command);
  const report = await executeTaskTest(command, root, vault.environment(), {primary, files: oracleFiles});
  report.command = command;
  report.cwd = root;
  report.contractId = contractId;
  report.evidence = evidence;
  report.evidenceFiles = files.map(file => path.relative(root, file));
  if (files.some(file => {
    try { return digest(projectFile(root, file)) !== evidence[file]; } catch { return true; }
  })) {
    report.success = false;
    report.status = 'FAIL';
    report.output += '\nEvidence changed during execution; run again.';
  }
  const updated = store.recordTestReport(id, report);
  return {task: updated, report};
}
