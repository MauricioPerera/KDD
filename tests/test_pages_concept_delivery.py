"""Execute the generated concept tool with a scoped loopback origin in Node."""
import http.server
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST_LIMIT = 4096
SHORT_TEXT = '# Short concept\n\nFixture contents.\n'
LONG_TEXT = '# Long concept\n\n' + 'a' * 5000 + '\n'
# The pinned publisher embeds an ID-to-URL JSON map and calls fetchOrigin(url).
PUBLISHER_OUTPUT = '''// Generated concept tool fixture.
var CONCEPTS = {"short.md":"/knowledge/short.md","long.md":"/knowledge/long.md"};
registerTool({
  name: "get_concept",
  handler: async function (args) {
    var url = CONCEPTS[args.id];
    if (!url) throw new Error("unknown concept id: " + args.id);
    var r = await host.fetchOrigin(url);
    if (r.status !== 200) throw new Error("fetch failed: HTTP " + r.status);
    return { id: args.id, markdown: r.body };
  }
});
'''
CLIENT = '''const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const [file, base, id, limit] = process.argv.slice(1);
let tool;
const requested = [];
const host = { async fetchOrigin(relative) {
  if (!relative.startsWith('/KDD/knowledge/')) throw Error('URL outside the publisher scope');
  requested.push(relative);
  const response = await fetch(new URL(relative, base), {signal: AbortSignal.timeout(5000)});
  const bytes = Buffer.from(await response.arrayBuffer());
  return {status: response.status, body: bytes.subarray(0, Number(limit)).toString('utf8'),
    truncated: bytes.length > Number(limit)};
}};
vm.runInNewContext(readFileSync(file, 'utf8'), {host, registerTool: value => { tool = value; }});
(async () => {
  try { console.log(JSON.stringify({value: await tool.handler({id}), requested})); }
  catch (error) { console.log(JSON.stringify({error: String(error.message), requested})); }
})();
'''


class PagesConceptDelivery(unittest.TestCase):
    def setUp(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('The real Node Pages runtime is absent from this consumer')
        self.node = node
        area = tempfile.TemporaryDirectory(prefix='kdd-concept-delivery-')
        self.addCleanup(area.cleanup)
        output = Path(area.name)
        self.tool = output / 'skills/get_concept/tool.js'
        self.tool.parent.mkdir(parents=True)
        self.tool.write_text(PUBLISHER_OUTPUT, encoding='utf-8', newline='\n')
        modules = runpy.run_path(str(ROOT / 'site/build.py'))
        self.transform = modules.get('scope_generated_concept')
        self.output = output

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                documents = {'/KDD/knowledge/short.md': SHORT_TEXT, '/KDD/knowledge/long.md': LONG_TEXT,
                             '/KDD/knowledge/OKF-SPEC.md': SHORT_TEXT}
                if self.path not in documents:
                    self.send_error(404)
                    return
                data = documents[self.path].encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args):
                pass

        service = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=service.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        self.addCleanup(thread.join, 5)
        self.addCleanup(service.server_close)
        self.addCleanup(service.shutdown)
        thread.start()
        self.base = f'http://127.0.0.1:{service.server_port}/KDD/'

    def get(self, identifier, *, prefixed=False):
        if prefixed:
            text = PUBLISHER_OUTPUT.replace('"/knowledge/', '"/KDD/knowledge/')
            self.tool.write_text(text, encoding='utf-8', newline='\n')
        if self.transform is not None:
            self.transform(self.output)
        result = subprocess.run([self.node, '-e', CLIENT, str(self.tool), self.base, identifier, str(HOST_LIMIT)],
                                capture_output=True, text=True, encoding='utf-8', timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_generated_tool_reads_concept_through_the_publisher_prefix(self):
        result = self.get('short.md')
        self.assertEqual(result.get('value'), {'id': 'short.md', 'markdown': SHORT_TEXT}, result)
        self.assertEqual(result['requested'], ['/KDD/knowledge/short.md'])

    def test_runtime_truncation_is_reported_instead_of_succeeding_with_partial_markdown(self):
        result = self.get('long.md', prefixed=True)
        self.assertIn('truncat', result.get('error', '').lower(), result)
        self.assertEqual(result['requested'], ['/KDD/knowledge/long.md'])
        self.assertNotIn('value', result)

    def test_unknown_concept_remains_a_read_free_error(self):
        result = self.get('absent.md')
        self.assertIn('unknown concept id', result['error'])
        self.assertEqual(result['requested'], [])

    def test_real_publisher_build_uses_the_scoped_tool(self):
        publisher = ROOT / 'site/node_modules/@rckflr/llms-skills/bin/llms-skills.mjs'
        if not publisher.is_file():
            self.skipTest('Install the pinned Pages publisher to exercise the real build')
        destination = self.output / 'real-build'
        runner = subprocess.run(
            [sys.executable, str(ROOT / 'site/build.py'), '--output', str(destination),
             '--ci-run-url', 'https://github.com/MauricioPerera/KDD/actions/runs/1'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(runner.returncode, 0, runner.stdout[-2000:] + runner.stderr[-2000:])
        self.tool = destination / 'skills/get_concept/tool.js'
        self.transform = None
        result = self.get('OKF-SPEC.md')
        self.assertEqual(result['requested'], ['/KDD/knowledge/OKF-SPEC.md'], result)
        self.assertEqual(result.get('value'), {'id': 'OKF-SPEC.md', 'markdown': SHORT_TEXT}, result)
