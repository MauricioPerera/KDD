import { exec } from 'node:child_process';
import type { TaskTestReport } from './types.ts';

export function executeTaskTest(command: string, cwd: string): Promise<TaskTestReport> {
  const start = performance.now();
  return new Promise((resolve) => {
    exec(command, { cwd, timeout: 30000 }, (error, stdout, stderr) => {
      const durationMs = performance.now() - start;
      const output = (stdout + '\n' + stderr).trim();
      const success = !error;

      let passed = 0;
      let failed = 0;

      const passMatch = output.match(/ℹ\s+pass\s+(\d+)/);
      if (passMatch) {
        passed = Number(passMatch[1]);
      } else {
        const checkmarks = (output.match(/✔/g) || []).length;
        passed = checkmarks;
      }

      const failMatch = output.match(/ℹ\s+fail\s+(\d+)/);
      if (failMatch) {
        failed = Number(failMatch[1]);
      } else {
        const crosses = (output.match(/✖/g) || []).length;
        failed = crosses;
      }

      if (success && passed === 0 && failed === 0) {
        passed = 1;
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
