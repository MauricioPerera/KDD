import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

// The existing receiver verifies the signature and subscription before emitting event.received.
// An authenticated SSH stream avoids installing a second receiver or changing the active one.
export function followReceiver(host, threadId, record) {
  const service = 'agent-mcp-federation-receiver.service';
  const worker = 'agent-mcp-federation-worker.service';
  const command = 'printf "journal.ready\\n"; exec sudo -n journalctl --no-pager --follow --no-tail ' +
    `--since="10 seconds ago" --output=json --grep=${threadId}`;
  const ssh = spawn('ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', host, command],
    { stdio: ['ignore', 'pipe', 'inherit'] });
  const lines = createInterface({ input: ssh.stdout });
  const buffered = [];
  let waiting;
  let closed;

  function check() {
    if (!waiting) return;
    const event = buffered.find(waiting.match);
    if (!event && !closed) return;
    const { resolve, reject, timer } = waiting;
    waiting = undefined;
    clearTimeout(timer);
    if (event) resolve(event);
    else reject(closed);
  }

  function stopped(error) {
    closed = error;
    check();
  }

  ssh.once('error', stopped);
  ssh.once('close', code => stopped(Error(`SSH journal ended with exit ${code}`)));
  lines.on('line', line => {
    if (line === 'journal.ready') {
      buffered.push({ event: line });
      check();
      return;
    }
    let row;
    let event;
    try {
      row = JSON.parse(line);
      event = JSON.parse(row.MESSAGE);
    } catch {
      return;
    }
    if (event.threadId !== threadId || !/^evt_[a-f0-9]{32}$/.test(event.eventId)) return;
    const unit = row._SYSTEMD_UNIT;
    const trusted = unit === service || unit === worker;
    // The service owns callback observations. Other units can only attest to agent execution.
    const fromTurn = row._SYSTEMD_USER_UNIT?.startsWith('agent-mcp-federation-turn@');
    if (!trusted && !fromTurn) return;
    if (['event.received', 'runner.ack'].includes(event.event) && unit !== service) return;
    if (!['event.received', 'runner.ack', 'agent.started', 'agent.completed', 'agent.failed'].includes(event.event)) return;
    const fields = ['at', 'event', 'agent', 'name', 'eventId', 'peerId', 'taskId', 'threadId',
      'duplicate', 'runtime', 'status', 'tools'];
    const safe = Object.fromEntries(fields.filter(key => key in event).map(key => [key, event[key]]));
    buffered.push(safe);
    record(safe);
    check();
  });

  return {
    waitFor(match, label, timeoutMs = 220_000) {
      return new Promise((resolve, reject) => {
        if (waiting) return reject(Error('Only one journal observation may be pending'));
        const timer = setTimeout(() => {
          waiting = undefined;
          reject(Error('Timed out waiting for ' + label));
        }, timeoutMs);
        waiting = { match, timer, resolve, reject };
        check();
      });
    },
    close() {
      lines.close();
      ssh.kill();
    },
  };
}

export function callbackMatch(target, name) {
  return row => row.event === 'event.received' && row.duplicate === false &&
    row.name === name && row.agent === target.agent && row.peerId === target.peerId &&
    row.taskId === target.taskId && row.threadId === target.threadId;
}
