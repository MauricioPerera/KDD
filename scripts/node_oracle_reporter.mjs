// Emit per-file node:test summaries on stdout. Route diagnostics separately.
// A file with no registered cases has no per-file test:summary event.
export default async function* (source) {
  for await (const event of source) {
    if (event.type === 'test:summary' && event.data.file) {
      yield JSON.stringify({file: event.data.file, success: event.data.success,
                            counts: event.data.counts}) + '\n';
    } else if (event.type === 'test:stdout' || event.type === 'test:stderr') {
      process.stderr.write(event.data.message);
    } else if (event.type === 'test:fail' && event.data.details?.error) {
      const error = event.data.details.error;
      process.stderr.write(String(error.stack ?? error) + '\n');
    }
  }
}
