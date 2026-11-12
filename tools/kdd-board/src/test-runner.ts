import { exec, execFile } from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import type { TaskTestReport } from './types.ts';

type OracleRunner = NonNullable<TaskTestReport['oracleRunner']>;
type Invocation = {interpreter: string; command: string; runner: OracleRunner};

function redact(output: string, secrets: Record<string, string>): string {
  for (const value of Object.values(secrets).filter(Boolean).sort((a, b) => b.length - a.length)) {
    output = output.split(value).join('[REDACTED]');
  }
  return output;
}

function tokensOf(command: string): string[] {
  return command.match(/(?:"[^"]*"|'[^']*'|\S+)/g)
    ?.map(token => token.replace(/^(?:"([^"]*)"|'([^']*)')$/, (_match, double, single) => double ?? single)) ?? [];
}

function runnerFor(tokens: string[]): OracleRunner | undefined {
  if (tokens[0] === 'node' && tokens[1] === '--test') return 'node-test-reporter-v1';
  if (/^python(?:3(?:\.\d+)?)?$/.test(tokens[0]) && tokens[1] === '-m' && tokens[2] === 'unittest') {
    return 'python-unittest-recorder-v1';
  }
}

export function oracleRunnerForCommand(command: string): OracleRunner | undefined {
  return runnerFor(tokensOf(command));
}

function verifiedInvocation(command: string, oracle: string): Invocation | null {
  const tokens = tokensOf(command);
  if (tokens.some(token => /[;&|<>\x60$]/.test(token))) return null;
  const relative = oracle.replace(/\\/g, '/').replace(/^\.\//, '');
  const matchesOracle = (value: string) => value.replace(/\\/g, '/').replace(/^\.\//, '') === relative;
  const runner = runnerFor(tokens);
  if (runner === 'node-test-reporter-v1') {
    const first = tokens[2] === '--test-reporter=tap' ? 3 : 2;
    if (tokens.length === first + 1 && matchesOracle(tokens[first])) {
      return {interpreter: 'python', command: 'node --test ' + JSON.stringify(relative), runner};
    }
  }
  if (runner === 'python-unittest-recorder-v1' && tokens.length === 4) {
    const module = relative.replace(/\.py$/, '').replace(/\//g, '.');
    if (matchesOracle(tokens[3]) || tokens[3] === module) {
      return {interpreter: tokens[0], command, runner};
    }
  }
  return null;
}

function executeVerifiedOracle(invocation: Invocation, cwd: string, env: NodeJS.ProcessEnv,
                               secrets: Record<string, string>, oracle: string, timeoutMs: number): Promise<TaskTestReport> {
  const start = performance.now();
  const bridge = fileURLToPath(new URL('../../../scripts/board_oracle_bridge.py', import.meta.url));
  const name = path.relative(cwd, oracle).replace(/\\/g, '/');
  const runner = invocation.runner === 'node-test-reporter-v1' ? 'node-test' : 'python-unittest';
  const metadata = {tests: name, oracle_files: [name], test_runner: runner, test_command: invocation.command};
  return new Promise(resolve => {
    execFile(invocation.interpreter, ['-I', '-B', bridge, JSON.stringify(metadata), cwd, String(timeoutMs / 1000)],
      {cwd, env, timeout: timeoutMs + 5000}, (error, stdout, stderr) => {
        let outcome: any;
        try { outcome = JSON.parse(stdout); } catch { outcome = undefined; }
        const verified = Boolean(!error && outcome?.ok === true && Number.isInteger(outcome.executed_tests) && outcome.executed_tests > 0);
        const timedOut = outcome?.error === 'timeout' || Boolean(error?.killed);
        const unverifiedNodeExit = !error && runner === 'node-test' && outcome?.process_exit_code === 0;
        const status = timedOut ? 'TIMEOUT' : verified ? 'PASS' : unverifiedNodeExit ? 'SKIP' : 'FAIL';
        const output = outcome ? [outcome.stdout, outcome.stderr, outcome.error].filter(Boolean).join('\n')
          : stderr || error?.message || 'Missing runner evidence';
        resolve({lastRun: new Date().toISOString(), durationMs: performance.now() - start,
          success: verified || unverifiedNodeExit, status,
          verifiedOracle: verified, oracleRunner: verified ? invocation.runner : undefined,
          passedTests: verified ? outcome.executed_tests : 0, failedTests: 0, output: redact(output, secrets)});
      });
  });
}

function testTotals(runner: 'node' | 'unittest' | null, stdout: string, stderr: string): {passed: number; failed: number} {
  if (runner === 'node') {
    const summary = stdout.trim().match(/(?:^|\n)# tests (\d+)\r?\n# suites \d+\r?\n# pass (\d+)\r?\n# fail (\d+)\r?\n# cancelled (\d+)\r?\n# skipped (\d+)\r?\n# todo (\d+)\r?\n# duration_ms [^\r\n]+$/);
    if (summary) {
      const [tests, passed, failed, cancelled, skipped, todo] = summary.slice(1, 7).map(Number);
      const namedTest = /^# Subtest: [^\r\n]+$/m.test(stdout);
      if (tests > 0 && namedTest && passed + failed + cancelled + skipped + todo === tests) return {passed, failed};
    }
  }
  if (runner === 'unittest') {
    const summary = stderr.trim().match(/(?:^|\n)Ran (\d+) tests? in [^\r\n]+\r?\n\r?\nOK(?: \(([^\r\n]*)\))?$/);
    if (summary) {
      const skipped = Number(summary[2]?.match(/skipped=(\d+)/)?.[1] || 0);
      const expected = Number(summary[2]?.match(/expected failures=(\d+)/)?.[1] || 0);
      return {passed: Math.max(0, Number(summary[1]) - skipped - expected), failed: 0};
    }
  }
  return {passed: 0, failed: 0};
}

export function executeTaskTest(command: string, cwd: string, secrets: Record<string, string> = {}, oracle?: string, timeoutMs = 30000): Promise<TaskTestReport> {
  const start = performance.now();
  const env = { ...process.env, ...secrets };
  delete env.NODE_TEST_CONTEXT;
  delete env.KDD_BOARD_TOKEN;
  if (oracle) {
    const invocation = verifiedInvocation(command, path.relative(cwd, oracle));
    if (invocation) return executeVerifiedOracle(invocation, cwd, env, secrets, oracle, timeoutMs);
    return Promise.resolve({
      lastRun: new Date().toISOString(), success: false, status: 'FAIL', durationMs: 0,
      passedTests: 0, failedTests: 0, output: 'The test command must run the sealed oracle with node --test or python -m unittest.',
    });
  }
  return new Promise(resolve => {
    exec(command, {cwd, timeout: timeoutMs, env}, (error, stdout, stderr) => {
      const runner = command.startsWith('node --test ') ? 'node'
        : /^python(?:3(?:\.\d+)?)? -m unittest /.test(command) ? 'unittest' : null;
      const totals = testTotals(runner, stdout, stderr);
      resolve({status: error?.killed ? 'TIMEOUT' : error ? 'FAIL' : 'SKIP',
        lastRun: new Date().toISOString(), durationMs: performance.now() - start,
        success: !error, passedTests: totals.passed, failedTests: totals.failed, verifiedOracle: false,
        output: redact((stdout + '\n' + stderr).trim(), secrets)});
    });
  });
}
