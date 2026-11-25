import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {createHash} from 'node:crypto';
import {constants, type BigIntStats} from 'node:fs';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';
import {BoardGitError} from './git-task-store.ts';

const execute = promisify(execFile);
const boardRepo = fileURLToPath(new URL('../../..', import.meta.url));
const verifier = fileURLToPath(new URL('../browser-pilot/run.mjs', import.meta.url));
const pinFormat = /^([a-f0-9]{40}):([a-f0-9]{64})$/;
const commitFormat = /^[a-f0-9]{40}$/;
const maxBytes = 4 * 1024 * 1024;
const digest = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

function sameFile(a: BigIntStats, b: BigIntStats) {
  return a.dev === b.dev && a.ino === b.ino && a.size === b.size &&
    a.mtimeNs === b.mtimeNs && a.ctimeNs === b.ctimeNs;
}

async function readRegular(file: string): Promise<Buffer> {
  const before = await fs.lstat(file, {bigint: true});
  assert.ok(before.isFile() && before.nlink === 1n && before.size <= BigInt(maxBytes));
  const flags = constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0);
  const handle = await fs.open(file, flags);
  try {
    const opened = await handle.stat({bigint: true});
    assert.ok(opened.isFile() && sameFile(opened, before));
    const bytes = Buffer.alloc(Number(opened.size));
    const read = await handle.read(bytes, 0, bytes.length, 0);
    assert.equal(read.bytesRead, bytes.length);
    assert.ok(sameFile(opened, await handle.stat({bigint: true})));
    return bytes;
  } finally {
    await handle.close();
  }
}

function localOptions() {
  const allowed = /^(PATH|PATHEXT|HOME|USERPROFILE|SYSTEMROOT|WINDIR|SYSTEMDRIVE|COMSPEC|LOCALAPPDATA|APPDATA|TMP|TEMP|TMPDIR|LANG|LC_ALL)$/i;
  const env = Object.fromEntries(Object.entries(process.env).filter(([name])=>allowed.test(name)));
  return {cwd:boardRepo, timeout:10000, maxBuffer:65536, windowsHide:true, env:{...env,
    GIT_NO_REPLACE_OBJECTS:'1', GIT_NO_LAZY_FETCH:'1', GIT_OPTIONAL_LOCKS:'0', GIT_TERMINAL_PROMPT:'0',
    GIT_CONFIG_NOSYSTEM:'1', GIT_CONFIG_GLOBAL:process.platform==='win32'?'NUL':'/dev/null'}};
}

async function verifyCommitPair(checkout: string, approved: unknown) {
  assert.ok(typeof approved === 'string' && commitFormat.test(approved));
  const options = localOptions();
  const objects = await Promise.all([checkout, approved].map(ref=>
    execute('git',['cat-file','-t',ref],options)));
  for (const {stdout} of objects) assert.equal(stdout.trim(),'commit');
  await execute('git',['merge-base','--is-ancestor',approved,checkout],options);
}

async function verifyReport(bytes: Buffer, exitCode: number) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(),'kdd-board-evidence-'));
  try {
    const file = path.join(directory,'report.json');
    await fs.writeFile(file,bytes,{flag:'wx',mode:0o600});
    const {stdout} = await execute(process.execPath,
      [verifier,'--verify-report','--report',file,'--exit-code',String(exitCode)],localOptions());
    const result = JSON.parse(stdout);
    assert.equal(result.ok,true);
    assert.ok((await readRegular(file)).equals(bytes));
    return result;
  } finally {
    await fs.rm(directory,{force:true,recursive:true,maxRetries:4,retryDelay:100});
  }
}

function projectCase(result: any) {
  const attempt = result.attempts[0];
  assert.deepEqual(attempt.artifacts,[]);
  assert.ok(Array.isArray(attempt.steps));
  for (const step of attempt.steps) assert.deepEqual(step.artifacts,[]);
  return {id:result.testId,status:result.status,attempt:attempt.index,
    duration_ms:attempt.durationMs,artifacts:[]};
}

async function readBrowserEvidence(directory: string, pin: string) {
  const parts = pin.match(pinFormat);
  assert.ok(parts && path.isAbsolute(directory));
  const [,checkout,receiptHash] = parts;
  const direct = path.resolve(directory);
  const before = await fs.lstat(direct,{bigint:true});
  assert.ok(before.isDirectory());
  assert.equal(path.relative(direct,await fs.realpath(direct)),'');
  const receiptBytes = await readRegular(path.join(direct,'receipt.json'));
  assert.equal(digest(receiptBytes),receiptHash);
  const receipt = JSON.parse(receiptBytes.toString('utf8'));
  assert.equal(receipt.checkout,checkout);
  assert.equal(receipt.exit_code,0);
  const bytes = await readRegular(path.join(direct,'report.json'));
  assert.ok(sameFile(before, await fs.lstat(direct,{bigint:true})));
  const reportHash = digest(bytes);
  assert.equal(reportHash,receipt.report_sha256);
  await verifyCommitPair(checkout,receipt.approved_ref);
  const verified = await verifyReport(bytes,receipt.exit_code);
  assert.equal(receipt.run_id,verified.run_id);
  assert.deepEqual(receipt.ids,verified.ids);
  const {run} = JSON.parse(bytes.toString('utf8'));
  return {status:'available',source:'local_bundle',checkout,approved_ref:receipt.approved_ref,
    run_id:verified.run_id,receipt_sha256:receiptHash,report_sha256:reportHash,
    cases:run.results.map(projectCase)};
}

export async function browserEvidence() {
  const directory = process.env.KDD_BOARD_BROWSER_EVIDENCE_DIR;
  const pin = process.env.KDD_BOARD_BROWSER_EVIDENCE_PIN;
  if (!directory && !pin) return {status:'unavailable'};
  try {
    assert.ok(directory && pin);
    return await readBrowserEvidence(directory,pin);
  } catch {
    throw new BoardGitError('No se pudo cotejar la evidencia de Chromium.',409,'BROWSER_EVIDENCE_INVALID');
  }
}
