#!/usr/bin/env python3
"""Run validations with native Git for Windows in a process-local environment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def runtime_environment(environ=None, platform=None):
    """Prefer an installed native Git without editing global configuration."""
    env = dict(os.environ if environ is None else environ)
    if (os.name if platform is None else platform) != 'nt':
        return env
    # Windows environment names are case-insensitive; Python exposes uppercase
    # keys, while callers may supply mixed-case dictionaries.
    env = {key.upper(): value for key, value in env.items()}
    roots = [env.get('PROGRAMW6432'), env.get('PROGRAMFILES'),
             env.get('PROGRAMFILES(X86)')]
    candidates = [Path(root) / 'Git' / 'cmd' for root in roots if root]
    if env.get('LOCALAPPDATA'):
        candidates.append(Path(env['LOCALAPPDATA']) / 'Programs' / 'Git' / 'cmd')
    for directory in candidates:
        if (directory / 'git.exe').is_file():
            entries = env.get('PATH', '').split(';')
            entries = [entry for entry in entries if entry.casefold() != str(directory).casefold()]
            env['PATH'] = ';'.join([str(directory), *entries])
            break
    return env


def prepare_runtime():
    """Apply the environment only to this interpreter and its descendants."""
    env = runtime_environment()
    if 'PATH' in env:
        os.environ['PATH'] = env['PATH']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('suite', 'preflight', 'contracts'))
    args, extra = parser.parse_known_args(argv)
    root = Path(__file__).resolve().parents[1]
    commands = {
        'suite': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
        'preflight': [sys.executable, 'scripts/preflight.py'],
        'contracts': [sys.executable, 'scripts/validate_test_commands.py', 'knowledge/contracts', '.'],
    }
    try:
        return subprocess.run([*commands[args.mode], *extra], cwd=root,
                              env=runtime_environment(), shell=False, check=False).returncode
    except OSError as exc:
        print('FAIL runtime: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
