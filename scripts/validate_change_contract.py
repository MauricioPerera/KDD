#!/usr/bin/env python3
"""Audit an implementation diff against an independently approved contract."""

import argparse
import ast
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

from validate_budgets import _budget_findings
from validate_contracts import parse_frontmatter
from validate_perimeter import validate_perimeter
from change_contract_multilang import audit_source


_SHA = re.compile(r'[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?')


def _finding(rule, path, message):
    return {'rule': rule, 'path': path, 'msg': message}


def _safe_path(path):
    if not isinstance(path, str):
        return False
    value = PurePosixPath(path.replace('\\', '/'))
    return (bool(path) and not value.is_absolute()
            and '..' not in value.parts and value.as_posix() != '.')


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('Git command failed: ' + ' '.join(args))
    return result.stdout


def _blob(root, sha, path):
    result = subprocess.run(['git', '-C', str(root), 'show', sha + ':' + path],
                            capture_output=True, timeout=30, check=False)
    return result.stdout if result.returncode == 0 else None


def _changed_paths(root, base_ref, head_ref):
    _git(root, 'merge-base', '--is-ancestor', base_ref, head_ref)
    changed = _git(root, 'diff', '--name-only', '-z', base_ref, head_ref)
    return sorted(path.decode('utf-8') for path in changed.split(b'\0') if path)


def _perimeter_findings(contract_text, contract_path, changed):
    with tempfile.TemporaryDirectory(prefix='kdd-contract-') as temp:
        path = Path(temp) / 'contract.md'
        path.write_text(contract_text, encoding='utf-8')
        result = validate_perimeter(str(path), changed)
    return [_finding(item['rule'], contract_path, item['msg'])
            for item in result if item['level'] == 'ERROR']


def _imports(source, path):
    tree = ast.parse(source, filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or '').split('.')[0])
    return names - {''}


def _is_local(root, head_ref, target, module):
    parent = PurePosixPath(target).parent
    prefixes = [module + '.py', module + '/']
    if parent != PurePosixPath('.'):
        prefixes.extend([str(parent / (module + '.py')),
                         str(parent / module) + '/'])
    tree = _git(root, 'ls-tree', '-r', '--name-only', head_ref, '--', *prefixes)
    return bool(tree.strip())


def _dependency_findings(root, head_ref, target, sources, allowed):
    try:
        before, after = sources
        new_imports = _imports(after, target) - _imports(before, target)
    except SyntaxError as exc:
        return [_finding('DEP_PARSE', target, str(exc))]
    permitted = {name.casefold() for name in allowed if isinstance(name, str)}
    findings = []
    for module in sorted(new_imports):
        if (module in sys.stdlib_module_names or module in sys.builtin_module_names
                or module.casefold() in permitted
                or _is_local(root, head_ref, target, module)):
            continue
        findings.append(_finding('DEP_UNDECLARED', target,
                                 'new external import not in deps_allowed: ' + module))
    return findings


def _multilang_findings(root, target, data, base_ref, head_ref):
    suffix = PurePosixPath(target).suffix
    manifest_name = ('package.json' if suffix in ('.js', '.jsx', '.ts', '.tsx')
                     else 'go.mod' if suffix == '.go'
                     else 'Cargo.toml' if suffix == '.rs' else None)
    if manifest_name is None:
        return [_finding('CHECK_UNSUPPORTED', target,
                         'dependency and budget checks have no adapter')]
    parent = PurePosixPath(target).parent
    candidates = []
    while True:
        candidates.append(str(parent / manifest_name)
                          if parent != PurePosixPath('.') else manifest_name)
        if parent == PurePosixPath('.'):
            break
        parent = parent.parent
    manifest = next((name for name in candidates
                     if _blob(root, head_ref, name) is not None), None)
    if manifest is None:
        return [_finding('MANIFEST_PARSE', target,
                         'required dependency manifest is missing')]
    try:
        manifests = {
            'before': (_blob(root, base_ref, manifest) or b'').decode('utf-8'),
            'after': _blob(root, head_ref, manifest).decode('utf-8'),
        }
    except UnicodeError as exc:
        return [_finding('MANIFEST_PARSE', target, str(exc))]
    return audit_source(target, _blob(root, base_ref, target) or b'',
                        _blob(root, head_ref, target), data, manifests)


def _target_findings(root, data, base_ref, head_ref, changed):
    target = data.get('target')
    if not _safe_path(target):
        return [_finding('CONTRACT_TARGET', str(target), 'invalid target path')]
    target = target.replace('\\', '/')
    if target not in changed:
        return []
    after_bytes = _blob(root, head_ref, target)
    if after_bytes is None:
        return [_finding('TARGET_MISSING', target, 'target missing at candidate SHA')]
    if not target.endswith('.py'):
        return _multilang_findings(root, target, data, base_ref, head_ref)
    try:
        after = after_bytes.decode('utf-8')
        before = (_blob(root, base_ref, target) or b'').decode('utf-8')
    except UnicodeError as exc:
        return [_finding('TARGET_ENCODING', target, str(exc))]
    findings = _dependency_findings(root, head_ref, target, (before, after),
                                    data.get('deps_allowed', []))
    with tempfile.TemporaryDirectory(prefix='kdd-target-') as temp:
        path = Path(temp) / 'candidate.py'
        path.write_text(after, encoding='utf-8')
        for item in _budget_findings(target, str(path), data.get('budget', {})):
            findings.append(_finding(item.rule, target, item.message))
    return findings


def audit_change(repo_root, contract_path, base_ref, head_ref):
    """Return deterministic findings for a Git diff under baseline policy."""
    if not _safe_path(contract_path):
        return [_finding('CONTRACT_PATH', str(contract_path),
                         'contract path must be repo-relative')]
    contract_path = contract_path.replace('\\', '/')
    if not (_SHA.fullmatch(base_ref) and _SHA.fullmatch(head_ref)):
        return [_finding('GIT_RANGE', contract_path, 'full commit SHAs required')]
    try:
        changed = _changed_paths(repo_root, base_ref, head_ref)
        contract_bytes = _blob(repo_root, base_ref, contract_path)
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return [_finding('GIT_RANGE', contract_path,
                         'baseline is unavailable or not an ancestor')]
    if contract_bytes is None:
        return [_finding('CONTRACT_BASE', contract_path,
                         'contract absent from approved baseline')]
    try:
        contract_text = contract_bytes.decode('utf-8')
        data, _body = parse_frontmatter(contract_text)
    except UnicodeError as exc:
        return [_finding('CONTRACT_BASE', contract_path, str(exc))]
    if not isinstance(data, dict):
        return [_finding('CONTRACT_BASE', contract_path,
                         'invalid approved contract')]
    try:
        findings = _perimeter_findings(contract_text, contract_path, changed)
        findings.extend(_target_findings(repo_root, data, base_ref,
                                         head_ref, changed))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return [_finding('AUDIT_ERROR', contract_path, str(exc))]
    return sorted(findings, key=lambda item: (item['path'], item['rule'],
                                              item['msg']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--contract', required=True)
    parser.add_argument('--base-ref', required=True)
    parser.add_argument('--head-ref', required=True)
    args = parser.parse_args(argv)
    findings = audit_change(args.repo_root, args.contract, args.base_ref,
                            args.head_ref)
    for item in findings:
        print('ERROR [{}] {}: {}'.format(item['rule'], item['path'], item['msg']))
    print('Summary: FAIL={}'.format(len(findings)))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
