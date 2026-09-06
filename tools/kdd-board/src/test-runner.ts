import { exec } from 'node:child_process';
import type { TaskTestReport } from './types.ts';

export function executeTaskTest(command: string, cwd: string, secrets: Record<string, string> = {}): Promise<TaskTestReport> {
  const start = performance.now();
  const env = { ...process.env, ...secrets };
  delete env.NODE_TEST_CONTEXT;
  delete env.KDD_BOARD_TOKEN;
  return new Promise((resolve) => {
    exec(command, { cwd, timeout: 30000, env }, (error, stdout, stderr) => {
      const durationMs = performance.now() - start;
      let output = (stdout + '\n' + stderr).trim();
      for (const value of Object.values(secrets).filter(Boolean).sort((a, b) => b.length - a.length)) {
        output = output.split(value).join('[REDACTED]');
      }
      const success = !error;

      let passed = 0;
      let failed = 0;

      const passMatch = output.match(/(?:ℹ|#)\s+pass\s+(\d+)/);
      if (passMatch) {
        passed = Number(passMatch[1]);
      }

      const failMatch = output.match(/(?:ℹ|#)\s+fail\s+(\d+)/);
      if (failMatch) {
        failed = Number(failMatch[1]);
      }

      const unittest = output.match(/Ran (\d+) tests? in/);
      if (unittest && /^OK(?: \(|$)/m.test(output) && success) {
        const skipped = Number(output.match(/skipped=(\d+)/)?.[1] || 0);
        const expectedFailures = Number(output.match(/expected failures=(\d+)/)?.[1] || 0);
        passed = Math.max(0, Number(unittest[1]) - skipped - expectedFailures);
      }

      resolve({
        lastRun: new Date().toISOString(),
        success,
        durationMs,
        passedTests: passed,
        failedTests: failed,
        output,
      });
    });
  });
}
