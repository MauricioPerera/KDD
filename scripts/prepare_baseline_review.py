"""Prepare a local KDD v1 review from exact Git evidence and VPS results."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import baseline_review as review


POLICY_VERSION = 'kdd-vps-baseline-review-v1'
REVISIONS = {'base': 'base_commit', 'candidate': 'candidate_commit'}
IDENTITY = ('base_commit', 'candidate_commit', 'candidate_tree')
TURN_IDENTITY = ('runId', 'conversationId', 'threadId')


def _reject(code, message):
    raise review.ReviewError(f'{code}: {message}')


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    return json.loads(raw, object_pairs_hook=review._json_pairs, parse_constant=review._nonfinite)


def _read_json(path):
    return _json(Path(path).read_text(encoding='utf-8'))


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def _execution(receipt, candidate):
    if receipt is None:
        return None
    review._keys(receipt, 'candidate_commit argv status exit_code stdout stderr', 'EXECUTION')
    status, code = receipt['status'], receipt['exit_code']
    if (receipt['candidate_commit'] != candidate or type(code) is not int
            or not isinstance(receipt['argv'], list) or not receipt['argv']
            or any(not isinstance(arg, str) or not arg for arg in receipt['argv'])
            or any(not isinstance(receipt[key], str) for key in ('stdout', 'stderr'))):
        _reject('EXECUTION', 'expected an execution receipt for the exact candidate')
    if status not in ('passed', 'failed', 'infrastructure_error'):
        _reject('EXECUTION', 'unknown execution status')
    if ((status == 'passed' and code != 0) or (status == 'failed' and code == 0)):
        _reject('EXECUTION', 'execution status contradicts its exit code')
    return receipt


def _sources(root, context, extra):
    keys = set(review._source_specs(extra))
    keys.update((revision, change['path']) for change in context['changes']
                for revision, side in (('base', 'before'), ('candidate', 'after'))
                if change[side] is not None)
    objects = {}
    for revision, field in REVISIONS.items():
        paths = {path for rev, path in keys if rev == revision}
        entries = review._tree_sources(root, context[field], paths)
        objects.update({(revision, path): obj for path, obj in entries.items()})
    contents = review._blob_contents(root, {obj['oid'] for obj in objects.values()})
    result = []
    for (revision, path), obj in sorted(objects.items()):
        data = contents[obj['oid']]
        result.append(dict(obj, revision=revision, path=path, sha256=_sha256(data),
                           content_b64=_b64(data)))
    return result


def _diff(root, base, candidate):
    return review._git(root, '-c', 'core.quotePath=true', '--attr-source=' + candidate,
        'diff-tree', '-r', '--patch', '--binary', '--full-index', '--no-commit-id',
        '--no-renames', '--no-ext-diff', '--no-textconv', '--no-color',
        '--diff-algorithm=myers', '--no-indent-heuristic', '--unified=3',
        '--inter-hunk-context=0', '--src-prefix=a/', '--dst-prefix=b/', base, candidate)


def _prepare(root, base, candidate, extra, execution):
    context = review.inspect_change(root, base, candidate)
    context.pop('review_ready')
    packet = dict(context, policy_version=POLICY_VERSION,
                  execution=_execution(execution, candidate), sources=_sources(root, context, extra),
                  diff_b64=_b64(_diff(root, base, candidate)))
    digest = _sha256(_canonical(packet))
    name = f'kdd-vps-baseline-review/{POLICY_VERSION}/{candidate}/{digest}'
    return {'packet': packet, 'packet_sha256': digest,
            'requestId': str(uuid.uuid5(uuid.NAMESPACE_URL, name))}


def _recheck_packet(root, envelope):
    review._keys(envelope, 'packet packet_sha256 requestId', 'PACKET')
    packet = envelope['packet']
    review._keys(packet, 'schema_version policy_version base_commit candidate_commit candidate_tree '
                         'changes risk_floor execution sources diff_b64', 'PACKET')
    sources = []
    for row in review._list(packet['sources']):
        review._keys(row, 'revision path mode oid sha256 content_b64', 'PACKET')
        sources.append({'revision': row['revision'], 'path': row['path']})
    rebuilt = _prepare(root, packet['base_commit'], packet['candidate_commit'],
                       sources, packet['execution'])
    if _canonical(rebuilt) != _canonical(envelope):
        _reject('PACKET', 'envelope does not match rebuilt Git evidence')
    return sources


def _opening(opening, identity):
    if opening is None:
        return False
    review._keys(opening, 'runId conversationId threadId launch_mode', 'TURN')
    if opening != dict(identity, launch_mode='exec'):
        _reject('TURN', 'opening does not identify a fresh launch for this turn')
    return True


def _response(output, envelope):
    response = _json(output)
    if isinstance(response, dict) and set(response) == {'message', 'next'}:
        if response['next'] is not None:
            review._text(response['next'])
        if not isinstance(response['message'], str):
            _reject('TURN', 'dialogue message must contain JSON text')
        response = _json(response['message'])
    archived = isinstance(response, dict) and set(response) == {'sha', 'lenses', 'findings'}
    if not archived:
        review._keys(response, 'sha packet_sha256 lenses read_set findings', 'TURN')
        if response['packet_sha256'] != envelope['packet_sha256']:
            _reject('TURN', 'reviewer named a different evidence packet')
    if response['sha'] != envelope['packet']['candidate_commit']:
        _reject('TURN', 'reviewer named a different candidate commit')
    return response, archived


def _check_sources(read_set, findings, allowed):
    review._finding_schema(findings)
    chosen = set(review._source_specs(read_set))
    for finding in findings:
        chosen.update(review._source_specs(finding['evidence']))
    if not chosen.issubset(allowed):
        _reject('SOURCE', 'turn cites a source outside the evidence packet')


def _turn(turn, envelope, allowed):
    review._keys(turn, 'id reviewer result opening', 'TURN')
    result = turn['result']
    review._keys(result, 'runId conversationId status threadId output error', 'TURN')
    identity = {key: result[key] for key in TURN_IDENTITY}
    for value in identity.values():
        review._text(value)
    if (result['status'] != 'completed' or result['error'] is not None
            or not isinstance(result['output'], str)):
        _reject('TURN', 'a completed individual VPS turn is required')
    fresh = _opening(turn['opening'], identity)
    response, archived = _response(result['output'], envelope)
    read_set, findings = response.get('read_set', []), response['findings']
    _check_sources(read_set, findings, allowed)
    row = {'id': turn['id'], 'reviewer': turn['reviewer'], 'kind': 'agent',
           'fresh_context': fresh and not archived, 'status': 'not_run' if archived else 'completed',
           'lenses': response['lenses'], 'read_set': read_set}
    provenance = dict(identity, review_id=turn['id'], opening=turn['opening'],
                      output_sha256=_sha256(result['output'].encode('utf-8')),
                      packet_echoed=not archived)
    return row, findings, provenance


def _assemble(root, envelope, handoff):
    sources = _recheck_packet(root, envelope)
    review._keys(handoff, 'requestId runId author risk risk_rationale risk_factors turns', 'HANDOFF')
    if handoff['requestId'] != envelope['requestId']:
        _reject('HANDOFF', 'requestId differs from the evidence packet')
    review._text(handoff['runId'])
    allowed = set(review._source_specs(sources))
    reviews, findings, turns = [], [], []
    for turn in review._list(handoff['turns']):
        row, found, provenance = _turn(turn, envelope, allowed)
        reviews.append(row)
        findings.extend(found)
        turns.append(provenance)
    for key in TURN_IDENTITY:
        if len({turn[key] for turn in turns}) != len(turns):
            _reject('TURN', 'a ' + key + ' is reused across reviewers')
    packet = envelope['packet']
    draft = {key: packet[key] for key in IDENTITY}
    draft.update({key: handoff[key] for key in ('author', 'risk', 'risk_rationale', 'risk_factors')})
    draft.update(schema_version=1, reviews=reviews, findings=findings)
    raw = _canonical(draft)
    verdict = review.verify_review(root, packet['base_commit'], packet['candidate_commit'],
                                   raw.decode('utf-8'))
    provenance = {'requestId': envelope['requestId'], 'runId': handoff['runId'],
                  'packet_sha256': envelope['packet_sha256'], 'review_sha256': _sha256(raw),
                  'handoff_sha256': _sha256(_canonical(handoff)), 'turns': turns}
    return {'draft': draft, 'provenance': provenance, 'verification': verdict}


def _prepare_cli(args):
    extra = []
    for value in args.source:
        revision, _, path = value.partition(':')
        extra.append({'revision': revision, 'path': path})
    receipt = _read_json(args.execution) if args.execution else None
    return _prepare(args.repo_root, args.base_ref, args.candidate_ref, extra, receipt)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='create a digest-bound evidence packet')
    assemble = commands.add_parser('assemble', help='validate a v1 draft and preserve provenance')
    for subparser in (prepare, assemble):
        subparser.add_argument('--repo-root', default='.')
    prepare.add_argument('--base-ref', required=True)
    prepare.add_argument('--candidate-ref', required=True)
    prepare.add_argument('--source', action='append', default=[], metavar='REVISION:PATH')
    prepare.add_argument('--execution')
    assemble.add_argument('--packet', required=True)
    assemble.add_argument('--handoff', required=True)
    return parser


def main(argv=None):
    """Emit packet or review JSON after checking all inputs."""
    args = _parser().parse_args(argv)
    try:
        if args.command == 'prepare':
            print(json.dumps(_prepare_cli(args), sort_keys=True, indent=2))
            return 0
        result = _assemble(args.repo_root, _read_json(args.packet), _read_json(args.handoff))
    except (ValueError, OSError, RecursionError) as exc:
        print('REJECT VPS review: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['verification']['review_ready'] else 1


if __name__ == '__main__':
    # Disable lazy fetching in every child Git process, including reused verifier calls.
    os.environ['GIT_NO_LAZY_FETCH'] = '1'
    os.environ['GIT_ALLOW_PROTOCOL'] = ''
    raise SystemExit(main())
