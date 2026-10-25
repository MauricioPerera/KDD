"""Real task closure, imported journals, drift and evidence mutations."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest
from tests import test_traceability_model as support


class TraceabilityGitTests(support.RepositoryFixture):
    def trace(self, ref='main', require_verified=False, manifest='quality/traceability.json'):
        try:
            return importlib.import_module('traceability_git').build_trace(
                self.root, ref, manifest, require_verified=require_verified)
        except NotImplementedError as error:
            self.fail('Traceability interface is not implemented: ' + str(error))

    def row(self, report, identifier='REQ-001'):
        return next(r for r in report['requirements'] if r['id'] == identifier)

    def require_failure(self, report, code):
        self.assertIs(report['ok'], False)
        self.assertIs(report['complete'], False)
        self.assertTrue(any(f['code'].startswith(code) for f in report['findings']), report['findings'])

    def node(self):
        model = importlib.import_module('task_model')
        path = self.root / 'knowledge/tasks/TASK-001.md'
        data, body = model.parse_task(path.read_text(encoding='utf-8'), 'knowledge/tasks/TASK-001.md')
        return model, path, data, body

    def test_real_completed_chain_keeps_original_refs_and_evidence(self):
        report = self.trace(require_verified=True)
        self.assertTrue(report['ok'])
        self.assertTrue(report['complete'])
        self.assertEqual(report['observed_commit'], self.refs['closed'])
        link = self.row(report)['links'][0]
        self.assertEqual(link['state'], 'verified')
        self.assertTrue(link['historical_verified'])
        self.assertEqual(link['task_id'], 'TASK-001')
        self.assertEqual(link['approved_ref'], self.refs['approved'])
        self.assertEqual(link['tested_commit'], self.refs['tested'])
        self.assertEqual(link['branch_tip'], self.refs['tip'])
        self.assertEqual(link['contract'], 'knowledge/contracts/value.md')
        self.assertEqual(link['oracle'], 'tests/test_value.py')
        self.assertEqual(link['target'], 'src/value.py')
        raw = (self.root / link['evidence']).read_bytes()
        self.assertEqual(link['evidence_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(json.loads(raw)['passed_tests'], 2)

    def test_selected_commit_ignores_other_branch_and_dirty_product(self):
        support.git(self.root, 'switch', '-q', '-c', 'unrelated-work')
        support.write(self.root, 'src/value.py', 'raise RuntimeError("do not execute dirty product")\n')
        support.write(self.root, 'tests/test_value.py', 'from pathlib import Path\nPath("unexpected-execution").write_text("bad")\n')
        before = support.git(self.root, 'status', '--porcelain=v1')
        report = self.trace()
        self.assertTrue(report['ok'])
        self.assertEqual(report['observed_commit'], self.refs['closed'])
        self.assertEqual(before, support.git(self.root, 'status', '--porcelain=v1'))
        self.assertEqual(support.git(self.root, 'branch', '--show-current'), 'unrelated-work')
        self.assertFalse((self.root / 'unexpected-execution').exists())

    def test_target_drift_is_stale_while_old_revision_remains_verified(self):
        support.write(self.root, 'src/value.py', support.IMPLEMENTATION + '\n# later implementation revision\n')
        changed = support.commit(self.root, 'later target revision')
        current = self.trace()
        self.require_failure(current, 'TRACE_STALE')
        self.assertEqual(current['observed_commit'], changed)
        self.assertTrue(self.row(current)['links'][0]['historical_verified'])
        old = self.trace(ref=self.refs['closed'])
        self.assertTrue(old['complete'])
        self.assertEqual(old['observed_commit'], self.refs['closed'])

    def test_oracle_and_contract_resealing_does_not_refresh_old_proof(self):
        oracle = (self.root / 'tests/test_value.py').read_text(encoding='utf-8')
        changed = oracle + '\n# a new oracle revision\n'
        support.write(self.root, 'tests/test_value.py', changed)
        contract = (self.root / 'knowledge/contracts/value.md').read_text(encoding='utf-8')
        contract = contract.replace(hashlib.sha256(oracle.encode()).hexdigest(), hashlib.sha256(changed.encode()).hexdigest())
        support.write(self.root, 'knowledge/contracts/value.md', contract)
        support.commit(self.root, 'different resealed oracle and contract')
        self.require_failure(self.trace(), 'TRACE_STALE')

    def test_requirement_text_drift_is_not_covered_by_old_task(self):
        support.write(self.root, 'knowledge/product-spec.md', support.SPEC.replace('Return seven', 'Return eight'))
        support.commit(self.root, 'changed requirement after approval')
        report = self.trace()
        self.require_failure(report, 'TRACE_STALE')
        self.assertTrue(self.row(report)['links'][0]['historical_verified'])

    def test_changed_own_bindings_invalidate_old_requirement_fingerprint(self):
        plan = self.plan()
        plan['bindings'][0]['tasks'].append('TASK-002')
        self.save_plan(plan)
        self.require_failure(self.trace(), 'TRACE_STALE')

    def test_unrelated_requirement_preserves_existing_verified_link(self):
        plan = self.plan()
        plan['bindings'].append(dict(requirement='REQ-002', contract='knowledge/contracts/value.md', tasks=[]))
        support.write(self.root, 'knowledge/product-spec.md', support.SPEC.replace('## Contexto', '- [REQ-002] A future independent outcome.\n\n## Contexto'))
        self.save_plan(plan)
        report = self.trace()
        self.assertTrue(report['ok'])
        self.assertFalse(report['complete'])
        self.assertEqual(self.row(report)['state'], 'verified')
        self.assertEqual(self.row(report, 'REQ-002')['state'], 'pending')
        self.require_failure(self.trace(require_verified=True), 'TRACE_PENDING')

    def test_new_requirement_cannot_reuse_a_previously_approved_task(self):
        plan = self.plan()
        plan['bindings'].append(dict(requirement='REQ-002', contract='knowledge/contracts/value.md', tasks=['TASK-001']))
        support.write(self.root, 'knowledge/product-spec.md', support.SPEC.replace('## Contexto', '- [REQ-002] A newly defined obligation.\n\n## Contexto'))
        self.save_plan(plan)
        report = self.trace()
        self.require_failure(report, 'TRACE_STALE')
        self.assertEqual(self.row(report)['state'], 'verified')
        self.assertEqual(self.row(report, 'REQ-002')['state'], 'stale')

    def test_missing_future_task_is_pending_and_strict_mode_rejects_it(self):
        plan = self.plan()
        plan['bindings'][0]['tasks'] = ['TASK-999']
        self.save_plan(plan)
        report = self.trace()
        self.assertTrue(report['ok'])
        self.assertFalse(report['complete'])
        self.assertEqual(self.row(report)['state'], 'pending')
        link = self.row(report)['links'][0]
        self.assertEqual(link['tested_commit'], '')
        self.assertFalse(link['historical_verified'])
        self.require_failure(self.trace(require_verified=True), 'TRACE_PENDING')

    def test_evidence_changed_without_reseal_is_rejected(self):
        _, _, task, _ = self.node()
        path = self.root / task['evidence']
        support.write(self.root, task['evidence'], path.read_text(encoding='utf-8') + '\n')
        support.commit(self.root, 'tampered evidence bytes')
        self.require_failure(self.trace(), 'TRACE_JOURNAL')

    def test_evidence_and_node_reseal_cannot_hide_illegal_done_mutation(self):
        model, path, task, body = self.node()
        data = json.loads((self.root / task['evidence']).read_text(encoding='utf-8'))
        data['stdout'] += 'Extra forged diagnostic output\n'
        data['output_sha256'] = hashlib.sha256((data['stdout'] + data['stderr']).encode()).hexdigest()
        raw = support.dump(data)
        support.write(self.root, task['evidence'], raw)
        task['evidence_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
        path.write_text(model.render_task(task, body), encoding='utf-8')
        support.commit(self.root, 'resealed done node and evidence')
        errors = importlib.import_module('validate_tasks').validate_snapshot(self.root, 'main')
        self.assertEqual(errors, [], 'Mutation must retain a valid snapshot to exercise history')
        self.require_failure(self.trace(), 'TRACE_JOURNAL')

    def test_invalid_intermediate_transition_is_not_hidden_by_valid_tip(self):
        model, path, task, body = self.node()
        original = path.read_text(encoding='utf-8')
        task.update(status='ready', verified_ref='', evidence='', evidence_sha256='', reason='forged reopen')
        path.write_text(model.render_task(task, body), encoding='utf-8')
        support.commit(self.root, 'invalid intermediate reopen')
        path.write_text(original, encoding='utf-8')
        support.commit(self.root, 'restore valid-looking final node')
        self.assertEqual(importlib.import_module('validate_tasks').validate_snapshot(self.root, 'main'), [])
        self.require_failure(self.trace(), 'TRACE_JOURNAL')

    def test_imported_journal_preserves_source_commits_and_proof(self):
        support.git(self.root, 'switch', '-q', '-c', 'publication-target', self.refs['approved'])
        support.git(self.root, 'merge', '--no-ff', '-qm', 'import original journal', 'main')
        merged = support.git(self.root, 'rev-parse', 'HEAD')
        report = self.trace(ref='HEAD', require_verified=True)
        self.assertTrue(report['ok'])
        self.assertEqual(report['observed_commit'], merged)
        self.assertEqual(self.row(report)['links'][0]['tested_commit'], self.refs['tested'])
        self.assertEqual(self.row(report)['links'][0]['branch_tip'], self.refs['tip'])
        self.assertEqual(report['audit_base'], self.refs['approved'])

    def test_unrelated_later_commit_keeps_only_declared_scope_verified(self):
        support.write(self.root, 'notes.txt', 'Unrelated note, not covered product code.\n')
        latest = support.commit(self.root, 'unrelated documentation')
        report = self.trace(require_verified=True)
        self.assertTrue(report['ok'])
        self.assertEqual(report['observed_commit'], latest)
        self.assertEqual(self.row(report)['links'][0]['tested_commit'], self.refs['tested'])
        self.assertNotEqual(latest, self.refs['tested'])

    def test_git_symlink_mode_is_rejected_without_following_it(self):
        target = 'quality/traceability.json'
        oid = support.git(self.root, 'hash-object', '-w', '--stdin', input='outside.json\n')
        support.git(self.root, 'update-index', '--cacheinfo', '120000,' + oid + ',' + target)
        support.git(self.root, 'commit', '-qm', 'linked manifest object')
        self.assertTrue(support.git(self.root, 'ls-tree', 'HEAD', '--', target).startswith('120000'))
        self.require_failure(self.trace(), 'TRACE_INPUT')

    def test_missing_git_history_is_explicit_failure(self):
        shallow = Path(self.temp.name) / 'shallow'
        support.git(Path(self.temp.name), 'clone', '-q', '--no-local', '--depth', '1', str(self.base), str(shallow))
        self.assertEqual(support.git(shallow, 'rev-parse', '--is-shallow-repository'), 'true')
        original = self.root
        self.root = shallow
        try:
            report = self.trace(require_verified=True)
        finally:
            self.root = original
        self.assertFalse(report['ok'])
        self.assertFalse(report['complete'])
        self.assertTrue(report['findings'])

    def test_bad_ref_missing_manifest_and_path_escape_are_errors(self):
        for options in [dict(ref='missing-branch'), dict(manifest='quality/absent.json'), dict(manifest='../outside.json')]:
            with self.subTest(options=options):
                report = self.trace(**options)
                self.assertFalse(report['ok'])
                self.assertFalse(report['complete'])
                self.assertTrue(any(f['code'] in ('TRACE_INPUT', 'TRACE_GIT') for f in report['findings']))


if __name__ == '__main__':
    unittest.main()
