"""Prepare and assemble a review against real Git objects and KDD's verifier."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from tests.test_baseline_risk_review import ReviewFixture

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'scripts/prepare_baseline_review.py'
POLICY = 'kdd-vps-baseline-review-v1'
LENSES = ('simplicity', 'implementation', 'oracle')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(packet):
    fingerprint = digest(canonical(packet))
    name = f'kdd-vps-baseline-review/{POLICY}/{packet["candidate_commit"]}/{fingerprint}'
    return {'packet': packet, 'packet_sha256': fingerprint,
            'requestId': str(uuid.uuid5(uuid.NAMESPACE_URL, name))}


class VPSBaselineReviewTests(ReviewFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.candidate({'src/app.py': b'VALUE = 2\r\n', 'tests/new_oracle.py': 'assert 2 == 2\n',
                        'README.md': None})
        self.review_reads = [{'revision': 'candidate', 'path': 'src/app.py'},
                             {'revision': 'base', 'path': 'README.md'},
                             {'revision': 'candidate', 'path': 'tests/new_oracle.py'}]

    def process(self, script, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(script), *map(str, args),
                               '--repo-root', str(self.root)], cwd=self.owner, capture_output=True,
                              timeout=45)

    def artifact(self, name, value):
        path = self.owner / name
        path.write_bytes(canonical(value))
        return path

    def prepare(self, *args):
        result = self.process(ADAPTER, 'prepare', '--base-ref', self.base,
                              '--candidate-ref', self.head, *args)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
        return json.loads(result.stdout)

    def assemble(self, packet, handoff, expected=0, marker=None):
        response = self.process(ADAPTER, 'assemble', '--packet', self.artifact('packet.json', packet),
                                '--handoff', self.artifact('handoff.json', handoff))
        self.assertEqual(response.returncode, expected, response.stderr.decode('utf-8'))
        if expected == 2:
            self.assertEqual(response.stdout, b'')
            self.assertIn(marker, response.stderr.decode('utf-8'))
            return None
        return json.loads(response.stdout)

    def handoff(self, envelope):
        turns = []
        for number, lens_names, reads in ((1, LENSES[:-1], self.review_reads[:2]),
                                           (2, LENSES[-1:], self.review_reads[2:])):
            identity = {'runId': 'turn-' + str(number), 'conversationId': 'conversation-' + str(number),
                        'threadId': 'thread-' + str(number)}
            output = {'sha': self.head, 'packet_sha256': envelope['packet_sha256'],
                      'lenses': [{'name': name, 'assessment': 'pass', 'rationale': 'Checked exact blobs.'}
                                 for name in lens_names], 'read_set': reads, 'findings': []}
            turns.append({'id': 'review-' + str(number), 'reviewer': 'reviewer-' + str(number),
                          'result': dict(identity, status='completed',
                                         output=canonical(output).decode('utf-8'), error=None),
                          'opening': dict(identity, launch_mode='exec')})
        return {'requestId': envelope['requestId'], 'runId': 'dialogue-pilot', 'author': 'author',
                'risk': 'medium', 'risk_rationale': 'Change contract and implementation.',
                'risk_factors': [], 'turns': turns}

    def edit_output(self, turn, **changes):
        result = turn['result']
        result['output'] = canonical(dict(json.loads(result['output']), **changes)).decode('utf-8')

    def test_packet_uses_committed_bytes_on_both_sides(self):
        original = self.prepare('--source', 'candidate:tests/oracle.py')
        (self.root / '.gitattributes').write_bytes(b'src/app.py -diff\n')
        (self.root / 'src/app.py').write_bytes(b'WORKTREE ONLY\n')
        before = self.snapshot()
        envelope = self.prepare('--source', 'candidate:tests/oracle.py')
        self.assertEqual(envelope, original)
        packet = envelope['packet']
        sources = {(row['revision'], row['path']): row for row in packet['sources']}
        for key, expected in ((('base', 'src/app.py'), b'VALUE = 1\n'),
                              (('candidate', 'src/app.py'), b'VALUE = 2\r\n'),
                              (('base', 'README.md'), b'# A real project\n')):
            self.assertEqual(base64.b64decode(sources[key]['content_b64']), expected)
            self.assertEqual(sources[key]['sha256'], digest(expected))
        self.assertIn(('candidate', 'tests/oracle.py'), sources)
        diff = base64.b64decode(packet['diff_b64'])
        self.assertIn(b'+VALUE = 2\r\n', diff)
        self.assertNotIn(b'WORKTREE ONLY', diff)
        self.assertEqual(packet['candidate_tree'], self.git('rev-parse', self.head + '^{tree}'))
        self.assertEqual(self.snapshot(), before)

    def test_exact_repeat_uses_same_request_and_verifier_v1(self):
        envelope = self.prepare()
        self.git('config', '--local', 'core.abbrev', '13')
        self.assertEqual(envelope, self.prepare())
        self.assertEqual(envelope, seal(envelope['packet']))
        self.assertNotEqual(envelope['requestId'],
                            self.prepare('--source', 'candidate:tests/oracle.py')['requestId'])
        handoff = self.handoff(envelope)
        result = handoff['turns'][0]['result']
        result['output'] = canonical(dict(message=result['output'], next='ORACULOS')).decode('utf-8')
        combined = self.assemble(envelope, handoff)
        self.assertEqual(combined, self.assemble(envelope, handoff))
        provenance, draft = combined['provenance'], combined['draft']
        self.assertEqual(provenance['review_sha256'], digest(canonical(draft)))
        self.assertEqual(provenance['handoff_sha256'], digest(canonical(handoff)))
        self.assertEqual(provenance['turns'][0]['threadId'], 'thread-1')
        self.assertEqual(provenance['turns'][0]['output_sha256'],
                         digest(handoff['turns'][0]['result']['output'].encode('utf-8')))
        self.assertNotIn('runId', draft)
        review = self.artifact('review-v1.json', draft)
        run = self.process(ROOT / 'scripts/quality_baseline.py', '--base-ref', self.base,
                           '--candidate-ref', self.head, '--review', review)
        self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8'))
        self.assertEqual(json.loads(run.stdout), combined['verification'])

    def test_archived_blocked_verdict_is_preserved_without_freshness(self):
        envelope = self.prepare()
        handoff = self.handoff(envelope)
        turn = handoff['turns'][0]
        output = json.loads(turn['result']['output'])
        output['lenses'][1]['assessment'] = 'blocked'
        output['lenses'][1]['rationale'] = 'Missing the diff and the execution evidence.'
        archived = canonical({key: output[key] for key in ('sha', 'lenses', 'findings')})
        turn['result']['output'] = canonical(dict(message=archived.decode('utf-8'),
                                                  next='ORACULOS')).decode('utf-8')
        turn['opening'] = None
        combined = self.assemble(envelope, handoff, expected=1)
        review = combined['draft']['reviews'][0]
        self.assertFalse(review['fresh_context'])
        self.assertEqual(review['status'], 'not_run')
        self.assertEqual(review['read_set'], [])
        self.assertEqual(review['lenses'][1], output['lenses'][1])
        self.assertFalse(combined['provenance']['turns'][0]['packet_echoed'])
        codes = {item['code'] for item in combined['verification']['findings']}
        self.assertIn('LENS_BLOCKED', codes)
        self.assertIn('REVIEW_INCOMPLETE', codes)

    def test_execution_evidence_does_not_execute_or_mask_infrastructure_failure(self):
        target = self.owner / 'must-not-run'
        receipt = {'candidate_commit': self.head, 'argv': [
            sys.executable, '-c', 'open(' + repr(str(target)) + ', "w").close()'],
            'status': 'infrastructure_error', 'exit_code': 3,
            'stdout': '', 'stderr': 'git configuration unavailable'}
        result = self.prepare('--execution', self.artifact('execution.json', receipt))
        self.assertFalse(target.exists())
        self.assertEqual(result['packet']['execution'], receipt)
        self.assertNotEqual(result['requestId'], self.prepare()['requestId'])
        for patch in ({'candidate_commit': self.base}, {'status': 'passed'}):
            with self.subTest(patch=patch):
                bad = self.artifact('execution.json', dict(receipt, **patch))
                response = self.process(ADAPTER, 'prepare', '--base-ref', self.base,
                                        '--candidate-ref', self.head, '--execution', bad)
                self.assertEqual(response.returncode, 2, response.stderr.decode('utf-8'))
                self.assertEqual(response.stdout, b'')
                self.assertIn('EXECUTION', response.stderr.decode('utf-8'))

    def test_missing_promisor_blob_does_not_fetch(self):
        oid = self.git('rev-parse', self.base + ':README.md')
        blob = self.root / '.git/objects' / oid[:2] / oid[2:]
        self.assertTrue(blob.is_file())
        blob.unlink()
        self.git('config', '--local', 'remote.origin.promisor', 'true')
        response = self.process(ADAPTER, 'prepare', '--base-ref', self.base,
                                '--candidate-ref', self.head)
        self.assertEqual(response.returncode, 2, response.stderr.decode('utf-8'))
        self.assertEqual(response.stdout, b'')
        self.assertFalse(blob.exists())
        self.assertEqual(self.git('cat-file', 'blob', oid), '# A real project')


    def test_resealed_forgery_rejected_against_real_git(self):
        envelope = self.prepare()
        packet = copy.deepcopy(envelope['packet'])
        row = packet['sources'][0]
        row['content_b64'] = base64.b64encode(b'invented evidence').decode('ascii')
        row['sha256'] = digest(b'invented evidence')
        forged = seal(packet)
        self.assemble(forged, self.handoff(forged), expected=2, marker='PACKET')

    def test_rejects_unbound_claims_and_reused_thread(self):
        envelope = self.prepare()
        handoff = self.handoff(envelope)
        handoff['requestId'] = 'other-request'
        self.assemble(envelope, handoff, expected=2, marker='HANDOFF')
        handoff = self.handoff(envelope)
        self.edit_output(handoff['turns'][0], sha=self.base)
        self.assemble(envelope, handoff, expected=2, marker='TURN')
        handoff = self.handoff(envelope)
        turn = handoff['turns'][0]
        output = json.loads(turn['result']['output'])
        turn['result']['output'] = canonical(dict(sha=self.base,
            lenses=output['lenses'], findings=[])).decode('utf-8')
        self.assemble(envelope, handoff, expected=2, marker='TURN')
        handoff = self.handoff(envelope)
        self.edit_output(handoff['turns'][0], packet_sha256='0' * 64)
        self.assemble(envelope, handoff, expected=2, marker='TURN')
        handoff = self.handoff(envelope)
        self.edit_output(handoff['turns'][0], read_set=[
            {'revision': 'candidate', 'path': 'tests/oracle.py'}])
        self.assemble(envelope, handoff, expected=2, marker='SOURCE')
        handoff = self.handoff(envelope)
        handoff['turns'][1]['result']['threadId'] = 'thread-1'
        handoff['turns'][1]['opening']['threadId'] = 'thread-1'
        self.assemble(envelope, handoff, expected=2, marker='TURN')

    def test_findings_survive_assembly_and_bind_to_packet(self):
        envelope = self.prepare()
        handoff = self.handoff(envelope)
        turn = handoff['turns'][0]
        finding = {'id': 'proof-incomplete', 'severity': 'major', 'status': 'open',
                   'scope': 'src/app.py', 'rationale': 'Execution result was not furnished.',
                   'decided_by': None, 'evidence': [self.review_reads[0]]}
        self.edit_output(turn, findings=[finding])
        result = self.assemble(envelope, handoff, expected=1)
        self.assertEqual(result['draft']['findings'], [finding])
        self.assertIn('OPEN_FINDING', {row['code'] for row in result['verification']['findings']})
        outside_packet = {'revision': 'candidate', 'path': 'tests/oracle.py'}
        self.edit_output(turn, findings=[dict(finding, evidence=[outside_packet])])
        self.assemble(envelope, handoff, expected=2, marker='SOURCE')


    def test_rejects_incomplete_turns_and_mismatched_opening(self):
        envelope = self.prepare()
        for status in ('queued', 'running', 'failed'):
            with self.subTest(status=status):
                handoff = self.handoff(envelope)
                handoff['turns'][0]['result']['status'] = status
                self.assemble(envelope, handoff, expected=2, marker='TURN')
        handoff = self.handoff(envelope)
        handoff['turns'][0]['opening']['conversationId'] = 'different-conversation'
        self.assemble(envelope, handoff, expected=2, marker='TURN')


        handoff = self.handoff(envelope)
        handoff['turns'][0]['opening']['launch_mode'] = 'resume'
        self.assemble(envelope, handoff, expected=2, marker='TURN')

    def test_thread_id_without_opening_does_not_qualify(self):
        envelope = self.prepare()
        handoff = self.handoff(envelope)
        for turn in handoff['turns']:
            turn['opening'] = None
        combined = self.assemble(envelope, handoff, expected=1)
        self.assertFalse(any(review['fresh_context'] for review in combined['draft']['reviews']))
        self.assertIn('REVIEW_INDEPENDENCE',
                      {item['code'] for item in combined['verification']['findings']})


if __name__ == '__main__':
    unittest.main()
