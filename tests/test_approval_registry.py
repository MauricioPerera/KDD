"""Real Git trees, independent baselines and fail-closed external selection."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import approval_registry as registry
from validate_baseline import validate_all_baselines


class GitApprovalFixture:
    @classmethod
    def setUpClass(cls):
        case = tempfile.TemporaryDirectory(prefix='kdd approval \u00f1 ')
        cls.addClassCleanup(case.cleanup)
        cls.root = Path(case.name) / 'repo'
        cls.root.mkdir()
        cls.command('git', 'init', '-q', '--initial-branch=main')
        for key, value in [('user.name', 'Approval fixture'),
                           ('user.email', 'fixture@example.invalid'),
                           ('commit.gpgsign', 'false'), ('core.autocrlf', 'false'),
                           ('maintenance.autoDetach', 'false'), ('gc.autoDetach', 'false')]:
            cls.command('git', 'config', key, value)
        cls.refs = {}
        cls.trees = {}
        cls.write_version('main')
        cls.refs['main'] = cls.commit('main baseline')
        for branch in ('one', 'two'):
            cls.command('git', 'checkout', '-qb', branch, cls.refs['main'])
            cls.write_version(branch)
            cls.refs[branch] = cls.commit(branch + ' independently reviewed baseline')
        cls.command('git', 'checkout', '-qb', 'integration', cls.refs['main'])
        cls.command('git', 'merge', '--no-ff', '-qm', 'merge proposal one', cls.refs['one'])
        cls.refs['merge'] = cls.command('git', 'rev-parse', 'HEAD')
        cls.command('git', 'checkout', '-qb', 'poison', cls.refs['one'])
        cls.write('scripts/approval_registry.py',
                  'from pathlib import Path\nPath("candidate-executed").write_text("unsafe")\n')
        cls.write('kdd-approval-registry.json', '{"candidate_wants":"self approval"}\n')
        cls.refs['poison'] = cls.commit('candidate-owned approval files')
        cls.command('git', 'checkout', '-qb', 'shadow', cls.refs['one'])
        cls.write('approval_registry.py', 'raise RuntimeError("candidate import executed")\n')
        cls.refs['shadow'] = cls.commit('candidate import shadow')
        cls.command('git', 'checkout', '-q', 'main')
        for name, ref in cls.refs.items():
            cls.trees[name] = cls.command('git', 'rev-parse', ref + '^{tree}')

    @classmethod
    def command(cls, *args, cwd=None, env=None):
        result = subprocess.run(list(args), cwd=cwd or cls.root, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=60)
        if result.returncode:
            raise RuntimeError('Fixture precondition failed: ' + repr(args) + '\n' + result.stderr)
        return result.stdout.strip()

    @classmethod
    def write(cls, relative, text):
        path = cls.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    @classmethod
    def write_version(cls, version):
        cls.write('app.py', 'def answer():\n    return ' + repr(version) + '\n')
        oracle = ('import unittest\nimport app\nclass Oracle(unittest.TestCase):\n'
                  '    def test_answer(self):\n        self.assertEqual(app.answer(), ' + repr(version) + ')\n')
        cls.write('tests/__init__.py', '')
        cls.write('tests/oracle.py', oracle)
        seal = hashlib.sha256(oracle.encode()).hexdigest()
        cls.write('knowledge/contracts/app.md',
            "---\ntype: 'Task Contract'\ntitle: 'Fixture'\ndescription: 'Real baseline fixture'\n"
            "tags: ['testing']\ntask: fixture\nintent: 'Return the approved answer'\n"
            "target: app.py\nsignature: 'def answer():'\ntest_command: 'python -m unittest tests/oracle.py'\n"
            "budget:\n  cyclomatic_max: 2\n  nesting_max: 2\ntests: tests/oracle.py\n"
            "tests_sha256: '" + seal + "'\ntouch_only: ['app.py']\ndeps_allowed: ['stdlib']\n"
            "forbids: ['network', 'llm']\n---\n" +
            ''.join('## ' + section + '\nFixture.\n\n' for section in
                    ('Intent', 'Interface', 'Invariants', 'Examples', 'Do / Don\'t', 'Tests', 'Constraints')))

    @classmethod
    def commit(cls, message):
        cls.command('git', 'add', '-A')
        cls.command('git', 'commit', '-qm', message)
        return cls.command('git', 'rev-parse', 'HEAD')

    def records(self):
        return {'schema_version': 1, 'trees': {
            self.trees[name]: {'baseline_ref': self.refs[name]} for name in ('main', 'one', 'two')}}

    def resolved(self, candidate='main', data=None, **kwargs):
        try:
            return registry.resolve(self.root, self.refs[candidate],
                                    json.dumps(self.records() if data is None else data), **kwargs)
        except registry.ApprovalError as exc:
            self.fail('Approved selection unexpectedly failed: ' + str(exc))


class TestApprovalRegistry(GitApprovalFixture, unittest.TestCase):
    def test_main_uses_its_own_approved_entry(self):
        result = self.resolved()
        self.assertEqual(result['candidate_commit'], self.refs['main'])
        self.assertEqual(result['candidate_tree'], self.trees['main'])
        self.assertEqual(result['baseline_ref'], self.refs['main'])
        self.assertIsNone(result['quality_ref'])
        self.assertEqual(result['source'], 'registry')

    def test_two_proposals_and_main_keep_independent_references(self):
        before = self.command('git', 'show-ref')
        for name in ('two', 'main', 'one', 'main', 'two'):
            self.assertEqual(self.resolved(name)['baseline_ref'], self.refs[name])
        self.assertEqual(self.command('git', 'show-ref'), before)
        self.assertEqual(self.command('git', 'status', '--porcelain'), '')

    def test_real_merge_reuses_the_proposal_tree_entry(self):
        self.assertNotEqual(self.refs['merge'], self.refs['one'])
        self.assertEqual(self.trees['merge'], self.trees['one'])
        result = self.resolved('merge')
        self.assertEqual(result['candidate_commit'], self.refs['merge'])
        self.assertEqual(result['baseline_ref'], self.refs['one'])

    def test_candidate_ref_is_read_without_checking_it_out(self):
        before = self.command('git', 'rev-parse', 'HEAD')
        self.assertEqual(self.resolved('two')['candidate_tree'], self.trees['two'])
        self.assertEqual(self.command('git', 'rev-parse', 'HEAD'), before)
        self.assertEqual((self.root / 'app.py').read_text(), "def answer():\n    return 'main'\n")

    def test_wrong_registry_reference_is_rejected_by_real_baseline_comparison(self):
        records = self.records()
        records['trees'][self.trees['one']]['baseline_ref'] = self.refs['main']
        result = self.resolved('one', records)
        self.command('git', 'checkout', '-q', 'one')
        try:
            findings = validate_all_baselines(result['baseline_ref'], self.root)
            self.assertTrue(any('tests/oracle.py' in f and 'differs' in f for f in findings), findings)
            self.assertEqual(validate_all_baselines(self.refs['one'], self.root), [])
        finally:
            self.command('git', 'checkout', '-q', 'main')

    def test_quality_reference_is_separate_and_can_be_required(self):
        records = self.records()
        records['trees'][self.trees['one']]['quality_ref'] = self.refs['main']
        result = self.resolved('one', records, require_quality=True)
        self.assertEqual(result['baseline_ref'], self.refs['one'])
        self.assertEqual(result['quality_ref'], self.refs['main'])

    def test_unpublished_reference_in_another_entry_cannot_invalidate_main(self):
        records = self.records()
        records['trees']['2' * 40] = {'baseline_ref': '1' * 40}
        self.assertEqual(self.resolved('main', records)['baseline_ref'], self.refs['main'])

    def test_missing_required_quality_fails(self):
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_QUALITY'):
            registry.resolve(self.root, self.refs['one'], json.dumps(self.records()), require_quality=True)

    def test_missing_approval_never_defaults_to_head(self):
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_REQUIRED'):
            registry.resolve(self.root, 'HEAD', '')

    def test_unknown_tree_does_not_use_legacy_global_environment(self):
        previous = os.environ.get('KDD_APPROVED_BASELINE_REF')
        os.environ['KDD_APPROVED_BASELINE_REF'] = self.refs['poison']
        try:
            with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_UNKNOWN_TREE'):
                registry.resolve(self.root, self.refs['poison'], json.dumps(self.records()))
        finally:
            if previous is None:
                os.environ.pop('KDD_APPROVED_BASELINE_REF', None)
            else:
                os.environ['KDD_APPROVED_BASELINE_REF'] = previous

    def test_malformed_json_is_rejected(self):
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_JSON'):
            registry.resolve(self.root, 'HEAD', '{broken')

    def test_duplicate_json_keys_are_rejected(self):
        tree, ref = self.trees['main'], self.refs['main']
        raw = '{"schema_version":1,"trees":{"' + tree + '":{"baseline_ref":"' + ref + '"},"' + tree + '":{"baseline_ref":"' + ref + '"}}}'
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_JSON'):
            registry.resolve(self.root, 'HEAD', raw)

    def test_case_normalization_collisions_are_rejected(self):
        records = self.records()
        records['trees'][self.trees['main'].upper()] = {'baseline_ref': self.refs['main']}
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_SCHEMA'):
            registry.resolve(self.root, 'HEAD', json.dumps(records))

    def test_version_and_unknown_fields_are_rejected(self):
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'extra': 1}):
            data = self.records();data.update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_SCHEMA'):
                registry.resolve(self.root, 'HEAD', json.dumps(data))

    def test_aliases_and_invalid_reference_types_are_rejected(self):
        for ref in ('HEAD', 'main', 'abc', True, None, 'a' * 41):
            records = self.records();records['trees'][self.trees['main']]['baseline_ref'] = ref
            with self.subTest(ref=ref), self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_SHA'):
                registry.resolve(self.root, 'HEAD', json.dumps(records))

    def test_nonexistent_commit_reference_is_rejected(self):
        records = self.records();records['trees'][self.trees['main']]['baseline_ref'] = '0' * 40
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_REF'):
            registry.resolve(self.root, 'HEAD', json.dumps(records))

    def test_tree_object_cannot_be_an_approved_commit(self):
        records = self.records();records['trees'][self.trees['main']]['baseline_ref'] = self.trees['main']
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_REF'):
            registry.resolve(self.root, 'HEAD', json.dumps(records))

    def test_explicit_caller_mode_preserves_full_reviewed_references(self):
        try:
            result = registry.resolve(self.root, self.refs['one'], '',
                                      explicit_baseline=self.refs['one'], explicit_quality=self.refs['main'])
        except registry.ApprovalError as exc:
            self.fail(str(exc))
        self.assertEqual(result['source'], 'explicit')
        self.assertEqual(result['baseline_ref'], self.refs['one'])
        self.assertEqual(result['quality_ref'], self.refs['main'])

    def test_explicit_and_registry_modes_cannot_be_mixed(self):
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_AMBIGUOUS'):
            registry.resolve(self.root, 'HEAD', json.dumps(self.records()), explicit_baseline=self.refs['main'])

    def test_explicit_mode_also_requires_a_full_baseline_sha(self):
        for ref in ('HEAD', 'main', 'abc'):
            with self.subTest(ref=ref), self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_SHA'):
                registry.resolve(self.root, 'HEAD', '', explicit_baseline=ref)
        with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_REQUIRED'):
            registry.resolve(self.root, 'HEAD', '', explicit_quality=self.refs['main'])

    def test_invalid_registry_structure_and_tree_keys_are_rejected(self):
        for trees, code in (({}, 'APPROVAL_SCHEMA'), ([], 'APPROVAL_SCHEMA'),
                            ({'HEAD': {'baseline_ref': self.refs['main']}}, 'APPROVAL_SHA'),
                            ({self.trees['main']: []}, 'APPROVAL_SCHEMA'),
                            ({self.trees['main']: {}}, 'APPROVAL_SCHEMA'),
                            ({self.trees['main']: {'baseline_ref': self.refs['main'], 'extra': 1}}, 'APPROVAL_SCHEMA')):
            with self.subTest(trees=trees), self.assertRaisesRegex(registry.ApprovalError, code):
                registry.resolve(self.root, 'HEAD', json.dumps({'schema_version': 1, 'trees': trees}))

    def test_size_limit_rejects_before_any_git_process(self):
        trace = self.root / 'oversize-trace.json'
        previous = os.environ.get('GIT_TRACE2_EVENT')
        os.environ['GIT_TRACE2_EVENT'] = str(trace)
        try:
            with self.assertRaisesRegex(registry.ApprovalError, 'APPROVAL_LIMIT'):
                registry.resolve(self.root, 'HEAD', ' ' * 48001)
            self.assertFalse(trace.exists(), 'Oversize data must be rejected before Git starts')
        finally:
            if previous is None:
                os.environ.pop('GIT_TRACE2_EVENT', None)
            else:
                os.environ['GIT_TRACE2_EVENT'] = previous

    def test_candidate_code_and_approval_file_are_never_executed_or_read_as_authority(self):
        records = self.records()
        records['trees'][self.trees['poison']] = {'baseline_ref': self.refs['one']}
        self.assertEqual(self.resolved('poison', records)['baseline_ref'], self.refs['one'])
        self.assertFalse((self.root / 'candidate-executed').exists())


if __name__ == '__main__':
    unittest.main()
