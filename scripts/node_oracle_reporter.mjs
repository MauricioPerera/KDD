import { isAbsolute, relative, sep } from 'node:path';

function relativePath(file) {
  const path = relative(process.cwd(), file);
  if (!path || isAbsolute(path) || path === '..' || path.startsWith('..' + sep)) {
    throw new Error('Node oracle case location is outside the project');
  }
  return path.split(sep).join('/');
}

function registration(data) {
  const { file, line, column, name } = data;
  if (!Number.isInteger(line) || line < 1 || !Number.isInteger(column) || column < 1) {
    throw new Error('Node oracle case is missing its registration location');
  }
  return [relativePath(file), line, column, name];
}

function recordCase(event, stack, cases) {
  const { data, type } = event;
  const location = registration(data);
  if (type === 'test:start') {
    if (data.nesting !== stack.length) throw new Error('Invalid Node oracle case ancestry');
    stack.push(location);
    return;
  }
  if (data.nesting !== stack.length - 1 ||
      JSON.stringify(stack.at(-1)) !== JSON.stringify(location)) {
    throw new Error('Invalid Node oracle case ancestry');
  }
  if (type === 'test:pass' && data.details?.type === 'test') cases.push([...stack]);
  stack.pop();
}

// Emit per-file node:test summaries on stdout. Route diagnostics separately.
// A file with no registered cases has no per-file test:summary event.
export default async function* (source) {
  const recordIds = process.env.KDD_NODE_ORACLE_RECORD_IDS === '1';
  const stack = [];
  const cases = [];
  for await (const event of source) {
    if (recordIds && ['test:start', 'test:pass', 'test:fail'].includes(event.type)) {
      recordCase(event, stack, cases);
    }
    if (event.type === 'test:summary' && event.data.file) {
      const { file, success, counts } = event.data;
      const summary = { file, success, counts };
      if (recordIds) {
        if (stack.length) throw new Error('Incomplete Node oracle case ancestry');
        const owner = relativePath(file);
        summary.case_ids = cases.map(lineage => JSON.stringify([owner, lineage]));
        cases.length = 0;
      }
      yield JSON.stringify(summary) + '\n';
    } else if (event.type === 'test:stdout' || event.type === 'test:stderr') {
      process.stderr.write(event.data.message);
    } else if (event.type === 'test:fail' && event.data.details?.error) {
      const error = event.data.details.error;
      process.stderr.write(String(error.stack ?? error) + '\n');
    }
  }
  if (recordIds && (stack.length || cases.length)) throw new Error('Missing Node oracle file summary');
}
