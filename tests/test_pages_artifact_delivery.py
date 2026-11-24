"""Run the Pages readiness step against a real local artifact service."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread
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
globalThis.fetch = (input, options) => {
  const url = new URL(input);
  if (url.origin !== 'https://results.example.invalid') throw new Error('Unexpected service origin');
  return realFetch(new URL(url.pathname + url.search, fixture.address), options);
};
// Shorten the test's real wall-clock deadline while checking the production bound.
const realTimeout = AbortSignal.timeout;
AbortSignal.timeout = ms => realTimeout(ms === 30000 ? fixture.deadline : ms);
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFunction('require', 'core', fixture.script);
run(require, {info: console.log, warning: console.warn}).catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
"""


@contextmanager
def service(responses):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("Authorization"), body))
            code, payload = responses[min(len(requests) - 1, len(responses) - 1)]
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        worker.start()
        try:
            yield "http://127.0.0.1:" + str(server.server_port), requests
        finally:
            server.shutdown()
            worker.join(timeout=2)


@unittest.skipUnless(shutil.which("node"), "Node is required by the Pages workflow")
class PagesArtifactDelivery(unittest.TestCase):
    def setUp(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.job = workflow["jobs"]["deploy"]
        self.steps = self.job["steps"]

    def readiness(self):
        ready = [step for step in self.steps if step.get("name") == READY]
        self.assertEqual(len(ready), 1, "Pages needs exactly one artifact readiness step")
        return ready[0]

    def execute(self, responses, *, deadline=5000, origin=ORIGIN, script=None):
        if script is None:
            script = self.readiness()["with"]["script"]
        env = dict(os.environ, ACTIONS_RUNTIME_TOKEN=TOKEN, ACTIONS_RESULTS_URL=origin,
                   KDD_PAGES_ARTIFACT=NAME, KDD_PAGES_ARTIFACT_ID=ARTIFACT_ID)
        env.pop("NODE_OPTIONS", None)
        with service(responses) as (address, requests):
            result = subprocess.run(
                ["node", "-e", NODE_RUNNER],
                input=json.dumps(dict(address=address, script=script, deadline=deadline)),
                cwd=ROOT, env=env, encoding="utf-8", capture_output=True, timeout=12,
            )
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        return result, requests

    def test_workflow_binds_upload_wait_and_deploy_to_current_attempt(self):
        ready = self.readiness()
        upload, = [step for step in self.steps if step.get("uses", "").startswith("actions/upload-pages-artifact@")]
        deploy, = [step for step in self.steps if step.get("uses", "").startswith("actions/deploy-pages@")]
        self.assertEqual(self.job["env"]["KDD_PAGES_ARTIFACT"],
                         "github-pages-${{ github.run_id }}-${{ github.run_attempt }}")
        shared_name = "${{ env.KDD_PAGES_ARTIFACT }}"
        self.assertEqual(upload["with"]["name"], shared_name)
        self.assertEqual(deploy["with"]["artifact_name"], shared_name)
        self.assertNotIn("KDD_PAGES_ARTIFACT", ready["env"])
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
            "{ method: 'POST', headers: {Authorization: 'Bearer ' + process.env.ACTIONS_RUNTIME_TOKEN}, "
            "body: JSON.stringify(" + json.dumps(BODY) + ") }); "
            "if ((await response.json()).artifacts[0].databaseId !== process.env.KDD_PAGES_ARTIFACT_ID)"
            " throw new Error('Invalid fixture');"
        )
        result, requests = self.execute([(200, {"artifacts": [MATCH]})], script=probe)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [(LIST_PATH, "Bearer " + TOKEN, BODY)])

    def test_artifact_becomes_visible_after_empty_and_previous_attempt(self):
        previous = dict(MATCH, name="github-pages-1234-1", databaseId="123")
        result, requests = self.execute([(200, {}), (200, {"artifacts": [previous]}),
                                         (200, {"artifacts": [previous, MATCH]})])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(requests, [(LIST_PATH, "Bearer " + TOKEN, BODY)] * 3)

    def test_existing_exact_artifact_is_ready_on_first_request(self):
        result, requests = self.execute([(200, {"artifacts": [MATCH]})])
        self.assertEqual(result.returncode, 0, result.stderr)
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
        result, requests = self.execute([(200, {"artifacts": []})], deadline=350)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), "30 s|30000|timed out")
        self.assertGreaterEqual(len(requests), 1)

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
