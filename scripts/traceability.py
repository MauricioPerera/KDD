"""Report requirement traceability from committed KDD artifacts, read-only."""
import argparse
import html
import json
import sys

from traceability_git import build_trace


def _cell(value):
    text = html.escape(str(value), quote=True).replace('|', '&#124;').replace('`', '&#96;')
    text = text.replace('\r', ' ').replace('\n', ' ')
    return text.encode('ascii', 'xmlcharrefreplace').decode('ascii')


def markdown(report):
    lines = ['# Requirement traceability', '',
             'Observed commit: ' + _cell(report['observed_commit']),
             'Complete: ' + str(report['complete']).lower(), '',
             '| Requirement | Contract | Oracle | Task | Tested commit | Evidence | State |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for requirement in report['requirements']:
        for link in requirement['links']:
            values = [requirement['id'], link['contract'], link['oracle'], link['task_id'],
                      link['tested_commit'], link['evidence'], link['state']]
            lines.append('| ' + ' | '.join(_cell(value) for value in values) + ' |')
    if report['findings']:
        lines.extend(['', '## Findings', ''])
        for finding in report['findings']:
            lines.append('- ' + _cell(finding['code']) + ': ' + _cell(finding['message']))
    return '\n'.join(lines) + '\n'


def main(argv=None):
    """Expose the reviewed traceability report and strict completion check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--ref', default='main')
    parser.add_argument('--manifest', default='quality/traceability.json')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--require-verified', action='store_true')
    args = parser.parse_args(argv)
    report = build_trace(args.repo_root, args.ref, args.manifest, args.require_verified)
    if args.format == 'markdown':
        print(markdown(report), end='')
    else:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    if report['ok']:
        return 0
    inputs = {'TRACE_INPUT', 'TRACE_SCHEMA', 'TRACE_SPEC', 'TRACE_GIT'}
    return 2 if any(f['code'] in inputs for f in report['findings']) else 1


if __name__ == '__main__':
    sys.exit(main())
