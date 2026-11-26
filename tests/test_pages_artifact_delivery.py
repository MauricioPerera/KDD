"""Run the Pages readiness step against a real local artifact service."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages.yml"
READY = "Wait for uploaded Pages artifact"
NAME = "github-pages-1234-2"
ARTIFACT_ID = "5678"
ORIGIN = "https://results.example.invalid"
LIST_PATH = "/twirp/github.actions.results.api.v1.ArtifactService/ListArtifacts"
BODY = {"workflowRunBackendId": "fixture-run", "workflowJobRunBackendId": "fixture-job"}
SCOPE = "Actions.Example Actions.Results:fixture-run:fixture-job"
TOKEN = "fixture." + base64.urlsafe_b64encode(json.dumps({"scp": SCOPE}).encode()).decode().rstrip("=") + ".fixture"
MATCH = {"name": NAME, "databaseId": ARTIFACT_ID, "size": "31"}


NODE_RUNNER = r"""
const fs = require('node:fs');
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const realFetch = globalThis.fetch;
const controller = fixture.abortAt ? new AbortController() : null;
let waitSignal;
globalThis.fetch = async (input, options) => {
  const url = new URL(input);
  if (url.origin !== 'https://results.example.invalid') throw new Error('Unexpected service origin');
  if (fixture.checkDeadline && (!waitSignal || options.signal !== waitSignal))
    throw new Error('Lookup lacks the common 30-second deadline');
  const response = await realFetch(new URL(url.pathname + url.search, fixture.address), options);
  if (fixture.abortAt === 'headers') controller.abort();
  return response;
};
const realTimeout = AbortSignal.timeout;
AbortSignal.timeout = ms => {
  if (!fixture.checkDeadline || ms !== 30000) return realTimeout(ms);
  if (waitSignal) throw new Error('Lookup restarted the common deadline');
  waitSignal = controller ? controller.signal : realTimeout(ms);
  return waitSignal;
};
function requireForStep(name) {
  const module = require(name);
  if (fixture.abortAt !== 'wait' || name !== 'node:timers/promises') return module;
  return {setTimeout(ms, value, options) {
    if (options?.signal !== waitSignal) throw new Error('Retry lacks the common deadline');
    controller.abort();
    return module.setTimeout(ms, value, options);
  }};
}
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFunction('require', 'core', fixture.script);
run(requireForStep, {info: console.log, warning: console.warn}).catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
"""


@contextmanager
def service(responses):
    requests = []
    release_body = Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("Authorization"), self.headers.get_content_type(), body))
            code, payload, *hold_body = responses[min(len(requests) - 1, len(responses) - 1)]
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            try:
                self.end_headers()
                if hold_body:
                    release_body.wait()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        worker.start()
        try:
            yield "http://127.0.0.1:" + str(server.server_port), requests
        finally:
            release_body.set()
            server.shutdown()
            worker.join(timeout=2)


class PagesArtifactDelivery(unittest.TestCase):
    def setUp(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.job = workflow["jobs"]["deploy"]
        self.steps = self.job["steps"]

    def readiness(self):
        ready = [step for step in self.steps if step.get("name") == READY]
        self.assertEqual(len(ready), 1, "Pages needs exactly one artifact readiness step")
        return ready[0]

    def execute(self, responses, *, abort_at=None, origin=ORIGIN, script=None):
        if not shutil.which("node"):
            self.skipTest("Node is required by the Pages workflow")
        check_deadline = script is None
        if script is None:
            script = self.readiness()["with"]["script"]
        env = dict(os.environ, ACTIONS_RUNTIME_TOKEN=TOKEN, ACTIONS_RESULTS_URL=origin,
                   KDD_PAGES_ARTIFACT=NAME, KDD_PAGES_ARTIFACT_ID=ARTIFACT_ID)
        env.pop("NODE_OPTIONS", None)
        with service(responses) as (address, requests):
            result = subprocess.run(
                ["node", "-e", NODE_RUNNER],
                input=json.dumps(dict(address=address, script=script, abortAt=abort_at,
                                      checkDeadline=check_deadline)),
                cwd=ROOT, env=env, encoding="utf-8", capture_output=True, timeout=12,
            )
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        return result, requests

    def test_workflow_binds_upload_wait_and_deploy_to_current_attempt(self):
        ready = self.readiness()
        upload, = [step for step in self.steps if step.get("uses", "").startswith("actions/upload-pages-artifact@")]
        deploy, = [step for step in self.steps if step.get("uses", "").startswith("actions/deploy-pages@")]
        self.assertEqual(upload["uses"], "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9")
        self.assertEqual(deploy["uses"], "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346")
        name = "github-pages-${{ github.run_id }}-${{ github.run_attempt }}"
        self.assertEqual(upload["with"]["name"], name)
        self.assertEqual(deploy["with"]["artifact_name"], name)
        self.assertEqual(ready["env"]["KDD_PAGES_ARTIFACT"], name)
        self.assertNotIn("env", self.job)
        self.assertEqual(ready["env"]["KDD_PAGES_ARTIFACT_ID"],
                         "${{ steps." + upload["id"] + ".outputs.artifact_id }}")
        self.assertEqual(ready["uses"], "actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd")
        self.assertLess(self.steps.index(upload), self.steps.index(ready))
        self.assertLess(self.steps.index(ready), self.steps.index(deploy))
        for step in (upload, ready, deploy):
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("if", step)

    def test_http_fixture_serves_a_real_node_request(self):
        probe = (
            "const response = await fetch(process.env.ACTIONS_RESULTS_URL + " + json.dumps(LIST_PATH) + ", "
            "{ method: 'POST', headers: {Authorization: 'Bearer ' + process.env.ACTIONS_RUNTIME_TOKEN, "
            "'Content-Type': 'application/json'}, "
            "body: JSON.stringify(" + json.dumps(BODY) + ") }); "
            "if ((await response.json()).artifacts[0].databaseId !== process.env.KDD_PAGES_ARTIFACT_ID)"
            " throw new Error('Invalid fixture');"
        )
        result, requests = self.execute([(200, {"artifacts": [MATCH]})], script=probe)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [(LIST_PATH, "Bearer " + TOKEN, "application/json", BODY)])

    def test_artifact_becomes_visible_after_empty_and_previous_attempt(self):
        previous = dict(MATCH, name="github-pages-1234-1", databaseId="123")
        result, requests = self.execute([(200, {}), (200, {"artifacts": [previous]}),
                                         (200, {"artifacts": [previous, MATCH]})])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [(LIST_PATH, "Bearer " + TOKEN, "application/json", BODY)] * 3)

    def test_existing_exact_artifact_is_ready_on_first_request(self):
        result, requests = self.execute([(200, {"artifacts": [MATCH]})])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(requests), 1)

    def test_original_protobuf_field_name_preserves_the_upload_id(self):
        for artifact_id in (ARTIFACT_ID, int(ARTIFACT_ID)):
            with self.subTest(artifact_id=artifact_id):
                artifact = {"name": NAME, "database_id": artifact_id}
                result, requests = self.execute([(200, {"artifacts": [artifact]})])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(ARTIFACT_ID, result.stdout)
                self.assertEqual(len(requests), 1)

    def test_two_id_fields_stop_with_one_lookup(self):
        for alternative in (ARTIFACT_ID, "7890"):
            with self.subTest(alternative=alternative):
                artifact = dict(MATCH, database_id=alternative)
                result, requests = self.execute([(200, {"artifacts": [artifact]})])
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr.lower(), r"ambiguous.*\bid\b")
                self.assertEqual(len(requests), 1)

    def test_invalid_original_protobuf_id_cannot_be_accepted(self):
        for wrong in ("7890", [ARTIFACT_ID], None):
            with self.subTest(wrong=wrong):
                artifact = {"name": NAME, "database_id": wrong}
                result, requests = self.execute([(200, {"artifacts": [artifact]})])
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr.lower(), r"unexpected.*\bid\b")
                self.assertEqual(len(requests), 1)

    def test_duplicate_name_stops_with_one_lookup(self):
        result, requests = self.execute([(200, {"artifacts": [MATCH, dict(MATCH, databaseId="7890")]})])
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "duplicate|ambiguous")
        self.assertEqual(len(requests), 1)

    def test_wrong_upload_id_stops_with_one_lookup(self):
        for wrong in ("7890", [ARTIFACT_ID]):
            with self.subTest(wrong=wrong):
                result, requests = self.execute([(200, {"artifacts": [dict(MATCH, databaseId=wrong)]})])
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr.lower(), r"(expected|unexpected|mismatch).*\bid\b")
                self.assertEqual(len(requests), 1)

    def test_empty_service_eventually_times_out(self):
        result, requests = self.execute([(200, {"artifacts": []})], abort_at="wait")
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "30 s|30000|timed out")
        self.assertGreaterEqual(len(requests), 1)

    def test_deadline_aborts_a_slow_lookup_before_accepting_its_result(self):
        result, requests = self.execute([(200, {"artifacts": [MATCH]}, True)], abort_at="headers")
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "30 s|30000|timed out")
        self.assertEqual(len(requests), 1)

    def test_denied_request_fails_without_printing_response_body(self):
        result, requests = self.execute([(403, {"msg": "private-response-sentinel"})])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("403", result.stderr)
        self.assertNotIn("private-response-sentinel", result.stdout + result.stderr)
        self.assertEqual(len(requests), 1)

    def test_invalid_response_is_not_an_empty_list(self):
        result, requests = self.execute([(200, {"artifacts": {"name": NAME}})])
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "response|invalid")
        self.assertEqual(len(requests), 1)

    def test_insecure_service_is_rejected_before_any_http_request(self):
        result, requests = self.execute([(200, {"artifacts": [MATCH]})], origin=ORIGIN.replace("https:", "http:"))
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "https|tls")
        self.assertEqual(requests, [])


if __name__ == "__main__":
    unittest.main()
