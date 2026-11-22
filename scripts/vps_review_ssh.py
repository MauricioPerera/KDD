"""Read Codex VPS delivery and first-turn evidence over an authorized SSH host."""
import argparse
import base64
import hashlib
import json
import os
from contextlib import closing
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import uuid


WORKER = Path('/opt/codex-webhook/app/codex-webhook.ts')
LAUNCHER = WORKER.with_name('codex-turn.ts')
WEBHOOK = 'codex-webhook.service'
TURN = 'codex-turn@{}.service'
IDS = ('runId', 'conversationId', 'threadId')
UID = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}')


def _require(condition, detail):
    if not condition:
        raise ValueError(detail)


def _json(data):
    return json.dumps(data, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('ascii')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    _require(isinstance(value, str) and UID.fullmatch(value) and str(uuid.UUID(value)) == value,
             'invalid request or conversation identity')
    return value


def _digest(value):
    _require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value), 'invalid SHA-256')
    return value


def _direct_child(parent, name):
    child = parent / name
    _require(not child.is_symlink() and child.resolve().parent == parent.resolve(),
             'unsafe path in private delivery store')
    return child


def _destination(root, request_id):
    directory = _direct_child(root, _uuid(request_id))
    return _direct_child(directory, 'packet.json')


def _fill_once(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.receipt-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temporary.unlink()
            raise
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        _require(not path.is_symlink() and path.is_file() and path.read_bytes() == raw,
                 'existing delivery differs from this request')
    finally:
        temporary.unlink()


def _upload(data, root):
    _require(set(data) == {'requestId', 'sha256', 'content_b64'}, 'invalid upload fields')
    expected = _digest(data['sha256'])
    raw = base64.b64decode(data['content_b64'], validate=True)
    _require(_sha(raw) == expected, 'delivery hash does not match')
    _require(not root.is_symlink(), 'unsafe private root')
    destination = _destination(root, data['requestId'])
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _fill_once(destination, raw)
    stored = destination.read_bytes()
    return {'handle': data['requestId'], 'sha256': _sha(stored), 'bytes': len(stored)}


def _file_epoch(path):
    def metadata():
        item = path.stat()
        return (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)

    before = metadata()
    sha = _sha(path.read_bytes())
    _require(metadata() == before, 'deployment file changed while reading')
    return {'path': str(path), 'sha256': sha, 'metadata': before}


def _deployment(worker, launcher, pins, service, unit_files):
    _require(service['state'] == 'active' and
             re.fullmatch(r'[a-f0-9]{32}', service['invocation']), 'inactive or unidentified service')
    files = [_file_epoch(path) for path in (worker, launcher, *unit_files)]
    _require(tuple(file['sha256'] for file in files[:2]) == tuple(pins),
             'worker or launcher does not match its reviewed pin')
    return _sha(_json({'service': service, 'files': files}))


def _unit_properties(unit, fields):
    output = _read_command(['systemctl', 'show', '--no-pager', unit, '-p', ','.join(fields)])
    return dict(line.split('=', 1) for line in output.splitlines() if '=' in line)


def _read_command(argv):
    result = subprocess.run(argv, capture_output=True, check=True, timeout=30)
    return result.stdout.decode('utf-8')


def _check_unit(run_id):
    values = _unit_properties(TURN.format(run_id), ('ExecStart', 'WorkingDirectory', 'FragmentPath', 'DropInPaths'))
    argv = values['ExecStart'].partition('argv[]=')[2].partition(' ;')[0].split()
    _require(values['WorkingDirectory'] == str(WORKER.parent) and len(argv) == 3
             and Path(argv[0]).is_absolute() and Path(argv[0]).name == 'node'
             and argv[1:] == [str(LAUNCHER), run_id], 'unexpected turn launcher command')
    return values


def _live_epoch(pins):
    fields = ('ActiveState', 'InvocationID', 'MainPID', 'FragmentPath', 'DropInPaths', 'ExecStart')
    values = _unit_properties(WEBHOOK, fields)
    sample = _check_unit('run_kdd_provenance')
    unit_files = [Path(name) for unit in (values, sample)
                  for name in [unit['FragmentPath'], *unit['DropInPaths'].split()]]
    service = {'state': values['ActiveState'], 'invocation': values['InvocationID'],
               'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               'worker_command': values['ExecStart'], 'turn_command': sample['ExecStart']}
    epoch = _deployment(WORKER, LAUNCHER, pins, service, unit_files)
    _require(values == _unit_properties(WEBHOOK, fields), 'service changed during measurement')
    return epoch, values['MainPID']


def _packet_receipt(root, data, epoch):
    upload = data['upload']
    request_id = _uuid(data['requestId'])
    _require(upload['handle'] == request_id and upload['epoch'] == epoch, 'foreign handle or deployment epoch')
    raw = _destination(root, request_id).read_bytes()
    _require(_sha(raw) == upload['sha256'] and len(raw) == upload['bytes'], 'stored packet differs from receipt')
    return {'sha256': _sha(raw), 'bytes': len(raw), 'epoch': epoch}


def _journal_field(event, line):
    key, separator, value = line.partition(':')
    if separator and key in IDS:
        _require(key not in event, 'ambiguous journal event')
        event[key] = value.strip().rstrip(',').strip("'")


def _event_groups(messages):
    events = []
    current = None
    for line in (line.strip() for message in messages for line in message.splitlines()):
        if line in ('codex_exec.started {', 'codex_exec.completed {'):
            current = {'kind': line.split()[0]}
        elif current is not None and line == '}':
            events.append(current)
            current = None
        elif current is not None:
            _journal_field(current, line)
    return events


def _opening_events(events, identity):
    expected = [dict(identity, kind=kind) for kind in ('codex_exec.started', 'codex_exec.completed')]
    return _event_groups(events) == expected


def _job(connection, identity, messages):
    row = connection.execute('''SELECT rowid, conversation_id, thread_id, status, payload, output, error
        FROM codex_webhook_jobs WHERE event_id=?''', (identity['runId'],)).fetchone()
    _require(row and (row['conversation_id'], row['thread_id']) ==
             (identity['conversationId'], identity['threadId']) and
             row['status'] == 'completed' and row['error'] is None, 'turn row does not prove completion')
    _require(_opening_events(messages, identity), 'journal does not prove both events')
    prior = connection.execute('''SELECT count(*) FROM codex_webhook_jobs
        WHERE conversation_id=? AND rowid<?''', (row['conversation_id'], row['rowid'])).fetchone()[0]
    return dict(identity, started=True, completed=True, prior_jobs=prior,
                launch_mode='exec' if prior == 0 else None,
                payload_sha256=_sha(row['payload'].encode('utf-8')),
                output_sha256=_sha(row['output'].encode('utf-8')))


def _audit(data, root, database, events, epoch):
    receipt = _packet_receipt(root, data, epoch)
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        turns = [_job(connection, identity, events[identity['runId']]) for identity in data['turns']]
    return dict(receipt, turns=turns)


def _database(pid):
    _require(pid.isascii() and pid.isdecimal() and pid != '0', 'invalid server pid')
    proc = Path('/proc') / pid
    prefix = b'MCP_DB_PATH='
    configured = [item[len(prefix):].decode('utf-8') for item in
                  (proc / 'environ').read_bytes().split(b'\0') if item.startswith(prefix)]
    _require(len(configured) <= 1, 'ambiguous database location')
    database = Path(configured[0] if configured else 'mcp-events.sqlite')
    return ((proc / 'cwd') / database).resolve(strict=True)


def _journal(identity, delivered_ns):
    _require(set(identity) == set(IDS) and identity['runId'].startswith('run_'), 'invalid run identity')
    _uuid(identity['runId'][4:])
    _uuid(identity['conversationId'])
    _uuid(identity['threadId'])
    _check_unit(identity['runId'])
    output = _read_command(['journalctl', '-u', TURN.format(identity['runId']),
                            '--since', '@' + str(delivered_ns // 10**9), '-o', 'json', '--no-pager', '-q'])
    entries = [json.loads(line) for line in output.splitlines()]
    return [row['MESSAGE'] for row in entries
            if int(row['__REALTIME_TIMESTAMP']) * 1000 >= delivered_ns]


def _server_receipt(root, data, operation, pins):
    epoch, pid = _live_epoch(pins)
    receipt = _direct_child(_destination(root, data['requestId']).parent, 'receipt.json')
    if operation == 'upload':
        result = dict(_upload(data, root), epoch=epoch)
        _fill_once(receipt, _json(result))
    else:
        _require(receipt.read_bytes() == _json(data['upload']), 'receipt is not from this store')
        delivered_ns = receipt.stat().st_mtime_ns
        events = {row['runId']: _journal(row, delivered_ns) for row in data['turns']}
        result = _audit(data, root, _database(pid), events, epoch)
    _require(_live_epoch(pins) == (epoch, pid), 'service changed during operation')
    return result


def _call_request(call):
    _require(set(call) == {'kind', 'action_id', 'operation', 'input'} and call['kind'] == 'call'
             and call['operation'] in ('upload', 'audit'), 'invalid SSH call')
    return call


def _serve(pins):
    caller = os.environ.get('SUDO_UID', str(os.getuid()))
    _require(caller.isascii() and caller.isdecimal(), 'invalid SSH caller')
    directory = Path('/var/lib/kdd-vps-review')
    _require(not directory.is_symlink(), 'unsafe private storage directory')
    directory.mkdir(mode=0o700, exist_ok=True)
    root = _direct_child(directory, caller)
    root.mkdir(mode=0o700, exist_ok=True)
    call = _call_request(json.load(sys.stdin))
    result = _server_receipt(root, call['input'], call['operation'], pins)
    print(_json({'action_id': call['action_id'], 'result': result}).decode('ascii'))


def _ssh(args, pins):
    _require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.host), 'invalid SSH alias')
    call = _call_request(json.loads(Path(args.request).read_bytes()))
    program = Path(__file__).read_text(encoding='utf-8')
    remote = shlex.join(['sudo', '-n', 'python3', '-c', program, '--serve',
                         '--worker-sha256', pins[0], '--launcher-sha256', pins[1]])
    returned = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                               '-o', 'ConnectTimeout=8', args.host, remote],
                              input=_json(call), capture_output=True, timeout=60)
    if returned.returncode:
        raise ValueError('SSH proof failed: ' + returned.stderr.decode('utf-8', 'replace').strip())
    response = json.loads(returned.stdout)
    _require(set(response) == {'action_id', 'result'} and response['action_id'] == call['action_id'],
             'SSH response is not bound to the request')
    print(_json(response).decode('ascii'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host')
    parser.add_argument('--request')
    parser.add_argument('--serve', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--worker-sha256', required=True)
    parser.add_argument('--launcher-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        pins = (_digest(args.worker_sha256), _digest(args.launcher_sha256))
        if args.serve:
            _serve(pins)
        else:
            _require(args.host and args.request, 'host and request are required')
            _ssh(args, pins)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as error:
        print('REJECT VPS SSH proof: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
