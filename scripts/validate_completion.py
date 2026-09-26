#!/usr/bin/env python3
"""Check project spec/report completion against structured CI evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


_PREFIX = re.compile(r'^(CONTRACT-[0-9]+)')
_CHECKBOX = re.compile(r'^\s*-\s*\[([ xX])\]\s*(.*)$')
_ID = re.compile(r'^\[([A-Z][A-Z0-9-]*)\]\s+(.+)$')
_SHA = re.compile(r'^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$')
_REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def _finding(path, rule, message):
    return {'file': path, 'level': 'ERROR', 'rule': rule, 'msg': message}


def _read(path):
    return path.read_text(encoding='utf-8')


def _normalized(path):
    return path.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _legacy_digest(spec, report):
    return hashlib.sha256(_normalized(spec) + b'\0' + _normalized(report)).hexdigest()


def _prefix(path):
    match = _PREFIX.match(path.name)
    return match.group(1) if match else None


def _criteria(spec_text, spec_rel):
    findings = []
    ids = {}
    in_section = False
    for line in spec_text.splitlines():
        if line.strip() == '## Criterios de aceptación':  # ascii: allow
            in_section = True
            continue
        if in_section and line.startswith('## '):
            break
        if not in_section:
            continue
        checkbox = _CHECKBOX.match(line)
        if not checkbox:
            continue
        item = _ID.match(checkbox.group(2))
        if not item:
            findings.append(_finding(spec_rel, 'CRITERION_ID',
                                     'cada checkbox cerrado requiere [AC-1] o [CI-1]'))
            continue
        criterion_id = item.group(1)
        if criterion_id in ids:
            findings.append(_finding(spec_rel, 'CRITERION_DUPLICATE',
                                     'ID duplicado: ' + criterion_id))
        ids[criterion_id] = checkbox.group(1).lower() == 'x'
        if not ids[criterion_id]:
            findings.append(_finding(spec_rel, 'CRITERION_PENDING',
                                     'criterio sin completar: ' + criterion_id))
    if not ids:
        findings.append(_finding(spec_rel, 'CRITERIA_MISSING',
                                 'sin criterios con ID en Criterios de aceptación'))  # ascii: allow
    if not any(key.startswith('CI-') for key in ids):
        findings.append(_finding(spec_rel, 'CI_CRITERION_MISSING',
                                 'al menos un criterio CI-* es obligatorio'))
    return ids, findings


def _ci_reference(ci, repository, evidence_rel):
    findings = []
    ci = ci if isinstance(ci, dict) else {}
    run_url = ci.get('run_url')
    expected = r'https://github\.com/{}/actions/runs/[0-9]+'.format(re.escape(repository))
    if not isinstance(run_url, str) or not re.fullmatch(expected, run_url):
        findings.append(_finding(evidence_rel, 'CI_RUN_URL',
                                 'run_url debe apuntar a un run del repositorio declarado'))
        run_url = None
    if not isinstance(ci.get('head_sha'), str) or not _SHA.fullmatch(ci['head_sha']):
        findings.append(_finding(evidence_rel, 'CI_HEAD_SHA',
                                 'head_sha debe ser un SHA completo'))
    return run_url, findings


def _item_findings(items, ids, run_url, evidence_rel):
    findings = []
    if not isinstance(items, dict) or set(items) != set(ids):
        findings.append(_finding(evidence_rel, 'EVIDENCE_CRITERIA',
                                 'los IDs de evidencia deben coincidir exactamente con el spec'))
        items = items if isinstance(items, dict) else {}
    for criterion_id in sorted(set(ids) & set(items)):
        item = items[criterion_id]
        valid = (isinstance(item, dict)
                 and item.get('status') in ('locally_verified', 'verified_in_ci')
                 and isinstance(item.get('evidence'), str)
                 and bool(item['evidence'].strip()))
        if not valid:
            findings.append(_finding(evidence_rel, 'EVIDENCE_ITEM',
                                     'estado/evidencia invalidos para ' + criterion_id))
        elif criterion_id.startswith('CI-') and (
                item['status'] != 'verified_in_ci' or item['evidence'] != run_url):
            findings.append(_finding(evidence_rel, 'CI_CRITERION_EVIDENCE',
                                     'criterio CI sin evidencia del run: ' + criterion_id))
    return findings


def _report_rows(report_text, report_rel):
    """Read the canonical criterion table without interpreting report prose."""
    lines = report_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines)
                     if line.strip() == '## Resultado por criterio')
    except StopIteration:
        return {}, [_finding(report_rel, 'REPORT_CRITERIA',
                             'falta la tabla Resultado por criterio')]
    section = []
    for line in lines[start + 1:]:
        if line.startswith('## '):
            break
        if line.strip():
            section.append(line.strip())
    if not _valid_report_header(section):
        return {}, [_finding(report_rel, 'REPORT_CRITERIA',
                             'cabecera de tabla invalida')]
    rows = {}
    findings = []
    for line in section[2:]:
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if not line.startswith('|') or not line.endswith('|') or len(cells) != 3:
            findings.append(_finding(report_rel, 'REPORT_CRITERIA',
                                     'fila de tabla invalida'))
            continue
        criterion_id = cells[0]
        if criterion_id in rows:
            findings.append(_finding(report_rel, 'REPORT_CRITERIA',
                                     'ID duplicado en reporte: ' + criterion_id))
        rows[criterion_id] = (cells[1], cells[2])
    return rows, findings


def _valid_report_header(section):
    return (len(section) >= 2
            and section[0] == '| ID | Estado | Evidencia |'
            and bool(re.fullmatch(r'\|\s*-+\s*\|\s*-+\s*\|\s*-+\s*\|',
                                  section[1])))


def _report_findings(report_text, report_rel, ids, items):
    rows, findings = _report_rows(report_text, report_rel)
    if set(rows) != set(ids):
        findings.append(_finding(report_rel, 'REPORT_CRITERIA',
                                 'IDs de reporte y spec no coinciden'))
    items = items if isinstance(items, dict) else {}
    for criterion_id in sorted(set(rows) & set(items)):
        item = items[criterion_id]
        if not isinstance(item, dict):
            continue
        status, evidence = rows[criterion_id]
        if status != item.get('status'):
            findings.append(_finding(report_rel, 'REPORT_STATUS',
                                     'estado contradictorio para ' + criterion_id))
        if evidence != item.get('evidence'):
            findings.append(_finding(report_rel, 'REPORT_ITEM_EVIDENCE',
                                     'evidencia contradictoria para ' + criterion_id))
    return findings


def _validate_evidence(root, pair, repository):
    spec, report = pair
    prefix = _prefix(report)
    spec_rel = spec.relative_to(root).as_posix()
    report_rel = report.relative_to(root).as_posix()
    evidence = report.with_name(prefix + '-EVIDENCE.json')
    evidence_rel = evidence.relative_to(root).as_posix()
    ids, findings = _criteria(_read(spec), spec_rel)
    if not evidence.is_file():
        return findings + [_finding(evidence_rel, 'EVIDENCE_MISSING',
                                    'cierre sin manifiesto de evidencia')]
    try:
        data = json.loads(_read(evidence))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return findings + [_finding(evidence_rel, 'EVIDENCE_PARSE', str(exc))]
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        return findings + [_finding(evidence_rel, 'EVIDENCE_SCHEMA',
                                    'schema_version debe ser 1')]
    if data.get('spec') != spec_rel or data.get('state') != 'verified_in_ci':
        findings.append(_finding(evidence_rel, 'EVIDENCE_STATE',
                                 'spec y state deben coincidir con el cierre verificado en CI'))
    run_url, ci_findings = _ci_reference(data.get('ci'), repository, evidence_rel)
    findings.extend(ci_findings)
    findings.extend(_item_findings(data.get('criteria'), ids, run_url, evidence_rel))
    report_text = _read(report)
    findings.extend(_report_findings(report_text, report_rel, ids,
                                     data.get('criteria')))
    if spec_rel not in report_text or not run_url or run_url not in report_text:
        findings.append(_finding(report_rel, 'REPORT_EVIDENCE',
                                 'el reporte debe enlazar al spec y al mismo run de CI'))
    return findings


def _valid_legacy(legacy):
    if not isinstance(legacy, dict):
        return False
    for key, digest in legacy.items():
        if not isinstance(key, str) or not _PREFIX.fullmatch(key):
            return False
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            return False
    return True


def _valid_policy(policy):
    if not isinstance(policy, dict):
        return False
    repository = policy.get('repository')
    return (policy.get('schema_version') == 1
            and isinstance(repository, str)
            and bool(_REPO.fullmatch(repository))
            and _valid_legacy(policy.get('legacy_pairs')))


def _load_policy(policy_file, repository_hint=None):
    if not policy_file.exists():
        if isinstance(repository_hint, str) and _REPO.fullmatch(repository_hint):
            return (repository_hint, {}), None
        return None, _finding(str(policy_file), 'POLICY',
                              'sin politica ni repositorio explicito para validar cierres')
    try:
        policy = json.loads(_read(policy_file))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, _finding(str(policy_file), 'POLICY', str(exc))
    repository = policy.get('repository') if isinstance(policy, dict) else None
    legacy = policy.get('legacy_pairs') if isinstance(policy, dict) else None
    if not _valid_policy(policy):
        return None, _finding(str(policy_file), 'POLICY', 'politica invalida')
    if repository_hint is not None and repository != repository_hint:
        return None, _finding(str(policy_file), 'POLICY_REPOSITORY',
                              'repositorio de la politica no coincide con CI')
    return (repository, legacy), None


def _path_map(root, directory, pattern, duplicate_rule):
    paths = {}
    findings = []
    for path in sorted(directory.glob(pattern)):
        prefix = _prefix(path)
        if prefix in paths:
            findings.append(_finding(path.relative_to(root).as_posix(), duplicate_rule,
                                     'mas de un archivo para ' + prefix))
        paths[prefix] = path
    return paths, findings


def _audit_pair(context, pair, prefix):
    root, repository, legacy = context
    spec, report = pair
    if not spec or not report:
        return 'FAIL', [_finding(prefix, 'PAIR_MISSING',
                                 'spec o reporte ausente para cierre/legado')]
    if prefix in legacy:
        if _legacy_digest(spec, report) == legacy[prefix]:
            return 'SKIP', []
        return 'FAIL', [_finding(prefix, 'LEGACY_DRIFT',
                                 'par historico modificado; migrar a evidencia nueva')]
    findings = _validate_evidence(root, pair, repository)
    return ('FAIL' if findings else 'PASS'), findings


def _audit(repo_root, policy_path, specs_dir='specs', repository=None):
    root = Path(repo_root).resolve()
    policy_file = Path(policy_path)
    if not policy_file.is_absolute():
        policy_file = root / policy_file
    policy, policy_error = _load_policy(policy_file, repository)
    counts = {'PASS': 0, 'FAIL': 0, 'SKIP': 0}
    if policy_error:
        counts['FAIL'] = 1
        return [policy_error], counts
    repository, legacy = policy
    specs_root = (root / specs_dir).resolve()
    reports_root = (root / 'docs' / 'reports').resolve()
    if (not specs_root.is_relative_to(root) or not reports_root.is_relative_to(root)
            or specs_root.exists() and not specs_root.is_dir()
            or reports_root.exists() and not reports_root.is_dir()):
        counts['FAIL'] = 1
        return [_finding(specs_dir, 'DIRECTORY',
                         'specs o docs/reports no son directorios seguros')], counts
    specs, spec_findings = _path_map(root, specs_root, 'CONTRACT-*.md', 'SPEC_DUPLICATE')
    reports, report_findings = _path_map(root, reports_root, 'CONTRACT-*-REPORT.md',
                                         'REPORT_DUPLICATE')
    findings = spec_findings + report_findings
    counts['FAIL'] += len(findings)
    for prefix in sorted(set(reports) | set(legacy)):
        status, item_findings = _audit_pair((root, repository, legacy),
                                            (specs.get(prefix), reports.get(prefix)), prefix)
        findings.extend(item_findings)
        counts[status] += 1
    return sorted(findings, key=lambda item: (item['file'], item['rule'])), counts


def validate_completion(repo_root, policy_path='completion-legacy.json', specs_dir='specs', repository=None):
    return _audit(repo_root, policy_path, specs_dir, repository)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--policy', default='completion-legacy.json')
    parser.add_argument('--specs-dir', default='specs')
    parser.add_argument('--repository', help='owner/repo from the CI context')
    args = parser.parse_args(argv)
    findings, counts = _audit(args.repo_root, args.policy, args.specs_dir, args.repository)
    for finding in findings:
        print('ERROR [{}] {}: {}'.format(finding['rule'], finding['file'], finding['msg']))
    print('Summary: PASS={PASS} FAIL={FAIL} SKIP={SKIP}'.format(**counts))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
