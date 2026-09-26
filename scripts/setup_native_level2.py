"""Install a dedicated source runtime; never mutate an existing destination."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__:
    from .native_level2 import ENGINE_COMMIT, verify_engine
else:
    from native_level2 import ENGINE_COMMIT, verify_engine


def setup(runtime):
    root = Path(runtime).absolute()
    root.mkdir(parents=True, exist_ok=False)
    engine, environment = root / 'engine', root / 'venv'
    commands = [
        ['git', 'clone', '--no-checkout', 'https://github.com/MauricioPerera/ccdd-gate.git', str(engine)],
        ['git', '-C', str(engine), 'checkout', '--detach', ENGINE_COMMIT],
        [sys.executable, '-m', 'venv', str(environment)],
    ]
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    commands.append([str(python), '-m', 'pip', 'install', 'PyYAML==6.0.3', 'jsonschema==4.23.0'])
    for command in commands:
        subprocess.run(command, check=True, timeout=300, stdout=sys.stderr)
    verify_engine(engine)
    return {'engine_commit': ENGINE_COMMIT, 'engine_root': str(engine), 'python': str(python)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(setup(args.runtime)))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__,
                          'detail': 'Setup failed; existing or partial runtime preserved'}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
