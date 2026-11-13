"""Prepare and combine native Python suite coverage from one CI attempt."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

from coverage import Coverage, CoverageData
from coverage.exceptions import CoverageException


SOURCE_DIRS = ('scripts', 'src', 'site', 'tools/kdd-adoption')


def prepare(root, output):
    if output.is_relative_to(root):
        raise ValueError('coverage output must be outside the checkout')
    for directory in SOURCE_DIRS:
        if not (root / directory).is_dir():
            raise ValueError('missing coverage source: ' + directory)
    output.mkdir(parents=True, exist_ok=False)
    # Include restricts tracing without scanning the checkout at every child exit.
    sources = ''.join('    ' + (root / directory).as_posix() + '/**/*.py\n'
                      for directory in SOURCE_DIRS)
    config = ('[run]\nbranch = true\nparallel = true\ninclude =\n' + sources
              + 'data_file = ' + (output / '.coverage').as_posix()
              + '\n')
    (output / 'coverage.ini').write_text(config, encoding='utf-8')


def merge_fragments(config, output):
    collector = Coverage(config_file=str(config))
    fragments = sorted(output.glob('.coverage.*'))
    if not fragments or (output / '.coverage').exists():
        raise ValueError('expected fresh coverage fragments from the first suite pass')
    for fragment in fragments:
        if not fragment.is_file() or not fragment.stat().st_size:
            raise ValueError('empty or invalid coverage fragment: ' + fragment.name)
        piece = CoverageData(basename=fragment)
        piece.read()
        if not piece.has_arcs():
            raise ValueError('coverage fragment lacks branch data: ' + fragment.name)
    combined = collector.get_data()
    collector.combine(data_paths=[str(fragment) for fragment in fragments], strict=True, keep=True)
    if not combined.measured_files():
        raise ValueError('coverage did not measure any Python files')
    return collector, len(fragments)


def report(root, output, identity):
    config = output / 'coverage.ini'
    if output.is_relative_to(root) or not config.is_file():
        raise ValueError('coverage output must be prepared outside the checkout')
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', identity['head_sha']):
        raise ValueError('coverage requires a full commit SHA')
    result = output / 'coverage.json'
    if result.exists():
        raise ValueError('coverage report already exists')
    collector, fragments = merge_fragments(config, output)
    temporary = output / 'coverage.pending.json'
    try:
        os.chdir(root)
        # Include never-executed files in the denominator once, after the suite.
        files = sorted(path.relative_to(root).as_posix() for directory in SOURCE_DIRS
                       for path in (root / directory).rglob('*.py') if path.is_file())
        collector.json_report(morfs=files, outfile=str(temporary))
        data = json.loads(temporary.read_text(encoding='utf-8'))
        if not data['totals']['num_statements'] or not data['totals']['num_branches']:
            raise ValueError('coverage report requires positive line and branch denominators')
        data['files'] = {Path(path).as_posix(): row for path, row in data['files'].items()}
        data['kdd'] = dict(identity, suite_pass=1, fragments=fragments,
                           source_directories=SOURCE_DIRS)
        temporary.write_text(json.dumps(data, ensure_ascii=True, sort_keys=True) + '\n',
                             encoding='utf-8')
        temporary.replace(result)
    finally:
        temporary.unlink(missing_ok=True)
    totals = data['totals']
    print('Python coverage pass 1: %s/%s lines and %s/%s branches (%s fragments)' %
          (totals['covered_lines'], totals['num_statements'], totals['covered_branches'],
           totals['num_branches'], fragments))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('prepare')
    finish = commands.add_parser('report')
    for command in (setup, finish):
        command.add_argument('--repo-root', default='.')
        command.add_argument('--output', required=True)
    for name in ('head-sha', 'run-id', 'attempt', 'platform'):
        finish.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        root, output = Path(args.repo_root).resolve(strict=True), Path(args.output).resolve()
        if args.command == 'prepare':
            prepare(root, output)
        else:
            report(root, output, {name: getattr(args, name)
                                  for name in ('head_sha', 'run_id', 'attempt', 'platform')})
    except (CoverageException, OSError, ValueError) as error:
        print('FAIL coverage: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
