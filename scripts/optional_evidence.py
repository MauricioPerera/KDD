#!/usr/bin/env python3
"""Report optional evidence as PASS, FAIL or SKIP in GitHub Actions."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
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

_SCAN_KEYS = {'schema_version', 'source_ref', 'tool', 'inputs', 'findings_sha256'}
_SHA256 = re.compile(r'[0-9a-f]{64}')
_UNSAFE_PATH = re.compile(r'[\\:\x00-\x1f*?\[\]<>|\"]')


def _scan_path(path):
    if not isinstance(path, str) or not path or _UNSAFE_PATH.search(path):
        raise ValueError('invalid scan path')
    if any(part.casefold() == '.git' or not part or part.endswith(('.', ' '))
           for part in path.split('/')):
        raise ValueError('ambiguous scan path: ' + path)
    return path


def _regular_scan_file(root, name):
    local = root
    for part in _scan_path(name).split('/'):
        local = local / part
        info = local.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('linked scan path: ' + name)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('expected a regular file: ' + name)
    return local.read_bytes()


def _git_scan(root, *args):
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', '--no-replace-objects', '--literal-pathspecs',
                             '-C', str(root), *args], env=env, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('cannot verify Git scan provenance: git ' + args[0])
    return result.stdout


def _scan_commit(root, ref, width):
    if not isinstance(ref, str) or not re.fullmatch('[0-9a-f]{' + str(width) + '}', ref):
        raise ValueError('a full externally reviewed Git commit is required')
    if _git_scan(root, 'rev-parse', '--verify', ref + '^{commit}').decode('ascii').strip() != ref:
        raise ValueError('scan reference is not a commit ID')
    return ref


def _scan_blob(root, commit, name):
    listing = _git_scan(root, 'ls-tree', '-z', commit, '--', name)
    header, _, path = listing.partition(b'\t')
    fields = header.split()
    if (len(fields) != 3 or fields[0] not in (b'100644', b'100755') or fields[1] != b'blob'
            or path != name.encode('utf-8') + b'\0'):
        raise ValueError('missing regular Git scan file: ' + name)
    return _git_scan(root, 'cat-file', 'blob', fields[2].decode('ascii'))


def _json_bytes(raw):
    return raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _unique_json(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError('duplicate scan JSON key: ' + name)
        result[name] = value
    return result


def _invalid_constant(token):
    raise ValueError('invalid scan JSON constant: ' + token)


def _scan_document(raw):
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_json, parse_constant=_invalid_constant)
    if not isinstance(data, dict):
        raise ValueError('expected a scan JSON object')
    return data


def _reviewed_json(root, revisions, name):
    approved, candidate = revisions
    expected = _json_bytes(_scan_blob(root, approved, name))
    if candidate != approved and _json_bytes(_scan_blob(root, candidate, name)) != expected:
        raise ValueError('candidate differs from reviewed scan: ' + name)
    if _json_bytes(_regular_scan_file(root, name)) != expected:
        raise ValueError('checkout differs from reviewed scan: ' + name)
    return expected


def _digest(value):
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _input_inventory(document, evidence_names):
    inputs, text = document['inputs'], document.get('text_inputs', [])
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('expected a nonempty scan input inventory')
    for name, digest in inputs.items():
        _scan_path(name)
        if not _digest(digest):
            raise ValueError('invalid input digest: ' + name)
    folded = {name.casefold() for name in inputs}
    if len(folded) != len(inputs) or folded.intersection(name.casefold() for name in evidence_names):
        raise ValueError('ambiguous scan input inventory')
    if not isinstance(text, list) or any(not isinstance(name, str) or name not in inputs for name in text):
        raise ValueError('text_inputs must be a subset of inputs')
    if len(set(text)) != len(text):
        raise ValueError('duplicate text input')
    return inputs, set(text)


def _verify_scan_document(document, report):
    if (set(document) - {'text_inputs'} != _SCAN_KEYS or type(document['schema_version']) is not int
            or document['schema_version'] != 1):
        raise ValueError('invalid scan manifest schema')
    tool = document['tool']
    if (not isinstance(tool, dict) or set(tool) != {'name', 'version'}
            or any(not isinstance(value, str) or not value.strip() for value in tool.values())):
        raise ValueError('invalid scanner identity')
    if document['findings_sha256'] != hashlib.sha256(report).hexdigest():
        raise ValueError('scan findings digest differs from manifest')
    data = _scan_document(report)
    if data.get('documentType') != 'kdd-compliance.findings' or not isinstance(data.get('findings'), list):
        raise ValueError('expected an explicit compliance findings array')


def _verify_input(root, revisions, entry, text):
    name, digest = entry
    raw = _scan_blob(root, revisions[0], name)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('scan input digest differs: ' + name)
    for commit in revisions[1:]:
        if _scan_blob(root, commit, name) != raw:
            raise ValueError('scan input changed in Git: ' + name)
    local = _regular_scan_file(root, name)
    if text:
        raw.decode('utf-8')
        if b'\0' in raw:
            raise ValueError('NUL in reviewed text input: ' + name)
        raw, local = (body.replace(b'\r\n', b'\n') for body in (raw, local))
    if local != raw:
        raise ValueError('scan input changed in checkout: ' + name)


def _verify_compliance(source, manifest, environ):
    root = Path(_git_scan(Path.cwd(), 'rev-parse', '--show-toplevel').decode('utf-8').rstrip('\r\n')).resolve()
    candidate = _git_scan(root, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip()
    if 'GITHUB_SHA' in environ and environ['GITHUB_SHA'] != candidate:
        raise ValueError('scan candidate does not match the CI checkout')
    _scan_commit(root, candidate, len(candidate))
    ref = environ.get('KDD_COMPLIANCE_APPROVED_REF') or environ.get('KDD_APPROVED_BASELINE_REF')
    approved = _scan_commit(root, ref, len(candidate))
    _git_scan(root, 'merge-base', '--is-ancestor', approved, candidate)
    names = [path.absolute().relative_to(root).as_posix() for path in (source, manifest)]
    revisions = (approved, candidate)
    report, attestation = (_reviewed_json(root, revisions, name) for name in names)
    document = _scan_document(attestation)
    _verify_scan_document(document, report)
    scanned = _scan_commit(root, document['source_ref'], len(candidate))
    _git_scan(root, 'merge-base', '--is-ancestor', scanned, approved)
    inputs, text = _input_inventory(document, names)
    commits = tuple(dict.fromkeys((scanned, approved, candidate)))
    for entry in inputs.items():
        _verify_input(root, commits, entry, entry[0] in text)


def _compliance_status(source, required, environ, status):
    manifest = source.with_name('scan-manifest.json')
    if not manifest.exists() and not manifest.is_symlink():
        return ('FAIL' if required else 'SKIP'), 'reviewed scan manifest missing'
    try:
        _verify_compliance(source, manifest, environ)
    except (OSError, ValueError, RecursionError, subprocess.TimeoutExpired) as exc:
        return 'FAIL', str(exc)
    return status


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


def _scan_status(source, required, status):
    try:
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('expected a JSON object')
        identifier = data.get('scanId', '')
        if isinstance(identifier, str) and identifier.startswith('example_') and status[0] != 'FAIL':
            return ('FAIL' if required else 'SKIP'), 'example scan is not project evidence'
    except (ValueError, OSError, RecursionError):
        return 'FAIL', 'invalid evidence JSON'
    return status


def evaluate_layers(layers, required, environ, summary=False):
    if set(layers) - set(LAYERS) or set(required) - set(layers):
        raise ValueError('unknown or out-of-scope evidence layer')
    rows = []
    for layer in layers:
        source = _source(layer, environ)
        exists = source is not None and source.is_file()
        outcome = _outcome(layer, environ) if summary else ''
        status = _status(layer, required, (exists, outcome, summary))
        if exists and layer != 'quality':
            status = _scan_status(source, layer in required, status)
            if layer == 'compliance' and status[0] not in ('FAIL', 'SKIP'):
                status = _compliance_status(source, layer in required, environ, status)
        rows.append({'layer': layer, 'status': status[0], 'source': str(source or ''),
                     'reason': status[1]})
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
