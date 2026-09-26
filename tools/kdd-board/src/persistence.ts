import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export function readVersion(file: string): string | null {
  try { return fs.readFileSync(file, 'utf8'); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null; throw error; }
}

/** Cooperating writers serialize commits; stale snapshots fail without losing data.
 * A crash can leave the lock behind: recovery must verify that no writer is alive.
 */
export function writeVersion(file: string, expected: string | null, content: string): void {
  fs.mkdirSync(path.dirname(file), {recursive: true});
  const lock = `${file}.lock`;
  const fd = fs.openSync(lock, 'wx', 0o600);
  const temporary = `${file}.${crypto.randomUUID()}.tmp`;
  try {
    if (readVersion(file) !== expected) throw new Error('Storage conflict: reload before retrying');
    fs.writeFileSync(temporary, content, {encoding: 'utf8', mode: 0o600, flag: 'wx'});
    fs.renameSync(temporary, file);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    fs.closeSync(fd);
    fs.unlinkSync(lock);
  }
}
