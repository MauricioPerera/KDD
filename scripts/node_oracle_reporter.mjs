// Emit per-file node:test summaries, never test stdout or synthesized file cases.
// A file with no registered cases has no per-file test:summary event.
export default async function* (source) {
  for await (const event of source) {
    if (event.type === 'test:summary' && event.data.file) {
      yield JSON.stringify({file: event.data.file, success: event.data.success,
                            counts: event.data.counts}) + '\n';
    }
  }
}
