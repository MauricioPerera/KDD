"""Real-engine native acceptance and parity probe in a disposable workspace."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from scripts import native_level2 as native
from tests.test_native_level2 import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    args = parser.parse_args()
    engine, python = args.engine_root.resolve(), args.python.absolute()
    with tempfile.TemporaryDirectory(prefix='kdd native demo ') as directory:
        root = Path(directory)
        contract = fixture(root)
        options = {'python': python, 'timeout': 20}
        passed = native.run_level2(contract, root, engine, **options)
        if not passed['ok'] or passed['gate']['runtime']['mcp_loaded']:
            raise AssertionError(passed)
        exported = native._export(native.prepare(contract, root), root)
        try:
            direct = subprocess.run([str(python), '-I', str(engine / 'runners/task_gate.py'), str(exported)],
                                    cwd=root, capture_output=True, text=True, timeout=20)
            raw = json.loads(direct.stdout)
            if direct.returncode or raw['metrics'] != passed['gate']['metrics'] or raw['verdict'] != passed['verdict']:
                raise AssertionError(raw)
        finally:
            exported.unlink()
        target = root / 'src/add.py'
        target.write_text('def add(a: int, b: int) -> int:\n    return 0\n')
        failed_tests = native.run_level2(contract, root, engine, **options)
        if failed_tests['verdict'] != 'FAIL' or failed_tests['stage'] != 'gate1-tests':
            raise AssertionError(failed_tests)
        target.write_text('def add(a: int, b: int) -> int:\n    if a:\n        if b:\n            return a + b\n    return a + b\n')
        failed_budget = native.run_level2(contract, root, engine, **options)
        if failed_budget['verdict'] != 'FAIL' or failed_budget['stage'] != 'gate2-complexity':
            raise AssertionError(failed_budget)
        target.write_text('import time\ndef add(a: int, b: int) -> int:\n    time.sleep(30)\n    return a + b\n')
        timed_out = native.run_level2(contract, root, engine, python=python, timeout=1)
        if timed_out['verdict'] != 'TIMEOUT' or timed_out['ok']:
            raise AssertionError(timed_out)
        (root / 'tests/check.py').write_text('assert True\n')
        failed_seal = native.run_level2(contract, root, engine, **options)
        if failed_seal['verdict'] != 'INVALID' or failed_seal.get('gate'):
            raise AssertionError(failed_seal)
        print(json.dumps({'pass': passed, 'direct_cli_parity': True,
                          'failed_tests': failed_tests['stage'], 'failed_budget': failed_budget['stage'],
                          'timeout': timed_out['verdict'],
                          'failed_seal': failed_seal['verdict'],
                          'exports_cleaned': not list(root.glob('*.gate.md'))}, indent=2))


if __name__ == '__main__':
    main()
