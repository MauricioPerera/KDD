import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';

export function tempOutsideGit(prefix: string): string {
  const fallback = process.platform === 'win32'
    ? path.join(process.env.SystemRoot || 'C:\\Windows', 'Temp') : '/tmp';
  for (const parent of [os.tmpdir(), fallback, path.parse(os.tmpdir()).root]) {
    let cursor = path.resolve(parent), insideGit = false;
    while (true) {
      if (fs.existsSync(path.join(cursor, '.git'))) { insideGit = true; break; }
      const next = path.dirname(cursor);
      if (next === cursor) break;
      cursor = next;
    }
    if (!insideGit) {
      try { return fs.mkdtempSync(path.join(parent, prefix)); } catch { /* try next parent */ }
    }
  }
  throw new Error('No writable temporary directory outside Git');
}

export function projectFixture(root: string) {
  fs.mkdirSync(path.join(root, 'src'), {recursive: true});
  fs.mkdirSync(path.join(root, 'knowledge/contracts'), {recursive: true});
  fs.writeFileSync(path.join(root, 'src/hello.py'), 'def hello(name): return "Hello, " + name\n');
  const oracle = "const {test}=require('node:test'); const assert=require('node:assert/strict'); const fs=require('node:fs'); test('project cwd',()=>assert.ok(fs.readFileSync('src/hello.py','utf8').includes('def hello'))); console.log(process.env.AUDIT_CANARY || 'no secret');";
  fs.writeFileSync(path.join(root, 'oracle.cjs'), oracle);
  const contract = `---
type: 'Task Contract'
title: 'Fixture contract'
description: 'Verify project execution.'
tags: ['test']
task: fixture
intent: 'Verify the project target.'
target: src/hello.py
signature: 'def hello(name):'
test_command: 'node --test --test-reporter=tap oracle.cjs'
budget:
  cyclomatic_max: 2
  nesting_max: 1
tests: oracle.cjs
tests_sha256: '${crypto.createHash('sha256').update(oracle).digest('hex')}'
touch_only: ['src/hello.py']
deps_allowed: []
forbids: ['network']
---
## Intent
Verify project execution.
## Interface
hello(name)
## Invariants
- Read the expected target.
## Examples
- A present target passes.
- A missing target fails.
## Do / Don't
- DO run in the selected project.
## Tests
Use the sealed oracle.
## Constraints
- PARAR y reportar si el target no existe.
`;
  fs.writeFileSync(path.join(root, 'knowledge/contracts/sample_task.md'), contract);
}

