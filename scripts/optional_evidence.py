#!/usr/bin/env python3
"""Report optional evidence as PASS, FAIL or SKIP in GitHub Actions."""

import argparse
import os
from pathlib import Path
import sys


LAYERS = {
    'security': ('KDD_SECURITY_SCAN_DIR', 'findings.json'),
    'compliance': ('KDD_COMPLIANCE_SCAN_DIR', 'findings.json'),
    'privacy': ('KDD_PRIVACY_SCAN_DIR', 'findings.json'),
    'accessibility': ('KDD_ACCESSIBILITY_SCAN_DIR', 'findings.json'),
    'dependency-eol': ('KDD_DEPENDENCY_EOL_SCAN_DIR', 'findings.json'),
    'observability': ('KDD_OBSERVABILITY_SCAN_DIR', 'findings.json'),
    'test-coverage': ('KDD_TEST_COVERAGE_SCAN_DIR', 'findings.json'),
    'quality': ('KDD_QUALITY_POLICY', ''),
}


def _names(value):
    names = [part.strip() for part in value.split(',') if part.strip()]
    if len(names) != len(set(names)):
        raise ValueError('duplicate evidence layer')
    unknown = set(names) - set(LAYERS)
    if unknown:
        raise ValueError('unknown evidence layer: ' + ', '.join(sorted(unknown)))
    return names


def _source(layer, environ):
    variable, filename = LAYERS[layer]
    configured = environ.get(variable, '')
    path = Path(configured) if configured else None
    return path / filename if path is not None and filename else path


def _outcome(layer, environ):
    key = 'KDD_{}_OUTCOME'.format(layer.upper().replace('-', '_'))
    return environ.get(key, '').lower()


def _status(layer, required, evidence):
    exists, outcome, summary = evidence
    if summary and outcome == 'failure':
        return 'FAIL', 'validator outcome: failure'
    if not exists:
        if layer in required:
            return 'FAIL', 'required evidence missing'
        return 'SKIP', 'evidence absent'
    if not summary:
        return 'PRESENT', 'validator has not run yet'
    if outcome == 'success':
        return 'PASS', 'evidence validated by CI step'
    return 'FAIL', 'validator outcome: ' + (outcome or 'not run')


def evaluate_layers(layers, required, environ, summary=False):
    if set(layers) - set(LAYERS) or set(required) - set(layers):
        raise ValueError('unknown or out-of-scope evidence layer')
    rows = []
    for layer in layers:
        source = _source(layer, environ)
        exists = source is not None and source.is_file()
        outcome = _outcome(layer, environ) if summary else ''
        status, reason = _status(layer, required, (exists, outcome, summary))
        rows.append({'layer': layer, 'status': status, 'source': str(source or ''),
                     'reason': reason})
    return rows


def _markdown(rows):
    lines = ['## Optional KDD evidence', '', '| Layer | Status | Source | Reason |',
             '|---|---|---|---|']
    for row in rows:
        cells = [str(row[key]).replace('|', '\\|').replace('\n', ' ')
                 for key in ('layer', 'status', 'source', 'reason')]
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check', 'summary'))
    parser.add_argument('--layers', required=True, help='comma-separated layer names')
    args = parser.parse_args(argv)
    try:
        layers = _names(args.layers)
        required = set(_names(os.environ.get('KDD_REQUIRED_EVIDENCE', '')))
        rows = evaluate_layers(layers, required, os.environ, args.mode == 'summary')
    except ValueError as exc:
        parser.error(str(exc))
    for row in rows:
        print('{status} [{layer}] {source}: {reason}'.format(**row))
    if args.mode == 'summary':
        counts = {state: sum(row['status'] == state for row in rows)
                  for state in ('PASS', 'FAIL', 'SKIP')}
        print('Summary: PASS={PASS} FAIL={FAIL} SKIP={SKIP}'.format(**counts))
        summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary_path:
            with open(summary_path, 'a', encoding='utf-8') as target:
                target.write(_markdown(rows))
    return int(any(row['status'] == 'FAIL' for row in rows))


if __name__ == '__main__':
    sys.exit(main())
