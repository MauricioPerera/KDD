"""Exercise the coordinator through real Git, CLI calls and immutable receipts."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from tests.test_baseline_risk_review import ReviewFixture

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/run_vps_baseline_review.py'
ADAPTER = ROOT / 'scripts/prepare_baseline_review.py'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


class VPSAutomationTests(ReviewFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.candidate({'src/app.py': 'VALUE = 2\n', 'tests/test_new.py': 'assert True\n'})
        result = self.run_cli(ADAPTER, 'prepare', '--repo-root', self.root, '--base-ref',
                              self.base, '--candidate-ref', self.head)
        self.packet = json.loads(result)
        self.files = write(self.owner / 'packet.json', self.packet)
        self.plan = {'author': 'Author', 'risk': 'medium', 'risk_rationale': 'New code and test.',
                     'risk_factors': [], 'reviewers': [
                        {'name': 'GIT', 'lenses': ['simplicity', 'implementation'],
                         'sources': [{'revision': 'candidate', 'path': 'src/app.py'}]},
                        {'name': 'ORACLE', 'lenses': ['oracle'],
                         'sources': [{'revision': 'candidate', 'path': 'tests/test_new.py'}]}]}
        self.plan_file = write(self.owner / 'plan.json', self.plan)
        self.state = self.owner / 'state.json'
        self.proofs = []

    def run_cli(self, script, *args, expected=0, error=None):
        p = subprocess.run([sys.executable, '-X', 'utf8', str(script), *map(str, args)],
                           cwd=self.owner, capture_output=True, encoding='utf-8', timeout=40)
        self.assertEqual(p.returncode, expected, p.stderr)
        if error:
            self.assertIn(error, p.stderr)
        return p.stdout

    def run_state(self, *args, **kwargs):
        return self.run_cli(RUNNER, '--repo-root', self.root, '--packet', self.files,
                            '--plan', self.plan_file, '--state', self.state, *args, **kwargs)

    def next(self, operation=None, expected=0):
        request = json.loads(self.run_state('next', expected=expected))
        if operation:
            self.assertEqual(request['kind'], 'call')
            self.assertEqual(request['operation'], operation)
        return request

    def record(self, action, result, **kwargs):
        answer = write(self.owner / 'answer.json', {'action_id': action['action_id'], 'result': result})
        output = self.run_state('record', '--response', answer, **kwargs)
        if kwargs.get('expected', 0) == 0:
            self.assertEqual(json.loads(output),
                             {'kind': 'recorded', 'action_id': action['action_id']})

    def upload(self):
        action = self.next('upload')
        raw = base64.b64decode(action['input']['content_b64'], validate=True)
        self.assertEqual(json.loads(raw), self.packet['packet'])
        self.assertEqual(action['input']['sha256'], digest(raw))
        self.assertEqual(action['input']['requestId'], self.packet['requestId'])
        result = {'handle': self.packet['requestId'], 'sha256': digest(raw), 'bytes': len(raw), 'epoch': 'e' * 64}
        self.assertEqual(result['sha256'], self.packet['packet_sha256'])
        return action, result

    def opening(self, index, blocked=False, foreign_read=False, finding=None, terminal=False):
        action = self.next('codex_send')
        self.assertEqual(set(action['input']), {'message'})
        prompt = action['input']['message']
        number = index + 1
        reviewer = self.plan['reviewers'][index]
        source = next(row for row in self.packet['packet']['sources']
                      if row['path'] == reviewer['sources'][0]['path'] and row['revision'] == 'candidate')
        self.assertIn(base64.b64decode(source['content_b64']).decode(), prompt)
        self.assertIn(self.packet['packet_sha256'], prompt)
        self.assertIn(self.head, prompt)
        self.assertIn('--- EVIDENCIA KDD ---', prompt)
        for key in ('sha', 'packet_sha256', 'read_set', 'findings', 'lenses'):
            self.assertIn('"' + key + '"', prompt)
        self.assertEqual(prompt.strip(), prompt)
        self.assertLessEqual(len(prompt.encode('utf-16-le')) // 2, 8000)
        identity = {'runId': f'run_00000000-0000-4000-8000-{number:012d}',
                    'conversationId': f'10000000-0000-4000-8000-{number:012d}'}
        self.record(action, dict(identity, status='queued'))
        action = self.next('codex_result')
        self.assertEqual(action['input'], {'runId': identity['runId']})
        if terminal:
            self.record(action, dict(identity, status='failed', threadId=None, output=None,
                                     error='process terminated'), expected=2)
            return
        self.record(action, dict(identity, status='running', threadId=None, output=None, error=None))
        action = self.next('codex_result')
        self.assertEqual(action['input'], {'runId': identity['runId']})
        identity['threadId'] = f'20000000-0000-4000-8000-{number:012d}'
        payload = {'sha': self.head, 'packet_sha256': self.packet['packet_sha256'],
                   'read_set': reviewer['sources'], 'findings': [] if finding is None else [finding],
                   'lenses': [{'name': name, 'assessment': 'blocked' if blocked else 'pass',
                               'rationale': 'Read and checked the committed source.'}
                              for name in reviewer['lenses']]}
        if foreign_read:
            payload['read_set'] = self.plan['reviewers'][1]['sources']
            result = dict(identity, status='completed', output=json.dumps(payload), error=None)
            self.record(action, result, expected=2)
            return
        if finding and finding['evidence'] != reviewer['sources']:
            self.record(action, dict(identity, status='completed', output=json.dumps(payload), error=None),
                        expected=2)
            return
        body = json.dumps(payload)
        self.record(action, dict(identity, status='completed', output=body, error=None))
        self.proofs.append(dict(identity, payload_sha256=digest(prompt.encode()),
                                output_sha256=digest(body.encode()), prior_jobs=0,
                                started=True, completed=True, launch_mode='exec'))

    def audited(self, blocked=False, finding=None):
        action, uploaded = self.upload()
        self.record(action, uploaded)
        self.opening(0, blocked, finding=finding)
        self.opening(1)
        audit = self.next('audit')
        self.assertEqual(audit['input']['upload'], uploaded)
        self.assertEqual(audit['input']['requestId'], self.packet['requestId'])
        self.assertEqual(audit['input']['turns'], [
            {key: row[key] for key in ('runId', 'conversationId', 'threadId')} for row in self.proofs])
        return audit, {'sha256': uploaded['sha256'], 'bytes': uploaded['bytes'], 'epoch': uploaded['epoch'], 'turns': self.proofs}

    def dialogue(self, wrong_run=False, altered_transcript=False, duplicate_false=False):
        action = self.next('codex_dialogue')
        self.assertEqual(action['input']['requestId'], self.packet['requestId'])
        self.assertEqual(action['input']['participants'], [
            {'name': review['name'], 'conversationId': proof['conversationId']}
            for review, proof in zip(self.plan['reviewers'], self.proofs)])
        self.assertTrue(0 < len(action['input']['topic']) <= 1000)
        self.assertEqual(action['input']['handoff'], {'start': 'GIT', 'maxTurns': 2})
        run = 'run_50000000-0000-4000-8000-000000000001'
        self.record(action, {'kind': 'dialogue', 'status': 'queued', 'runId': run, 'duplicate': False})
        before = {'kind': 'dialogue', 'status': 'completed', 'runId': run,
                  'completedTurns': 2, 'error': None, 'transcript': [
                     {'speaker': 'GIT', 'message': 'Complete', 'runId': 'run_60000000-0000-4000-8000-000000000001'},
                     {'speaker': 'ORACLE', 'message': 'Complete', 'runId': 'run_60000000-0000-4000-8000-000000000002'}]}
        status = self.next('codex_result')
        self.assertEqual(status['input'], {'runId': run})
        self.record(status, before)
        repeat = self.next('codex_dialogue')
        self.assertEqual(repeat['input'], action['input'])
        duplicate = {'kind': 'dialogue', 'status': 'completed', 'runId': run, 'duplicate': True}
        if wrong_run:
            duplicate['runId'] = 'run_50000000-0000-4000-8000-000000000002'
            self.record(repeat, duplicate, expected=2, error='runId')
            return
        if duplicate_false:
            self.record(repeat, dict(duplicate, duplicate=False), expected=2, error='duplicate')
            return
        self.record(repeat, duplicate)
        replay = self.next('codex_result')
        self.assertEqual(replay['input'], {'runId': run})
        if altered_transcript:
            before['transcript'][0]['message'] = 'Changed'
            self.record(replay, before, expected=2, error='transcript')
            return
        self.record(replay, before)
        return run

    def test_full_workflow_uses_same_dialogue_request_and_validates_v1(self):
        before = self.snapshot()
        self.record(*self.audited())
        run = self.dialogue()
        result = self.next()
        self.assertEqual(result['kind'], 'done')
        self.assertEqual(set(result), {'kind','runId','draft','provenance','verification'})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result['provenance']['packet_sha256'], self.packet['packet_sha256'])
        self.assertEqual(result['provenance']['requestId'], self.packet['requestId'])
        self.assertEqual(result, self.next())
        self.assertTrue(result['verification']['review_ready'])
        self.assertEqual(result['runId'], run)
        self.assertEqual(result['provenance']['runId'], run)
        self.assertTrue(all(review['fresh_context'] for review in result['draft']['reviews']))
        review = write(self.owner / 'review.json', result['draft'])
        direct = json.loads(self.run_cli(ROOT / 'scripts/quality_baseline.py',
                            '--repo-root', self.root, '--base-ref', self.base,
                            '--candidate-ref', self.head, '--review', review))
        self.assertTrue(direct['review_ready'])
        self.assertEqual(direct['sources'], result['verification']['sources'])

    def test_blocked_lens_remains_blocked(self):
        self.record(*self.audited(blocked=True))
        self.dialogue()
        result = self.next(expected=1)
        self.assertFalse(result['verification']['review_ready'])
        self.assertIn('LENS_BLOCKED', {f['code'] for f in result['verification']['findings']})

    def test_upload_mismatch_and_foreign_action_cannot_open_reviewer(self):
        action, uploaded = self.upload()
        self.record(dict(action, action_id='unknown'), uploaded, expected=2)
        self.record(action, dict(uploaded, sha256='0' * 64), expected=2)
        self.assertEqual(self.next('upload'), action)

    def test_unconfirmed_open_is_not_reissued(self):
        self.record(*self.upload())
        opening = self.next('codex_send')
        self.run_state('next', expected=2, error='codex_send')
        self.record(opening, {'runId': 'run_00000000-0000-4000-8000-000000000001',
                             'conversationId': '10000000-0000-4000-8000-000000000001', 'status': 'queued'})
        self.next('codex_result')

    def test_wrong_payload_output_or_prior_job_blocks_audit(self):
        action, evidence = self.audited()
        for key, value in [('payload_sha256', '0' * 64), ('output_sha256', '0' * 64),
                           ('prior_jobs', 1), ('started', False), ('launch_mode', 'resume'), ('threadId', self.proofs[1]['threadId'])]:
            with self.subTest(key=key):
                changed = [dict(self.proofs[0], **{key: value}), self.proofs[1]]
                self.record(action, dict(evidence, turns=changed), expected=2)
        self.record(action, dict(evidence, epoch='f' * 64), expected=2)
        self.record(action, evidence)

    def test_changed_plan_cannot_continue_existing_state(self):
        self.record(*self.upload())
        self.plan['risk_rationale'] = 'A different plan.'
        write(self.plan_file, self.plan)
        self.run_state('next', expected=2)

    def test_same_run_id_with_changed_transcript_is_rejected(self):
        self.record(*self.audited())
        self.dialogue(altered_transcript=True)

    def test_different_run_on_repeat_is_rejected(self):
        self.record(*self.audited())
        self.dialogue(wrong_run=True)


    def test_model_cannot_claim_a_source_delivered_to_the_other_thread(self):
        self.record(*self.upload())
        self.opening(0, foreign_read=True)

    def test_oversized_message_is_rejected_before_any_upload(self):
        self.candidate({'src/app.py': 'VALUE = "' + 'x' * 8100 + '"\n'})
        result = self.run_cli(ADAPTER, 'prepare', '--repo-root', self.root, '--base-ref',
                              self.base, '--candidate-ref', self.head)
        self.files.write_text(result, encoding='utf-8')
        self.run_state('next', expected=2)
        self.assertFalse(self.state.exists())

    def test_open_finding_is_preserved(self):
        finding = {'id':'no-negative-control','severity':'major','status':'open',
                   'scope':'src/app.py','rationale':'Missing a negative control.',
                   'decided_by':None,'evidence':self.plan['reviewers'][0]['sources']}
        self.record(*self.audited(finding=finding))
        self.dialogue()
        result = self.next(expected=1)
        self.assertEqual(result['draft']['findings'], [finding])
        self.assertIn('OPEN_FINDING', {row['code'] for row in result['verification']['findings']})

    def test_finding_cannot_cite_an_undelivered_source(self):
        self.record(*self.upload())
        self.opening(0, finding={'id':'foreign','severity':'major','status':'open',
                     'scope':'src/app.py','rationale':'Used an undelivered source.',
                     'decided_by':None,'evidence':self.plan['reviewers'][1]['sources']})

    def test_resealed_forgery_is_rejected_before_upload(self):
        packet = self.packet['packet']
        row = packet['sources'][0]
        row['content_b64'] = base64.b64encode(b'invented source').decode()
        row['sha256'] = digest(b'invented source')
        raw = json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        fingerprint = digest(raw)
        namespace = 'kdd-vps-baseline-review/'+packet['policy_version']+'/'+self.head+'/'+fingerprint
        self.packet.update(packet_sha256=fingerprint, requestId=str(uuid.uuid5(uuid.NAMESPACE_URL, namespace)))
        write(self.files, self.packet)
        self.run_state('next', expected=2)
        self.assertFalse(self.state.exists())

    def test_missing_promisor_blob_is_not_fetched(self):
        result = self.run_cli(ADAPTER, 'prepare', '--repo-root', self.root, '--base-ref',
                              self.base, '--candidate-ref', self.head, '--source', 'base:README.md')
        self.files.write_text(result, encoding='utf-8')
        oid = self.git('rev-parse', self.base + ':README.md')
        missing = self.root / '.git/objects' / oid[:2] / oid[2:]
        missing.unlink()
        self.git('config', '--local', 'remote.origin.promisor', 'true')
        self.run_state('next', expected=2)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.git('cat-file', 'blob', oid), '# A real project')

    def test_nonduplicate_retry_is_rejected(self):
        self.record(*self.audited())
        self.dialogue(duplicate_false=True)

    def test_failed_provider_turn_cannot_become_a_review(self):
        self.record(*self.upload())
        self.opening(0, terminal=True)

    def test_two_concurrent_callers_emit_only_one_opening(self):
        self.record(*self.upload())
        args = [sys.executable, '-X', 'utf8', str(RUNNER), '--repo-root', str(self.root),
                '--packet', str(self.files), '--plan', str(self.plan_file), '--state',
                str(self.state), 'next']
        def launch(_):
            return subprocess.run(args, cwd=self.owner, capture_output=True,
                                  encoding='utf-8', timeout=40)
        with ThreadPoolExecutor(max_workers=2) as threads:
            observed = list(threads.map(launch, range(2)))
        self.assertEqual(sorted(p.returncode for p in observed), [0, 2])
        emitted = json.loads(next(p.stdout for p in observed if p.returncode==0))
        self.assertEqual(emitted['operation'], 'codex_send')

    def test_excerpt_and_execution_evidence_reach_the_prompt(self):
        self.candidate({'docs/context.md': 'NEIGHBOR_FIRST\nONLY_THIS_LINE\nNEIGHBOR_LAST\n'})
        base = self.head
        self.candidate({'src/app.py': 'VALUE = 3\n'})
        self.plan['reviewers'][1]['sources'] = self.plan['reviewers'][0]['sources']
        receipt = write(self.owner / 'execution.json', {'candidate_commit': self.head,
                        'argv': ['python','actual_oracle.py'], 'status':'failed',
                        'exit_code':7, 'stdout':'BOUND_TEST_OUTPUT', 'stderr':''})
        prepared = self.run_cli(ADAPTER, 'prepare', '--repo-root', self.root, '--base-ref',
                                base, '--candidate-ref', self.head,
                                '--source','base:docs/context.md','--execution',receipt)
        self.files.write_text(prepared,encoding='utf-8')
        self.packet=json.loads(prepared)
        self.plan['reviewers'][0]['excerpts']=[
            {'revision':'base','path':'docs/context.md','start_line':2,'end_line':2}]
        write(self.plan_file,self.plan)
        self.record(*self.upload())
        sent = self.next('codex_send')
        prompt = sent['input']['message']
        self.assertIn('EXTRACTO docs/context.md 2-2', prompt)
        self.assertIn('ONLY_THIS_LINE', prompt)
        self.assertNotIn('NEIGHBOR_FIRST', prompt)
        self.assertNotIn('NEIGHBOR_LAST', prompt)
        self.assertIn('BOUND_TEST_OUTPUT', prompt)
        self.assertIn('actual_oracle.py', prompt)
        self.assertIn('failed', prompt)
        identity = {'runId': 'run_00000000-0000-4000-8000-000000000001',
                    'conversationId': '10000000-0000-4000-8000-000000000001'}
        self.record(sent, dict(identity, status='queued'))
        polled = self.next('codex_result')
        identity['threadId'] = '20000000-0000-4000-8000-000000000001'
        report = {'sha': self.head, 'packet_sha256': self.packet['packet_sha256'],
                  'read_set': self.plan['reviewers'][0]['sources'] +
                              [{'revision': 'base', 'path': 'docs/context.md'}],
                  'lenses': [{'name': lens, 'assessment': 'pass', 'rationale': 'Fixture verdict.'}
                             for lens in self.plan['reviewers'][0]['lenses']], 'findings': []}
        self.record(polled, dict(identity, status='completed', error=None,
                                 output=json.dumps(report)), expected=2)
