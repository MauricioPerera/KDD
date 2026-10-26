"""Real process journals for explicit exclusion, default compatibility and CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_test_commands as runner

PROBE = '''import json,os,subprocess,sys,time,uuid
from pathlib import Path
name=sys.argv[1]
identity=uuid.uuid4().hex
def event(phase):
    value=dict(label=name,phase=phase,time=time.monotonic_ns(),pid=os.getpid(),identity=identity)
    Path('events',phase+'-'+identity+'.json').write_text(json.dumps(value),encoding='utf-8')
event('start')
if name=='heavy':
    children=[subprocess.Popen([sys.executable,'probe.py','inner-'+str(i)]) for i in range(4)]
    deadline=time.monotonic()+20
    while len(list(Path('events').glob('ready-*')))<4:
        if time.monotonic()>deadline: raise RuntimeError('four child readiness markers absent')
        time.sleep(.01)
    Path('events/release').write_text('release',encoding='utf-8')
    for child in children:
        if child.wait(timeout=20): raise RuntimeError('nested child failed')
elif name.startswith('inner-'):
    Path('events','ready-'+name).write_text('ready',encoding='utf-8')
    deadline=time.monotonic()+20
    while not Path('events/release').exists():
        if time.monotonic()>deadline: raise RuntimeError('observable release absent')
        time.sleep(.01)
elif name=='sleep': time.sleep(10)
else: time.sleep(.03)
event('end')
print('RESOURCE_PROBE:'+name)
raise SystemExit(7 if name=='fail' else 0)
'''


class ContractResourceScheduling(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='kdd resources \u00f1 ')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / 'events').mkdir()
        self.contracts = self.root / 'contracts'
        self.contracts.mkdir()
        (self.root / 'probe.py').write_text(PROBE, encoding='utf-8')

    def command(self, label):
        return '"{}" probe.py {}'.format(sys.executable, label)

    def contract(self, name, label, target='scripts/probe.py'):
        command = self.command(label)
        (self.contracts / name).write_text(
            "---\ntarget: " + target + "\ntest_command: '" + command + "'\n---\n", encoding='utf-8')
        return command

    def configured(self, commands, **options):
        try:
            return runner.run_all(str(self.contracts), str(self.root),
                                  exclusive_commands=commands, **options)
        except TypeError as error:
            self.fail('The reviewed resource interface is unavailable: ' + str(error))

    def events(self, label=None, phase=None):
        values = [json.loads(path.read_text(encoding='utf-8'))
                  for path in (self.root / 'events').glob('*.json')]
        return sorted([value for value in values if (label is None or value['label'] == label)
                       and (phase is None or value['phase'] == phase)], key=lambda row:row['time'])

    def example(self):
        self.contract('a.md', 'a')
        self.contract('b.md', 'b')
        return self.contract('z-heavy.md', 'heavy', 'src/product.py')

    def test_default_serial_preserves_original_order(self):
        self.contract('a.md', 'a'); self.contract('b.md', 'b')
        results = runner.run_all(str(self.contracts), str(self.root))
        self.assertEqual([row['label'] for row in self.events(phase='start')], ['a','b'])
        self.assertTrue(all(row['ok'] for row in results))

    def test_default_parallel_executes_every_command(self):
        for name in ('a','b','c','d'):
            self.contract(name+'.md', name)
        results = runner.run_all(str(self.contracts), str(self.root), workers=4)
        self.assertEqual(sorted(row['label'] for row in self.events(phase='end')), ['a','b','c','d'])
        self.assertEqual(len(results), 4)

    def test_exclusive_nested_four_children_finish_before_other_commands_start(self):
        heavy = self.example()
        results = self.configured([heavy], workers=4)
        self.assertTrue(all(row['ok'] for row in results), results)
        self.assertEqual(len([row for row in self.events(phase='end') if row['label'].startswith('inner-')]), 4)
        end = self.events('heavy','end')[0]['time']
        self.assertTrue(all(row['time'] >= end for row in self.events(phase='start')
                            if row['label'] in ('a','b')))
        self.assertEqual([Path(row['path']).name for row in results], ['a.md','b.md','z-heavy.md'])
        self.assertEqual(results[-1]['scope'], 'product')

    def test_multiple_exclusive_commands_do_not_overlap(self):
        a = self.contract('z-a.md','a'); b = self.contract('z-b.md','b')
        self.contract('a-light.md','light')
        results = self.configured([b,a], workers=4)
        starts = self.events(phase='start'); ends = {r['label']:r['time'] for r in self.events(phase='end')}
        self.assertEqual(set(row['label'] for row in starts[:2]), {'a','b'})
        self.assertGreaterEqual(starts[1]['time'], ends[starts[0]['label']])
        self.assertGreaterEqual(starts[2]['time'], max(ends['a'],ends['b']))
        self.assertTrue(all(row['ok'] for row in results))

    def test_exclusive_failure_does_not_omit_remaining_commands(self):
        failed = self.contract('z-fail.md','fail'); self.contract('a.md','a')
        results = self.configured([failed], workers=4)
        self.assertEqual([r['exit_code'] for r in results], [0,7])
        self.assertEqual(len(self.events('a','end')), 1)
        self.assertFalse(results[-1]['ok'])

    def test_exclusive_timeout_preserves_timeout_and_executes_the_rest(self):
        sleeping = self.contract('z-sleep.md','sleep'); self.contract('a.md','a')
        results = self.configured([sleeping], workers=4, timeout=1.5)
        self.assertEqual(results[-1]['error'], 'timeout')
        self.assertFalse(results[-1]['ok'])
        self.assertTrue(results[0]['ok'], results[0])
        self.assertEqual(len(self.events('a','end')), 1)

    def test_exact_dedup_keeps_both_scopes_and_one_execution(self):
        value = self.contract('a.md','a'); self.contract('b.md','a','src/product.py')
        results = self.configured([value], deduplicate=True, workers=4)
        self.assertEqual(len(self.events('a','start')), 1)
        self.assertEqual([r['scope'] for r in results], ['infrastructure','product'])
        self.assertEqual(results[1]['shared_from'], results[0]['path'])
        self.assertEqual(results[1]['duration_seconds'], 0)
        self.assertIn('RESOURCE_PROBE:a', results[1]['stdout'])

    def test_without_dedup_each_exclusive_contract_still_executes(self):
        value = self.contract('a.md','a'); self.contract('b.md','a')
        results = self.configured([value], workers=4)
        self.assertEqual(len(self.events('a','start')), 2)
        self.assertTrue(all(row['shared_from'] is None for row in results))

    def test_empty_policy_preserves_serial_order(self):
        self.contract('a.md','a'); self.contract('b.md','b')
        results = self.configured([], workers=1)
        self.assertEqual([row['label'] for row in self.events(phase='start')], ['a','b'])
        self.assertTrue(all(row['ok'] for row in results))

    def test_unknown_command_is_rejected_before_any_process(self):
        self.contract('a.md','a')
        with self.assertRaisesRegex(ValueError, 'exclusive'):
            self.configured(['unknown command'], workers=4)
        self.assertEqual(self.events(), [])

    def test_non_sequence_policies_are_rejected_before_any_process(self):
        self.contract('a.md','a')
        for value in (None, True, 'command', {'command':1}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'exclusive'):
                self.configured(value, workers=4)
        self.assertEqual(self.events(), [])

    def test_invalid_entries_and_duplicates_are_rejected(self):
        value = self.contract('a.md','a')
        for commands in ([None], [True], [''], [value,value]):
            with self.subTest(commands=commands), self.assertRaisesRegex(ValueError, 'exclusive'):
                self.configured(commands, workers=4)
        self.assertEqual(self.events(), [])

    def test_commands_are_not_fuzzily_matched(self):
        value = self.contract('a.md','a')
        with self.assertRaisesRegex(ValueError, 'exclusive'):
            self.configured([value+' '], workers=4)
        self.assertEqual(self.events(), [])

    def test_policy_and_outcomes_are_not_cached_across_calls(self):
        value = self.contract('a.md','a')
        self.configured([value], workers=4)
        self.configured([], workers=4)
        self.assertEqual(len(self.events('a','start')), 2)

    def cli(self, raw):
        return subprocess.run([sys.executable,str(ROOT/'scripts/validate_test_commands.py'),
            str(self.contracts),str(self.root),'--workers','4','--exclusive-commands-json',raw],
            cwd=self.root,capture_output=True,text=True,encoding='utf-8',timeout=60)

    def test_cli_rejects_invalid_json_without_running_tests(self):
        self.contract('a.md','a')
        result = self.cli('{broken')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exclusive', (result.stdout+result.stderr).lower())
        self.assertEqual(self.events(), [])

    def test_cli_runs_the_explicit_policy_with_real_commands(self):
        heavy = self.example()
        result = self.cli(json.dumps([heavy]))
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        end = self.events('heavy','end')[0]['time']
        self.assertTrue(all(row['time']>=end for row in self.events(phase='start') if row['label'] in ('a','b')))

    def test_real_external_bundle_accepts_the_resource_policy_and_reports_every_contract(self):
        heavy = self.example()
        scripts = self.root/'scripts'; scripts.mkdir()
        names = ['trusted_ci.py','run_test_suite.py','validate_test_commands.py',
                 'validate_contracts.py','process_tree.py','execution_profile.py']
        for name in names: shutil.copyfile(ROOT/'scripts'/name,scripts/name)
        for argv in (['git','init','-q'],['git','config','user.name','Simulated reviewer'],
                     ['git','config','user.email','fixture@example.invalid'],
                     ['git','config','commit.gpgsign','false'],['git','config','gc.autoDetach','false'],
                     ['git','config','maintenance.autoDetach','false'],['git','add','.'],
                     ['git','commit','-qm','Synthetic runtime fixture; no real approval']):
            result = subprocess.run(argv,cwd=self.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        ref = subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.root,text=True).strip()
        with tempfile.TemporaryDirectory(prefix='kdd-external-resources-') as directory:
            bundle = Path(directory)/'bundle'; report = Path(directory)/'commands.json'
            prepared = subprocess.run([sys.executable,'-I',str(scripts/'trusted_ci.py'),'prepare',
                '--repo-root',str(self.root),'--trusted-ref',ref,'--bundle-dir',str(bundle)],
                capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(prepared.returncode,0,prepared.stdout+prepared.stderr)
            result = subprocess.run([sys.executable,'-I',str(bundle/'trusted_ci.py'),'commands',
                '--repo-root',str(self.root),'--contracts-dir','contracts','--workers','4',
                '--exclusive-commands-json',json.dumps([heavy]),'--report-json',str(report)],
                capture_output=True,text=True,encoding='utf-8',timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(data['ok'])
            self.assertEqual(len(data['results']),3)
            self.assertTrue(all(row['ok'] for row in data['results']))

    def test_workflow_preserves_matrix_timeout_and_two_identical_passes(self):
        text = (ROOT/'.github/workflows/validate.yml').read_text(encoding='utf-8')
        self.assertIn('exclusive_contract_commands:',text)
        self.assertIn('--exclusive-commands-json "$KDD_EXCLUSIVE_CONTRACT_COMMANDS"',text)
        self.assertIn('--timeout 600 --deduplicate --workers "$KDD_CONTRACT_WORKERS"',text)
        self.assertEqual(text.count('os: [ubuntu-latest, windows-latest]'),2)
        self.assertEqual(text.count('run: python -I "$KDD_TRUSTED_BUNDLE/trusted_ci.py" suite --repo-root . --start-directory tests --pattern "test_*.py" --workers "$KDD_SUITE_WORKERS" --report-dir "$RUNNER_TEMP/kdd-suite-reports"'),2)
        self.assertNotIn('continue-on-error:',text)


if __name__ == '__main__':
    unittest.main()
