"""Check the SSH worker's real files, read-only SQLite queries and launch evidence."""
import base64
from contextlib import closing, redirect_stdout
from io import StringIO
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import json
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import vps_review_ssh as ssh


REQUEST = '714aa433-b81b-5065-86f1-c990d571ac97'
EPOCH = 'e' * 64
IDENTITY = {'runId': 'run_00000000-0000-4000-8000-000000000001',
            'conversationId': '10000000-0000-4000-8000-000000000001',
            'threadId': '20000000-0000-4000-8000-000000000001'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class VPSProofTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.storage = self.dir / 'packets'
        self.db = self.dir / 'jobs.sqlite'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('''CREATE TABLE codex_webhook_jobs(
                event_id TEXT, conversation_id TEXT, thread_id TEXT, status TEXT,
                payload TEXT, output TEXT, error TEXT)''')
            db.execute('INSERT INTO codex_webhook_jobs VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (*IDENTITY.values(), 'completed', 'first message', 'original answer', None))
        self.contents = b'{"candidate_commit":"example"}'
        self.packet = {'requestId': REQUEST, 'sha256': sha(self.contents),
                       'content_b64': base64.b64encode(self.contents).decode()}
        self.events = {IDENTITY['runId']: [
            'codex_exec.started {', f"  runId: '{IDENTITY['runId']}',",
            f"  conversationId: '{IDENTITY['conversationId']}',",
            f"  threadId: '{IDENTITY['threadId']}'", '}',
            'codex_exec.completed {', f"  runId: '{IDENTITY['runId']}',",
            f"  conversationId: '{IDENTITY['conversationId']}',",
            f"  threadId: '{IDENTITY['threadId']}'", '}']}

    def upload(self):
        return ssh._upload(self.packet, self.storage)

    def audit(self, uploaded, events):
        return ssh._audit({'requestId': REQUEST, 'upload': dict(uploaded, epoch=EPOCH), 'turns': [IDENTITY]},
                          self.storage, self.db, events, EPOCH)

    def test_exact_delivery_and_duplicate_upload(self):
        first = self.upload()
        self.assertEqual(first, self.upload())
        self.assertEqual((self.storage / REQUEST / 'packet.json').read_bytes(), self.contents)
        self.assertEqual(first, {'handle': REQUEST, 'sha256': sha(self.contents),
                                'bytes': len(self.contents)})
        wrong = b'changed but still has a valid hash'
        with self.assertRaises(ValueError):
            ssh._upload(dict(self.packet, sha256=sha(wrong),
                            content_b64=base64.b64encode(wrong).decode()), self.storage)

    def test_received_hash_is_checked_before_storage(self):
        with self.assertRaises(ValueError):
            ssh._upload(dict(self.packet, sha256='0' * 64), self.storage)
        self.assertFalse(self.storage.exists())

    def test_first_turn_and_payload_are_derived_from_real_database(self):
        uploaded = self.upload()
        before = self.db.read_bytes()
        connect = sqlite3.connect
        with patch.object(ssh.sqlite3, 'connect', wraps=connect) as observed:
            evidence = self.audit(uploaded, self.events)
            self.assertTrue(observed.call_args.kwargs['uri'])
            self.assertTrue(str(observed.call_args.args[0]).endswith('?mode=ro'))
        self.assertEqual(evidence, {'sha256': sha(self.contents), 'bytes': len(self.contents), 'epoch': EPOCH,
                                   'turns': [dict(IDENTITY, payload_sha256=sha(b'first message'),
                                        output_sha256=sha(b'original answer'), prior_jobs=0,
                                        started=True, completed=True, launch_mode='exec')]})
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_opening_or_foreign_handle_rejected(self):
        uploaded = self.upload()
        with self.assertRaises(ValueError):
            self.audit(uploaded, {IDENTITY['runId']: self.events[IDENTITY['runId']][5:]})
        with self.assertRaises(ValueError):
            self.audit(dict(uploaded, handle='../jobs.sqlite'), self.events)

    def test_prior_jobs_are_counted_from_actual_rows(self):
        uploaded = self.upload()
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('INSERT INTO codex_webhook_jobs(rowid,event_id,conversation_id,thread_id,status,payload,output,error) VALUES (0,?,?,?,?,?,?,?)',
                       ('different', IDENTITY['conversationId'], 'old', 'completed', 'old', 'old', None))
        evidence = self.audit(uploaded, self.events)
        self.assertEqual(evidence['turns'][0]['prior_jobs'], 1)
        self.assertIsNone(evidence['turns'][0]['launch_mode'])

    def test_packet_tampering_and_incorrect_journal_events_are_rejected(self):
        uploaded = self.upload()
        events = self.events[IDENTITY['runId']]
        for modified in (events[:5], [line.replace(IDENTITY['threadId'], 'wrong-thread') for line in events]):
            with self.assertRaises(ValueError):
                self.audit(uploaded, {IDENTITY['runId']: modified})
        (self.storage / REQUEST / 'packet.json').write_bytes(b'different bytes')
        with self.assertRaises(ValueError):
            self.audit(uploaded, self.events)

    def test_audit_rejects_foreign_or_failed_database_rows(self):
        uploaded = self.upload()
        try:
            for column, invalid, original in (
                ('conversation_id', 'foreign', IDENTITY['conversationId']),
                ('thread_id', 'foreign', IDENTITY['threadId']),
                ('status', 'failed', 'completed'), ('error', 'real failure', None),
            ):
                with self.subTest(column=column):
                    with closing(sqlite3.connect(self.db)) as db, db:
                        db.execute(f'UPDATE codex_webhook_jobs SET {column}=?', (invalid,))
                    with self.assertRaises(ValueError):
                        self.audit(uploaded, self.events)
                    with closing(sqlite3.connect(self.db)) as db, db:
                        db.execute(f'UPDATE codex_webhook_jobs SET {column}=?', (original,))
        finally:
            self.assertEqual(self.audit(uploaded, self.events)['turns'][0]['runId'],
                             IDENTITY['runId'])

    def test_deployment_rejects_bad_pins_inactive_unit_and_epoch_drift(self):
        worker = self.dir / 'worker.ts'
        launcher = self.dir / 'turn.ts'
        unit = self.dir / 'unit.service'
        worker.write_bytes(b'worker')
        launcher.write_bytes(b'launcher')
        unit.write_bytes(b'unit')
        pins = (sha(b'worker'), sha(b'launcher'))
        service = {'state': 'active', 'invocation': '7' * 32}
        first = ssh._deployment(worker, launcher, pins, service, [unit])
        self.assertRegex(first, r'^[0-9a-f]{64}$')
        self.assertEqual(first, ssh._deployment(worker, launcher, pins, service, [unit]))
        for invalid in (('0' * 64, pins[1]), (pins[0], '0' * 64)):
            with self.assertRaises(ValueError):
                ssh._deployment(worker, launcher, invalid, service, [unit])
        with self.assertRaises(ValueError):
            ssh._deployment(worker, launcher, pins, dict(service, state='inactive'), [unit])
        changed = ssh._deployment(worker, launcher, pins, dict(service, invocation='8' * 32), [unit])
        self.assertNotEqual(first, changed)
        stored = dict(self.upload(), epoch=first)
        with self.assertRaises(ValueError):
            ssh._audit({'requestId': REQUEST, 'upload': stored, 'turns': [IDENTITY]},
                       self.storage, self.db, self.events, changed)
        unit.write_bytes(b'new unit')
        self.assertNotEqual(first, ssh._deployment(worker, launcher, pins, service, [unit]))

    def test_audit_rejects_a_deployment_replaced_with_identical_bytes(self):
        worker = self.dir / 'worker.ts'
        launcher = self.dir / 'turn.ts'
        unit = self.dir / 'unit.service'
        for path, content in ((worker, b'worker'), (launcher, b'launcher'), (unit, b'unit')):
            path.write_bytes(content)
        pins = (sha(b'worker'), sha(b'launcher'))
        service = {'state': 'active', 'invocation': '7' * 32}
        first = ssh._deployment(worker, launcher, pins, service, [unit])
        prior = worker.stat()
        worker.write_bytes(b'changed')
        worker.write_bytes(b'worker')
        os.utime(worker, ns=(prior.st_atime_ns, prior.st_mtime_ns + 2_000_000_000))
        self.assertEqual(sha(worker.read_bytes()), pins[0])
        updated = ssh._deployment(worker, launcher, pins, service, [unit])
        self.assertNotEqual(first, updated)
        with self.assertRaises(ValueError):
            ssh._audit({'requestId': REQUEST, 'upload': dict(self.upload(), epoch=first),
                        'turns': [IDENTITY]}, self.storage, self.db, self.events, updated)

    def test_ssh_cli_sends_request_and_binds_the_host(self):
        path = self.dir / 'request.json'
        call = {'kind': 'call', 'action_id': 'upload-proof', 'operation': 'upload', 'input': self.packet}
        path.write_text(json.dumps(call), encoding='utf-8')
        answer = {'action_id': call['action_id'], 'result':
                  {'handle': REQUEST, 'sha256': sha(self.contents), 'bytes': len(self.contents), 'epoch': EPOCH}}
        args = ['--host', 'authorized-vps', '--request', str(path),
                '--worker-sha256', 'a'*64, '--launcher-sha256', 'b'*64]
        with patch.object(ssh.subprocess, 'run',
                          return_value=subprocess.CompletedProcess([],0,json.dumps(answer).encode(),b'')) as served:
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(ssh.main(args), 0)
            argv = served.call_args.args[0]
            self.assertIn('authorized-vps', argv)
            self.assertIn('StrictHostKeyChecking=yes', argv)
            self.assertIn('BatchMode=yes', argv)
            self.assertEqual(json.loads(served.call_args.kwargs['input']), call)
            self.assertEqual(json.loads(output.getvalue()), answer)
            remote_command = ' '.join(argv[argv.index('authorized-vps') + 1:])
            self.assertIn('a' * 64, remote_command)
            self.assertIn('b' * 64, remote_command)
