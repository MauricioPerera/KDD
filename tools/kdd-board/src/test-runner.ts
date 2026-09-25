import { exec, execFile } from 'node:child_process';
import path from 'node:path';
import type { TaskTestReport } from './types.ts';

function verifiedInvocation(command: string, oracle: string): {file: string; args: string[]; runner: 'node' | 'unittest'} | null {
  const tokens = command.match(/(?:"[^"]*"|'[^']*'|\S+)/g)?.map(t => t.replace(/^(?:"([^"]*)"|'([^']*)')$/, (_m, double, single) => double ?? single));
  if (!tokens || tokens.some(t => /[;&|<>`$]/.test(t))) return null;
  const relative = oracle.replace(/\\/g, '/').replace(/^\.\//, '');
  const matchesOracle = (value: string) => value.replace(/\\/g, '/').replace(/^\.\//, '') === relative;
  if (tokens[0] === 'node' && tokens[1] === '--test') {
    const rest = tokens.slice(2);
    const args = rest[0] === '--test-reporter=tap' ? rest.slice(1) : rest;
    if (args.length === 1 && matchesOracle(args[0])) {
      return {file: 'node', args: ['--test', '--test-reporter=tap', args[0]], runner: 'node'};
    }
  }
  if (/^python(?:3(?:\.\d+)?)?$/.test(tokens[0]) && tokens[1] === '-m' && tokens[2] === 'unittest' && tokens.length === 4) {
    const module = relative.replace(/\.py$/, '').replace(/\//g, '.');
    if (matchesOracle(tokens[3]) || tokens[3] === module) {
      return {file: tokens[0], args: tokens.slice(1), runner: 'unittest'};
    }
  }
  return null;
}

function testTotals(runner: 'node' | 'unittest' | null, stdout: string, stderr: string, oracle?: string): {passed: number; failed: number} {
  if (runner === 'node') {
    const summary = stdout.trim().match(/(?:^|\n)# tests (\d+)\r?\n# suites \d+\r?\n# pass (\d+)\r?\n# fail (\d+)\r?\n# cancelled (\d+)\r?\n# skipped (\d+)\r?\n# todo (\d+)\r?\n# duration_ms [^\r\n]+$/);
    if (summary) {
      const [tests, passed, failed, cancelled, skipped, todo] = summary.slice(1, 7).map(Number);
      const subtests = [...stdout.matchAll(/^# Subtest: ([^\r\n]+)$/gm)].map(match => match[1]);
      const namedTest = subtests.some(name => !oracle || (name !== oracle && name !== path.basename(oracle)));
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

export function executeTaskTest(command: string, cwd: string, secrets: Record<string, string> = {}, oracle?: string): Promise<TaskTestReport> {
  const start = performance.now();
  const env = { ...process.env, ...secrets };
  delete env.NODE_TEST_CONTEXT;
  delete env.KDD_BOARD_TOKEN;
  const invocation = oracle ? verifiedInvocation(command, path.relative(cwd, oracle)) : null;
  if (oracle && !invocation) return Promise.resolve({
    lastRun: new Date().toISOString(), success: false, durationMs: 0,
    passedTests: 0, failedTests: 0, output: 'The test command must run the sealed oracle with node --test or python -m unittest.',
  });
  return new Promise((resolve) => {
    const callback = (error: Error | null, stdout: string, stderr: string) => {
      const durationMs = performance.now() - start;
      const runner = invocation?.runner ?? (command.startsWith('node --test ') ? 'node' : /^python(?:3(?:\.\d+)?)? -m unittest /.test(command) ? 'unittest' : null);
      const totals = testTotals(runner, stdout, stderr, oracle);
      let output = (stdout + '\n' + stderr).trim();
      for (const value of Object.values(secrets).filter(Boolean).sort((a, b) => b.length - a.length)) {
        output = output.split(value).join('[REDACTED]');
      }
      const success = !error;

      resolve({
        lastRun: new Date().toISOString(),
        success,
        durationMs,
        passedTests: totals.passed,
        failedTests: totals.failed,
        verifiedOracle: Boolean(invocation && success && totals.passed > 0 && totals.failed === 0),
        output,
      });
    };
    if (invocation) execFile(invocation.file, invocation.args, {cwd, timeout: 30000, env}, callback);
    else exec(command, { cwd, timeout: 30000, env }, callback);
  });
}
