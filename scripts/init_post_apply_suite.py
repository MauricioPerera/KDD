"""Run the complete initialized-project suite with a native worker profile."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--report-json')
    args = parser.parse_args(argv)
    try:
        root = Path(args.repo_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError('repository root is not a directory')
        report = Path(args.report_json).absolute() if args.report_json else None
        if report is not None and os.path.lexists(report):
            raise ValueError('report destination already exists')
        command = [sys.executable, str(root / 'scripts/run_test_suite.py'),
                   '--start-directory', 'tests', '--pattern', 'test_*.py',
                   '--workers', '6' if os.name == 'nt' else '4']
        if report is not None:
            command += ['--report-json', str(report)]
        return subprocess.call(command, cwd=root)
    except (OSError, ValueError) as exc:
        print('POST_INIT_SUITE: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
