"""Run the approved compliance inputs through the real Git and CLI boundary."""
from collections import Counter
import hashlib
import json
import unittest

from tests import test_goldfish_compliance as compliance


class ComplianceBatch(unittest.TestCase):
    def project(self, extra=0, long_paths=False):
        fixture = compliance.ComplianceEvidence()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.repo = fixture.repo.resolve(strict=True)
        files = {}
        directory = 'z inputs/' + 'x' * 142 if long_paths else 'z inputs'
        for index in range(extra):
            name = f'{directory}/input {index:02d}.bin'
            content = b'prefix\0\n\xff\r\n' + bytes([index])
            path = fixture.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            files[name] = hashlib.sha256(content).hexdigest()
        if files:
            fixture.scanned = fixture.commit('Commit extra binary license inputs')
        evidence = fixture.record()
        evidence['inputs'].update(files)
        fixture.write_json(compliance.MANIFEST, evidence)
        approved = fixture.commit('Review full scan inventory')
        (fixture.repo / 'README.md').write_bytes(b'Change outside the reviewed scan.\n')
        candidate = fixture.commit('Publish the unchanged reviewed scan')
        self.assertEqual(len({fixture.scanned, approved, candidate}), 3)
        return fixture, approved, candidate, list(files)

    def launches(self, fixture, phase, approved, candidate):
        trace = fixture.repo.parent / (phase + '.trace')
        result = fixture.layers(phase, approved, GITHUB_SHA=candidate,
                                GIT_TRACE2_EVENT=str(trace))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = 'PRESENT' if phase == 'check' else 'PASS'
        self.assertIn(status + ' [compliance]', result.stdout)
        return [event['argv'] for line in trace.read_text(encoding='utf-8').splitlines()
                if (event := json.loads(line))['event'] == 'start']

    def test_git_start_ceiling_for_two_and_eighteen_inputs_in_each_phase(self):
        for extra in (0, 16):
            fixture, approved, candidate, _ = self.project(extra)
            for phase in ('check', 'summary'):
                with self.subTest(inputs=extra + 2, phase=phase):
                    starts = len(self.launches(fixture, phase, approved, candidate))
                    self.assertGreater(starts, 0)
                    self.assertLessEqual(starts, 15, (extra + 2, phase, starts))

    def test_large_argv_is_split_with_every_input_read(self):
        fixture, approved, candidate, files = self.project(30, long_paths=True)
        expected = Counter([compliance.INPUT, compliance.METADATA, *files])
        for phase in ('check', 'summary'):
            with self.subTest(phase=phase):
                starts = self.launches(fixture, phase, approved, candidate)
                self.assertLessEqual(len(starts), 20)
                chunks = [(argv[argv.index('--') - 1], argv[argv.index('--') + 1:])
                          for argv in starts if 'ls-tree' in argv and '--' in argv
                          and any(name in argv for name in files)]
                for revision in (fixture.scanned, approved, candidate):
                    group = [chunk for rev, chunk in chunks if rev == revision]
                    self.assertGreaterEqual(len(group), 2)
                    self.assertEqual(Counter(name for chunk in group for name in chunk), expected)
                    for chunk in group:
                        self.assertLessEqual(sum(len(name.encode('utf-8')) + 3 for name in chunk), 4096)

    def test_input_differs_only_in_approved_commit(self):
        fixture, approval, _, files = self.project(4)
        fixture.git('switch', '--detach', approval)
        path = fixture.repo / files[-1]
        original = path.read_bytes()
        path.write_bytes(b'input different only in the reviewed commit\n')
        changed = fixture.commit('Review a candidate with a different last input')
        path.write_bytes(original)
        head = fixture.commit('Restore the scanned input in the candidate')
        fixture.rejected(changed, GITHUB_SHA=head)

    def test_last_binary_input_differs_even_when_replace_hides_its_bytes(self):
        fixture, approved, _, files = self.project(4)
        name = files[-1]
        original = fixture.git('rev-parse', 'HEAD:' + name).decode().strip()
        (fixture.repo / name).write_bytes(b'new\0bytes\n')
        fixture.commit('Change just the final input')
        changed = fixture.git('rev-parse', 'HEAD:' + name).decode().strip()
        fixture.git('replace', changed, original)
        reviewed = b'prefix\0\n\xff\r\n\x03'
        self.assertEqual(fixture.git('show', 'HEAD:' + name), reviewed)
        (fixture.repo / name).write_bytes(reviewed)
        fixture.rejected(approved)

    def test_last_input_cannot_be_missing_or_a_link_with_the_same_oid(self):
        for kind in ('missing', 'link'):
            with self.subTest(kind=kind):
                fixture, approved, _, files = self.project(4)
                name = files[-1]
                if kind == 'missing':
                    # Keep the local file in place while deleting it from the index.
                    fixture.git('rm', '--cached', '--', name)
                else:
                    oid = fixture.git('rev-parse', 'HEAD:' + name).decode().strip()
                    fixture.git('update-index', '--cacheinfo', '120000,' + oid + ',' + name)
                fixture.git('commit', '-qm', 'Change the final Git inventory entry')
                self.assertTrue((fixture.repo / name).is_file())
                fixture.rejected(approved)


if __name__ == '__main__':
    unittest.main()
