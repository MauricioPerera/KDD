"""Reject new or increased Python complexity violations between Git commits."""

import argparse
import ast
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from validate_budgets import _metrics, _RULES
from validate_contracts import parse_frontmatter


REGULAR = {'100644', '100755'}


def git(root, *args, data=None, code='BUDGET_GIT'):
    result = subprocess.run(['git', '--no-replace-objects', '--literal-pathspecs',
                             '-C', str(root), *args], input=data, capture_output=True,
                            timeout=30, check=False)
    if result.returncode:
        detail = result.stderr.decode('utf-8', 'replace').strip()
        raise ValueError(code + ': ' + (detail or 'Git rejected the comparison'))
    return result.stdout


def compare_refs(root, base, head):
    algorithm = git(root, 'rev-parse', '--show-object-format').decode('ascii').strip()
    width = {'sha1': 40, 'sha256': 64}.get(algorithm)
    if not width or git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('BUDGET_REF: complete Git history and native commit IDs are required')
    for reference in (base, head):
        if len(reference) != width or not re.fullmatch(r'[0-9a-f]+', reference):
            raise ValueError('BUDGET_REF: use full native commit IDs')
        original = git(root, 'rev-parse', '--verify', '--end-of-options',
                       reference + '^{commit}', code='BUDGET_REF')
        if original.strip() != reference.encode('ascii'):
            raise ValueError('BUDGET_REF: reference must identify an original commit')
    git(root, 'merge-base', '--is-ancestor', base, head, code='BUDGET_REF')


def tree(root, reference):
    entries = {}
    for line in git(root, 'ls-tree', '-rz', '--full-tree', reference).split(b'\0')[:-1]:
        header, path = line.split(b'\t', 1)
        mode, _, oid = header.decode('ascii').split()
        entries[path.decode('utf-8')] = (mode, oid)
    return entries


def exact_path(path):
    if (not isinstance(path, str) or not path or '\\' in path or ':' in path or '\0' in path
            or any(part in ('', '.', '..', '.git') for part in path.split('/'))):
        raise ValueError('BUDGET_CONTRACT: expected an exact repository path')
    return path


def blob_id(entries, path):
    mode, oid = entries.get(path, ('', ''))
    if mode not in REGULAR:
        raise ValueError('BUDGET_OBJECT: expected a regular blob at ' + path)
    return oid


def blobs(root, ids):
    objects = {}
    ordered = list(dict.fromkeys(ids))
    for index in range(0, len(ordered), 32):
        chunk = ordered[index:index + 32]
        data = git(root, 'cat-file', '--batch', data=('\n'.join(chunk) + '\n').encode('ascii'))
        offset = 0
        for oid in chunk:
            end = data.index(b'\n', offset)
            fields = data[offset:end].split()
            if len(fields) != 3 or fields[:2] != [oid.encode('ascii'), b'blob']:
                raise ValueError('BUDGET_OBJECT: expected original blob ' + oid)
            start, stop = end + 1, end + 1 + int(fields[2])
            if data[stop:stop + 1] != b'\n':
                raise ValueError('BUDGET_OBJECT: incomplete original blob ' + oid)
            objects[oid], offset = data[start:stop], stop + 1
        if offset != len(data):
            raise ValueError('BUDGET_OBJECT: unexpected object output')
    return objects


def contract_paths(entries, directory):
    for path in entries:
        name = PurePosixPath(path)
        if (name.parent.as_posix() == directory and name.suffix == '.md'
                and not name.name.startswith('TEMPLATE-')):
            yield path


def contract_policy(raw, path):
    data, _ = parse_frontmatter(raw.decode('utf-8'))
    if not isinstance(data, dict) or data.get('type') != 'Task Contract':
        raise ValueError('BUDGET_CONTRACT: invalid task contract ' + path)
    target = exact_path(data.get('target'))
    budget = data.get('budget')
    if not target.lower().endswith('.py') or str(data.get('language', 'python')).lower() != 'python':
        return None
    if not isinstance(budget, dict) or not budget:
        raise ValueError('BUDGET_CONTRACT: missing Python budget in ' + path)
    if set(budget) - _RULES.keys() or any(
            type(limit) not in (int, str) or not re.fullmatch(r'[1-9][0-9]*', str(limit))
            for limit in budget.values()):
        raise ValueError('BUDGET_CONTRACT: invalid Python budget in ' + path)
    return data, target, {key: int(limit) for key, limit in budget.items()}


class Functions(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.values = {}

    def descend(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node):
        self.descend(node)

    def visit_FunctionDef(self, node):
        name = '.'.join((*self.scope, node.name))
        if name in self.values:
            raise ValueError('BUDGET_PARSE: ambiguous qualified function name ' + name)
        self.values[name] = (ast.dump(node, include_attributes=False), _metrics(node))
        self.descend(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def functions(raw, path):
    visitor = Functions()
    try:
        visitor.visit(ast.parse(raw, filename=path))
    except (SyntaxError, ValueError) as exc:
        raise ValueError('BUDGET_PARSE: ' + path + ': ' + str(exc)) from exc
    return visitor.values


def check_seal(raw, expected, contract):
    normalized = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    if hashlib.sha256(normalized.encode('utf-8')).hexdigest() != expected:
        raise ValueError('BUDGET_CONTRACT: invalid oracle seal in ' + contract)


def comparisons(root, before, after, directory):
    paths = {path: (before, False) for path in contract_paths(before, directory)}
    for path in contract_paths(after, directory):
        paths.setdefault(path, (after, True))
    contents = blobs(root, (blob_id(entries, path) for path, (entries, _) in paths.items()))
    for path, (entries, new) in sorted(paths.items()):
        policy = contract_policy(contents[blob_id(entries, path)], path)
        if policy is None:
            continue
        data, target, budget = policy
        if new:
            oracle = blob_id(after, exact_path(data.get('tests')))
            check_seal(blobs(root, [oracle])[oracle], data.get('tests_sha256'), path)
            blob_id(after, target)
        if target not in after or before.get(target) == after[target]:
            continue
        old = blob_id(before, target) if target in before else None
        yield path, target, budget, old, blob_id(after, target)


def overruns(contract, target, budget, original, candidate):
    findings = []
    for name, current in sorted(candidate.items()):
        previous = original.get(name)
        if current == previous:
            continue
        print('MEASURE %s %s:%s %s' % (contract, target, name, current[1]))
        for key, limit in budget.items():
            value = current[1][key]
            if value > limit and (previous is None or value > previous[1][key]):
                findings.append('ERROR [%s] %s %s:%s %s=%s exceeds %s' %
                                (_RULES[key], contract, target, name, key, value, limit))
    return findings


def audit(root, directory, base, head):
    compare_refs(root, base, head)
    jobs = list(comparisons(root, tree(root, base), tree(root, head), directory))
    contents = blobs(root, (oid for job in jobs for oid in job[-2:] if oid))
    parsed = {}
    findings = []
    for contract, target, budget, old, new in jobs:
        for oid in (old, new):
            if oid is not None and oid not in parsed:
                parsed[oid] = functions(contents[oid], target)
        findings.extend(overruns(contract, target, budget, parsed.get(old, {}), parsed[new]))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contracts_dir')
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--base-ref', required=True)
    parser.add_argument('--head-ref', required=True)
    args = parser.parse_args()
    try:
        findings = audit(Path(args.repo_root).resolve(strict=True),
                         exact_path(args.contracts_dir), args.base_ref, args.head_ref)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('FAIL changed budgets: ' + str(error), file=sys.stderr)
        return 1
    for finding in findings:
        print(finding)
    print('%s: %s changed Python budget finding(s)' %
          ('FAIL' if findings else 'OK', len(findings)))
    return int(bool(findings))


if __name__ == '__main__':
    sys.exit(main())
