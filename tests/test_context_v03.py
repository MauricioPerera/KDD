"""Real CLI integration tests for the explicit CCDD v0.3 profile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/context_v03.py'


def fixture(path):
    path.mkdir(parents=True)
    (path / 'env.txt').write_text('Entorno sintetico\n', encoding='utf-8', newline='\n')
    (path / 'policy.txt').write_text('No revelar datos\n', encoding='utf-8', newline='\n')
    spec = {'ccdd_version': '0.3', 'contract': {
        'name': 'synthetic-agent', 'budget': {'model': 'test', 'max_tokens': 300, 'reserve_output': 20},
        'slots': [
            {'id': 'environment', 'priority': 0, 'source': {'type': 'static', 'path': 'env.txt', 'sign': True},
             'compaction': 'none', 'min_tokens': 1},
            {'id': 'policies', 'priority': 1, 'source': {'type': 'static', 'path': 'policy.txt', 'sign': True},
             'compaction': 'none', 'min_tokens': 1, 'review_quorum': 2},
            {'id': 'state', 'priority': 2, 'source': {'type': 'dynamic', 'provider': 'synthetic_state'},
             'compaction': 'truncate', 'max_tokens': 80},
            {'id': 'user_message', 'priority': 4, 'source': {'type': 'runtime'},
             'compaction': 'truncate', 'max_tokens': 80}],
        'guardrails': [
            {'id': 'no-secrets', 'type': 'regex_deny', 'pattern': 'sk-[A-Za-z0-9]{20,}', 'on_fail': 'abort'},
            {'id': 'state-schema', 'type': 'json_schema', 'target_slot': 'state',
             'schema_path': 'state.schema.json', 'on_fail': 'abort'},
            {'id': 'references', 'type': 'reference_check', 'on_fail': 'abort'}]}}
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object',
              'required': ['tenant', 'count'], 'additionalProperties': False,
              'properties': {'tenant': {'type': 'string', 'minLength': 3},
                             'count': {'type': 'integer', 'minimum': 1}}}
    save_yaml(path, spec)
    (path / 'state.schema.json').write_text(json.dumps(schema), encoding='utf-8')
    inputs = {'state': json.dumps({'tenant': 'demo', 'count': 2}), 'user_message': 'Hola mundo'}
    (path / 'inputs.json').write_text(json.dumps(inputs), encoding='utf-8')
    sign(path, spec)
    return spec, schema, inputs


def save_yaml(path, spec):
    (path / 'context.yaml').write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
                                       encoding='utf-8', newline='\n')


def sign(path, spec):
    hashes = {}
    for slot in spec['contract']['slots']:
        src = slot['source']
        if src['type'] == 'static' and src.get('sign'):
            text = (path / src['path']).read_text(encoding='utf-8')
            hashes[slot['id']] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    (path / 'expected-hashes.json').write_text(json.dumps(hashes), encoding='utf-8')


class ContextV03Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'base'
        self.spec, self.schema, self.inputs = fixture(self.base)

    def invoke(self, *args, isolated=False):
        command = [sys.executable] + (['-S'] if isolated else []) + [str(CLI), *map(str, args)]
        result = subprocess.run(command, cwd=self.root, env=dict(os.environ, PYTHONUTF8='1'),
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f'CLI must emit JSON: {exc}; exit={result.returncode}; stderr={result.stderr!r}')
        return result, payload

    def candidate(self):
        dest = self.root / 'candidate'
        shutil.copytree(self.base, dest)
        return dest

    def assemble(self, path=None):
        path = path or self.base
        return self.invoke('assemble', path, '--inputs', path / 'inputs.json')

    def rejected(self, result, payload, code, status):
        self.assertEqual(result.returncode, code, payload)
        self.assertEqual(payload['status'], status)
        self.assertNotIn('payload', payload)

    def test_lint_real_yaml_is_read_only_and_accepts_signed_context(self):
        before = {p.name: p.read_bytes() for p in self.base.iterdir()}
        result, data = self.invoke('lint', self.base)
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        self.assertIs(data['governance_verified'], False)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.base.iterdir()})

    def test_real_assembly_is_deterministic_and_keeps_original_slot_format(self):
        result, data = self.assemble()
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        self.assertIs(data['governance_verified'], False)
        expected = ('<<environment>>\nEntorno sintetico\n\n<<policies>>\nNo revelar datos\n\n'
                    '<<state>>\n' + self.inputs['state'] + '\n\n<<user_message>>\nHola mundo')
        self.assertEqual(data['payload'], expected)
        self.assertEqual(data['payload_sha256'], hashlib.sha256(expected.encode('utf-8')).hexdigest())
        self.assertEqual(data['tokens_used'], sum((len(value) + 3) // 4 for value in (
            'Entorno sintetico', 'No revelar datos', self.inputs['state'], 'Hola mundo')))
        self.assertEqual(data['tokens_available'], 280)
        second, again = self.assemble()
        self.assertEqual(second.returncode, 0, again)
        self.assertEqual(data, again)
        self.assertFalse((self.base / 'last-assembly.json').exists())

    def test_invalid_json_schema_input_blocks_without_leaking_values(self):
        secret = 'tenant-private-demo'
        (self.base / 'inputs.json').write_text(json.dumps({'state': json.dumps({'tenant': secret, 'count': 0}),
                                                          'user_message': 'Hola'}), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_boolean_is_not_accepted_as_json_schema_integer(self):
        self.inputs['state'] = json.dumps({'tenant': 'demo', 'count': True})
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_nested_schema_array_enum_and_additional_properties(self):
        self.schema = {'type': 'object', 'required': ['channel', 'tools', 'metadata'],
                       'additionalProperties': False, 'properties': {
                           'channel': {'type': 'string', 'enum': ['WEB', 'VOICE']},
                           'tools': {'type': 'array', 'items': {'type': 'string', 'minLength': 1}},
                           'metadata': {'type': 'object', 'additionalProperties': {'type': 'string'}}}}
        (self.base / 'state.schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
        self.inputs['state'] = json.dumps({'channel': 'VOICE', 'tools': ['find'], 'metadata': {'x': 'y'}})
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        self.inputs['state'] = json.dumps({'channel': 'OTHER', 'tools': ['find'], 'metadata': {'x': 1}})
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_regex_guard_blocks_without_echoing_matched_secret(self):
        synthetic = 'sk-' + 'A' * 24
        self.inputs['user_message'] = synthetic
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')
        self.assertNotIn(synthetic, result.stdout + result.stderr)

    def test_multiple_regex_guards_are_all_executed(self):
        self.spec['contract']['guardrails'].insert(1, {'id': 'private-url', 'type': 'regex_deny',
                                                       'pattern': 'private[.]example', 'on_fail': 'abort'})
        save_yaml(self.base, self.spec)
        self.inputs['user_message'] = 'visit private.example'
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_warn_guardrail_reports_failure_without_claiming_guardrail_passed(self):
        self.spec['contract']['guardrails'][0]['on_fail'] = 'warn'
        save_yaml(self.base, self.spec)
        self.inputs['user_message'] = 'sk-' + 'B' * 24
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        guard = next(x for x in data['guardrails'] if x['id'] == 'no-secrets')
        self.assertIs(guard['passed'], False)

    def test_mutated_signed_static_is_rejected(self):
        (self.base / 'policy.txt').write_text('Changed\n', encoding='utf-8')
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_missing_hash_manifest_is_rejected(self):
        (self.base / 'expected-hashes.json').unlink()
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_unrecognized_guardrail_fails_closed(self):
        self.spec['contract']['guardrails'].append({'id': 'unknown', 'type': 'new_guard', 'on_fail': 'abort'})
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_reroute_is_rejected_instead_of_silent_fallback(self):
        self.spec['contract']['guardrails'][0]['on_fail'] = 'reroute'
        self.spec['contract']['guardrails'][0]['reroute_to'] = 'fallback'
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_duplicate_yaml_key_is_rejected(self):
        p = self.base / 'context.yaml'
        p.write_text(p.read_text(encoding='utf-8').replace('ccdd_version:', 'ccdd_version: "0.3"\nccdd_version:', 1),
                     encoding='utf-8')
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_yaml_alias_is_rejected(self):
        p = self.base / 'context.yaml'
        p.write_text(p.read_text(encoding='utf-8').replace('ccdd_version:', 'unused: &a 1\nother: *a\nccdd_version:', 1),
                     encoding='utf-8')
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_yaml_custom_tag_is_rejected(self):
        p = self.base / 'context.yaml'
        p.write_text(p.read_text(encoding='utf-8').replace('ccdd_version:', 'evil: !!python/object:danger {}\nccdd_version:', 1),
                     encoding='utf-8')
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_unknown_top_level_field_is_rejected(self):
        self.spec['unknown_security_option'] = True
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_parent_traversal_is_rejected(self):
        self.spec['contract']['slots'][0]['source']['path'] = '../outside.txt'
        (self.root / 'outside.txt').write_text('outside', encoding='utf-8')
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_real_directory_link_cannot_escape_contract(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'secret.txt').write_text('synthetic', encoding='utf-8')
        link = self.base / 'linked'
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                raise
            created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(created.returncode, 0, created.stderr)
        self.spec['contract']['slots'][0]['source']['path'] = 'linked/secret.txt'
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_other_ccdd_version_is_not_silently_accepted(self):
        self.spec['ccdd_version'] = '0.4'
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_bad_regex_is_invalid_in_lint(self):
        self.spec['contract']['guardrails'][0]['pattern'] = '['
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_missing_slot_reference_is_invalid(self):
        self.spec['contract']['guardrails'][1]['target_slot'] = 'missing'
        save_yaml(self.base, self.spec)
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_missing_dynamic_input_is_invalid(self):
        self.inputs.pop('state')
        (self.base / 'inputs.json').write_text(json.dumps(self.inputs), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 2, 'INVALID')

    def test_extra_or_wrong_typed_input_is_invalid(self):
        for inputs in ({**self.inputs, 'other': 'x'}, {**self.inputs, 'state': {'tenant': 'demo'}}):
            with self.subTest(inputs=inputs):
                (self.base / 'inputs.json').write_text(json.dumps(inputs), encoding='utf-8')
                result, data = self.assemble()
                self.rejected(result, data, 2, 'INVALID')

    def test_duplicate_json_input_is_invalid(self):
        (self.base / 'inputs.json').write_text('{"state":"one","state":"two","user_message":"x"}', encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 2, 'INVALID')

    def test_truncated_json_never_passes_schema(self):
        self.spec['contract']['slots'][2]['max_tokens'] = 2
        save_yaml(self.base, self.spec)
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_critical_slot_over_budget_blocks(self):
        self.spec['contract']['budget']['max_tokens'] = 22
        save_yaml(self.base, self.spec)
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_dynamic_slot_below_required_floor_blocks(self):
        self.spec['contract']['slots'][2]['max_tokens'] = 2
        self.spec['contract']['slots'][2]['min_tokens'] = 8
        save_yaml(self.base, self.spec)
        result, data = self.assemble()
        self.rejected(result, data, 3, 'BLOCKED')

    def test_invalid_schema_is_not_pass(self):
        self.schema['type'] = 'not-a-real-type'
        (self.base / 'state.schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_missing_schema_is_invalid(self):
        (self.base / 'state.schema.json').unlink()
        result, data = self.invoke('lint', self.base)
        self.rejected(result, data, 2, 'INVALID')

    def test_remote_schema_ref_never_contacts_server(self):
        hits = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.schema['$ref'] = 'http://127.0.0.1:' + str(server.server_port) + '/schema'
        (self.base / 'state.schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
        result, data = self.assemble()
        self.rejected(result, data, 2, 'INVALID')
        self.assertEqual(hits, [])

    def test_no_installed_dependencies_fails_closed(self):
        result, data = self.invoke('lint', self.base, isolated=True)
        self.rejected(result, data, 2, 'INVALID')

    def test_identical_diff_passes_without_claiming_verified_quorum(self):
        candidate = self.candidate()
        result, data = self.invoke('diff', self.base, candidate)
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        self.assertIs(data['governance_verified'], False)

    def test_removed_guardrail_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['guardrails'].pop(0)
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_removed_slot_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['slots'].pop()
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_changed_dynamic_provider_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][2]['source']['provider'] = 'other_provider'
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_critical_priority_degradation_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['priority'] = 3
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_critical_slot_cannot_become_compactable(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['compaction'] = 'truncate'
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_existing_static_cannot_lose_signature_requirement(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['source']['sign'] = False
        save_yaml(candidate, self.spec)
        sign(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_dynamic_slot_cannot_ascend_to_critical_priority(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][2]['priority'] = 0
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_critical_slot_floor_cannot_be_reduced(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['min_tokens'] = 0
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_existing_slot_presentation_order_cannot_change(self):
        candidate = self.candidate()
        slots = self.spec['contract']['slots']
        slots[0], slots[1] = slots[1], slots[0]
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_new_critical_signed_static_requires_review(self):
        candidate = self.candidate()
        (candidate / 'new_policy.txt').write_text('Nueva politica\n', encoding='utf-8')
        self.spec['contract']['slots'].append({'id': 'new_policy', 'priority': 1,
            'source': {'type': 'static', 'path': 'new_policy.txt', 'sign': True},
            'compaction': 'none', 'min_tokens': 1})
        save_yaml(candidate, self.spec)
        sign(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')
        self.assertIn('REVIEW_REQUIRED', data['findings'])

    def test_increased_quorum_is_allowed_without_claiming_verified_signatures(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['review_quorum'] = 3
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')
        self.assertIs(data['governance_verified'], False)

    def test_adding_a_guardrail_is_allowed_when_existing_controls_are_preserved(self):
        candidate = self.candidate()
        self.spec['contract']['guardrails'].append({'id': 'extra', 'type': 'regex_deny',
                                                     'pattern': 'secret-extra', 'on_fail': 'abort'})
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.assertEqual(result.returncode, 0, data)
        self.assertEqual(data['status'], 'PASS')

    def test_weaker_guardrail_action_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['guardrails'][0]['on_fail'] = 'warn'
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_changed_regex_is_not_assumed_equivalent(self):
        candidate = self.candidate()
        self.spec['contract']['guardrails'][0]['pattern'] = 'never-match'
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_schema_content_change_is_blocked(self):
        candidate = self.candidate()
        self.schema['properties']['count']['minimum'] = 0
        (candidate / 'state.schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_signed_static_change_requires_review_even_with_new_hash(self):
        candidate = self.candidate()
        (candidate / 'policy.txt').write_text('Una politica nueva\n', encoding='utf-8')
        sign(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')
        self.assertIn('REVIEW_REQUIRED', data['findings'])

    def test_review_quorum_decrease_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['slots'][1]['review_quorum'] = 1
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_budget_reduction_is_blocked(self):
        candidate = self.candidate()
        self.spec['contract']['budget']['max_tokens'] = 250
        save_yaml(candidate, self.spec)
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')

    def test_registry_change_cannot_be_accepted_without_signature_verification(self):
        candidate = self.candidate()
        (candidate / 'reviewers.json').write_text('{"reviewer":"synthetic"}', encoding='utf-8')
        result, data = self.invoke('diff', self.base, candidate)
        self.rejected(result, data, 3, 'BLOCKED')


class ContextV03CIIntegration(unittest.TestCase):
    def test_dependency_lock_is_pinned_with_hashes(self):
        lock = ROOT / 'tools/context-v03/requirements.txt'
        lines = [line.strip() for line in lock.read_text(encoding='ascii').splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        self.assertTrue(lines)
        for line in lines:
            self.assertIn('==', line)
            self.assertIn('--hash=sha256:', line)
        names = {line.split('==', 1)[0].lower() for line in lines}
        self.assertTrue({'pyyaml', 'jsonschema', 'referencing', 'rpds-py'} <= names)

    def test_real_workflow_installs_locked_dependencies_before_contracts_and_suites(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8'))
        job = workflow['jobs']['validate']
        self.assertEqual(job['strategy']['matrix']['os'], ['ubuntu-latest', 'windows-latest'])
        steps = job['steps']
        names = [step.get('name') for step in steps]
        self.assertIn('Install pinned context compatibility dependencies', names)
        installation = names.index('Install pinned context compatibility dependencies')
        for name in ("Run each contract's test_command", 'Run unit tests (1/2)', 'Run unit tests (2/2)'):
            self.assertLess(installation, names.index(name))
        step = steps[installation]
        self.assertNotIn('if', step)
        command = step['run']
        for required in ('--require-hashes', '--only-binary=:all:', 'tools/context-v03/requirements.txt'):
            self.assertIn(required, command)


if __name__ == '__main__':
    unittest.main()
