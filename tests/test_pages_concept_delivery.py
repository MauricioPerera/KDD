"""Execute the generated concept tool with a scoped loopback origin in Node."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

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


FINALIZER = 'scripts/finalize_pages_concepts.py'
CHECK = (
    "import hashlib, os, pathlib, sys; "
    "body = pathlib.Path('scripts/finalize_pages_concepts.py').read_text(encoding='utf-8').encode('utf-8'); "
    "sys.exit(0 if hashlib.sha256(body).hexdigest() == os.environ['KDD_PAGES_FINALIZER_SHA256'] "
    "else 'Pages finalizer hash mismatch')"
)
FIXTURE_PUBLISHER = """import {appendFileSync, readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const [mode, parameter, flag] = process.argv.slice(2);
const filename = 'skills/get_concept/tool.js';
const bytes = readFileSync(filename);
const digest = createHash('sha256').update(bytes).digest('hex');
if (mode === 'publish' && parameter === '--check') {
  if (readFileSync('fixture-published-digest', 'utf8') !== digest) process.exit(4);
} else if (mode === 'publish' && !parameter) {
  writeFileSync('fixture-published-digest', digest);
} else if (mode === 'validate' && flag === '--strict') {
  const uri = new URL(filename, parameter);
  if (uri.pathname !== '/KDD/' + filename) process.exit(5);
  const response = await fetch(uri, {signal: AbortSignal.timeout(4000)});
  if (!response.ok || !Buffer.from(await response.arrayBuffer()).equals(bytes)) process.exit(6);
} else {
  process.exit(7);
}
appendFileSync('fixture-publisher-log', JSON.stringify({mode, option: flag || parameter || null, digest}) + '\\n');
"""


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
        self.build = modules['build_pages']
        self.static_files = modules['STATIC_FILES']
        publication = runpy.run_path(str(ROOT / 'scripts/finalize_pages_concepts.py'))
        self.transform = publication.get('scope_generated_concept')
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

    def test_build_and_finalization_republish_the_corrected_tool(self):
        fixture = self.output / 'source'
        fixture.mkdir()
        for name in self.static_files:
            source = ROOT / 'site' / name
            copied = fixture / 'site' / name
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copied)
        (fixture / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/process_tree.py', fixture / 'scripts/process_tree.py')
        (fixture / 'tests').mkdir()
        (fixture / 'tests/test_sample.py').write_text(
            'import unittest\nclass Sample(unittest.TestCase):\n    def test_value(self): self.assertTrue(True)\n',
            encoding='utf-8', newline='\n')
        (fixture / 'knowledge').mkdir()
        (fixture / 'knowledge/OKF-SPEC.md').write_text(SHORT_TEXT, encoding='utf-8')
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_CONFIG')}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        for args in (('init', '-q'), ('add', '--', 'knowledge/OKF-SPEC.md')):
            result = subprocess.run(['git', *args], cwd=fixture, env=env,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.output / 'build'
        published = []

        def fixture_publisher(_repo, output, *arguments):
            target = output / 'skills/get_concept/tool.js'
            if arguments[0] == 'memory':
                target.parent.mkdir(parents=True, exist_ok=True)
                content = PUBLISHER_OUTPUT.replace('"short.md":"/knowledge/short.md"',
                                                   '"OKF-SPEC.md":"/knowledge/OKF-SPEC.md"')
                target.write_text(content, encoding='utf-8', newline='\n')
            elif arguments == ('publish',):
                published.append(target.read_bytes())

        with patch.dict(self.build.__globals__, {'run_publisher': fixture_publisher}):
            self.build(str(fixture), str(destination), 'https://github.com/MauricioPerera/KDD/actions/runs/1')
        initial, = published
        publisher = fixture / 'site/node_modules/@rckflr/llms-skills/bin/llms-skills.mjs'
        publisher.parent.mkdir(parents=True)
        publisher.write_text(FIXTURE_PUBLISHER, encoding='utf-8', newline='\n')
        shutil.copyfile(ROOT / 'site/build.py', fixture / 'site/build.py')
        entry = fixture / FINALIZER
        shutil.copyfile(ROOT / FINALIZER, entry)
        result = subprocess.run([sys.executable, '-I', str(entry), '--output', str(destination)],
                                cwd=fixture, env=env, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        trace = destination / 'fixture-publisher-log'
        self.assertTrue(trace.is_file(), 'The actual finalizer CLI must publish and verify its artifact')
        events = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(event['mode'], event['option']) for event in events],
                         [('publish', None), ('publish', '--check'), ('validate', '--strict')])
        self.tool = destination / 'skills/get_concept/tool.js'
        self.transform = None
        self.assertNotEqual(initial, self.tool.read_bytes())
        final = hashlib.sha256(self.tool.read_bytes()).hexdigest()
        self.assertEqual({event['digest'] for event in events}, {final})
        result = self.get('OKF-SPEC.md')
        self.assertEqual(result['requested'], ['/KDD/knowledge/OKF-SPEC.md'], result)
        self.assertEqual(result.get('value'), {'id': 'OKF-SPEC.md', 'markdown': SHORT_TEXT}, result)


    def test_preview_and_deployment_finalize_the_same_artifacts_before_use(self):
        workflows = ROOT / '.github/workflows'
        preview = (workflows / 'validate.yml').read_text(encoding='utf-8')
        deployment = (workflows / 'deploy-pages.yml').read_text(encoding='utf-8')
        cases = (
            (preview, 'Build and validate Pages for PR', 'Finalize scoped Pages concepts for PR',
             "- name: Run each contract's test_command",
             'kdd-pages-pr-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT-$RUNNER_OS'),
            (deployment, 'Build and validate public bundle', 'Finalize scoped Pages concepts',
             'uses: actions/upload-pages-artifact@', 'kdd-pages'),
        )
        for text, build, step, next_use, directory in cases:
            with self.subTest(step=step):
                first = text.index('- name: ' + build)
                marker = '      - name: ' + step + '\n'
                self.assertIn(marker, text)
                finalization = text.index(marker)
                self.assertLess(first, finalization)
                self.assertLess(finalization, text.index(next_use, first))
                block = text[finalization:].split('\n      - ', 1)[0]
                command = 'python -I ' + FINALIZER + ' --output "$RUNNER_TEMP/' + directory + '"'
                checker = 'python -I -c "' + CHECK + '"'
                self.assertIn('        shell: bash\n', block)
                self.assertIn('        run: |\n          ' + checker + '\n          ' + command + '\n', block)
                body = (ROOT / FINALIZER).read_text(encoding='utf-8').encode('utf-8')
                digest = hashlib.sha256(body).hexdigest()
                self.assertIn('KDD_PAGES_FINALIZER_SHA256: ' + digest + '\n', block)
                self.assertIn('--output "$RUNNER_TEMP/' + directory + '"', text[first:finalization])
                for forbidden in ('continue-on-error:', '|| true', 'exit 0'):
                    self.assertNotIn(forbidden, block)
                if text is preview:
                    condition = text[first:finalization].split('if: ', 1)[1].splitlines()[0]
                    self.assertIn('if: ' + condition, block)
                else:
                    self.assertNotIn('        if:', block)
                    upload = text[text.index(next_use, finalization):].split('\n      - ', 1)[0]
                    self.assertIn('path: $' + '{{ runner.temp }}/kdd-pages', upload)

    def test_protected_finalizer_check_rejects_file_changes(self):
        entry = self.output / FINALIZER
        entry.parent.mkdir(parents=True)
        content = (ROOT / FINALIZER).read_text(encoding='utf-8')
        entry.write_text(content, encoding='utf-8', newline='\n')
        env = dict(os.environ, KDD_PAGES_FINALIZER_SHA256=hashlib.sha256(content.encode('utf-8')).hexdigest())

        def check():
            return subprocess.run([sys.executable, '-I', '-c', CHECK], cwd=self.output, env=env,
                                  capture_output=True, text=True, timeout=10)

        self.assertEqual(check().returncode, 0)
        entry.write_text(content + '\n# Different finalizer bytes\n', encoding='utf-8')
        denied = check()
        self.assertEqual(denied.returncode, 1)
        self.assertIn('Pages finalizer hash mismatch', denied.stderr)
