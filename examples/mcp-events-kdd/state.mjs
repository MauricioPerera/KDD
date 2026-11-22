import assert from 'node:assert/strict';
import { existsSync, renameSync, writeFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

export function openRun(evidence, initial) {
  const database = evidence + '.sqlite';
  // Keep the owner lock separate so saving a checkpoint can commit while the lock is held.
  // SQLite releases the owner lock even if the process is killed.
  const owner = new DatabaseSync(evidence + '.owner.sqlite');
  let db;
  try {
    owner.exec('PRAGMA busy_timeout = 0; BEGIN IMMEDIATE;');
    if (initial) {
      assert.ok(!existsSync(database) && !existsSync(evidence), 'Use a new evidence path or resume explicitly.');
    } else assert.ok(existsSync(database), 'No saved run at this evidence path.');
    db = new DatabaseSync(database);
    db.exec(`
      PRAGMA synchronous = FULL;
      CREATE TABLE IF NOT EXISTS run_state (id INTEGER PRIMARY KEY CHECK (id = 1), document TEXT NOT NULL);
    `);
    const row = db.prepare('SELECT document FROM run_state WHERE id=1').get();
    assert.ok(initial || row, 'No checkpoint has been stored.');
    const report = initial ?? JSON.parse(row.document);
    assert.equal(report.schema, 2, 'Unsupported orchestrator state.');
    const put = db.prepare(`
      INSERT INTO run_state VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document
    `);
    function save() {
      const json = JSON.stringify(report, null, 2) + '\n';
      put.run(json);
      writeFileSync(evidence + '.tmp', json);
      renameSync(evidence + '.tmp', evidence);
    }
    save();
    return {
      report, save,
      close() {
        try { db.close(); } finally { owner.close(); }
      },
    };
  } catch (error) {
    try { db?.close(); } finally { owner.close(); }
    throw error;
  }
}
