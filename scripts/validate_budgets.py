#!/usr/bin/env python3
"""Enforce declared complexity budgets for Python task targets.

Deterministic, stdlib-only, and independent from external complexity packages.
Legacy validation omits non-Python targets. Required measurement rejects
unsupported inputs and zero coverage, and reports the measured source version.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from validate_contracts import Finding, parse_frontmatter, relative_artifact, validate_file


def _functions(tree):
    return [node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _cyclomatic(node):
    branches = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While,
                              ast.ExceptHandler, ast.IfExp, ast.match_case)):
            branches += 1
        elif isinstance(child, ast.BoolOp):
            branches += max(0, len(child.values) - 1)
    return 1 + branches


def _nesting(node, depth=0):
    compound = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
                ast.With, ast.AsyncWith, ast.Match)
    maximum = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, compound) else depth
        maximum = max(maximum, _nesting(child, child_depth))
    return maximum


def _parameters(node):
    args = node.args
    return (len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
            + bool(args.vararg) + bool(args.kwarg))


def _metrics(function):
    return {
        'cyclomatic_max': _cyclomatic(function),
        'nesting_max': _nesting(function),
        'lines_max': function.end_lineno - function.lineno + 1,
        'params_max': _parameters(function),
    }


def _budget_findings(contract_name, target, budget):
    findings = []
    try:
        with open(target, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=target)
    except (OSError, SyntaxError) as exc:
        return [Finding(contract_name, "BUDGET_PARSE", str(exc))]

    for function in _functions(tree):
        name = "{}:{}".format(contract_name, function.name)
        metrics = _metrics(function)
        rules = {
            "cyclomatic_max": "BUDGET_CYCLOMATIC",
            "nesting_max": "BUDGET_NESTING",
            "lines_max": "BUDGET_LINES",
            "params_max": "BUDGET_PARAMS",
        }
        for key, actual in metrics.items():
            if key in budget and actual > int(budget[key]):
                findings.append(Finding(
                    name, rules[key],
                    "{}={} excede {}={}".format(key, actual, key, budget[key])))
    return findings


def validate_directory(contracts_dir, repo_root, contract_name=None):
    findings = []
    for filename in sorted(os.listdir(contracts_dir)):
        if not filename.endswith(".md") or filename.startswith("TEMPLATE-"):
            continue
        if contract_name and filename != "{}.md".format(contract_name):
            continue
        contract_path = os.path.join(contracts_dir, filename)
        with open(contract_path, "r", encoding="utf-8") as fh:
            data, _body = parse_frontmatter(fh.read())
        if not isinstance(data, dict) or not isinstance(data.get("budget"), dict):
            continue
        target = os.path.join(repo_root, data.get("target", ""))
        if not target.lower().endswith(".py") or not os.path.isfile(target):
            continue
        findings.extend(_budget_findings(filename, target, data["budget"]))
    return findings


_RULES = {'cyclomatic_max': 'BUDGET_CYCLOMATIC', 'nesting_max': 'BUDGET_NESTING',
          'lines_max': 'BUDGET_LINES', 'params_max': 'BUDGET_PARAMS'}


def _required_path(root, relative, code):
    absolute = relative_artifact(str(root), relative)
    if absolute is None:
        raise ValueError(code + ': an exact confined path is required')
    path = root
    try:
        for part in Path(absolute).relative_to(root).parts:
            path = path / part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError(code + ': filesystem aliases are not supported')
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(code + ': a regular file with one link is required')
    except OSError as error:
        raise ValueError(code + ': input is unavailable') from error
    return path


def _required_metadata(path, root):
    relative = path.relative_to(root).as_posix()
    contract = _required_path(root, relative, 'BUDGET_CONTRACT')
    metadata, _ = parse_frontmatter(contract.read_text(encoding='utf-8'))
    if not isinstance(metadata, dict) or not isinstance(metadata.get('budget'), dict):
        raise ValueError('BUDGET_CONTRACT: declared budget metadata is required')
    budget = metadata['budget']
    if set(budget) - set(_RULES):
        raise ValueError('BUDGET_UNSUPPORTED: unsupported required metric')
    target = _required_path(root, metadata.get('target'), 'BUDGET_TARGET')
    language = str(metadata.get('language', 'python')).lower()
    if target.suffix.lower() != '.py' or language != 'python':
        raise ValueError('BUDGET_UNSUPPORTED: required measurement supports Python only')
    errors = [str(row) for row in validate_file(str(contract), repo_root=str(root))
              if row.level == 'ERROR']
    if errors:
        raise ValueError('BUDGET_CONTRACT: ' + '; '.join(errors))
    return metadata, target, {key: int(value) for key, value in budget.items()}


def _required_measurement(path, root):
    metadata, target, budget = _required_metadata(path, root)
    try:
        raw = target.read_bytes()
        normalized = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        tree = ast.parse(normalized.decode('utf-8'), filename=metadata['target'])
    except (OSError, ValueError, SyntaxError) as error:
        raise ValueError('BUDGET_PARSE: Python measurement could not parse its source') from error
    functions = [{'name': function.name, 'line': function.lineno, 'metrics': _metrics(function)}
                 for function in _functions(tree)]
    if not functions:
        raise ValueError('BUDGET_COVERAGE: no functions were measured')
    return {'contract': path.relative_to(root).as_posix(), 'target': metadata['target'],
            'method': 'python-ast', 'language': 'python', 'scope': 'module-functions',
            'hash_method': 'sha256-lf', 'target_sha256': hashlib.sha256(normalized).hexdigest(),
            'target_raw_sha256': hashlib.sha256(raw).hexdigest(),
            'budget': budget, 'functions': functions}


def _required_overruns(measurement):
    findings = []
    for function in measurement['functions']:
        for key, limit in measurement['budget'].items():
            actual = function['metrics'][key]
            if actual > limit:
                findings.append({'file': measurement['contract'], 'rule': _RULES[key],
                    'message': '%s: %s=%s exceeds %s=%s' % (function['name'], key, actual, key, limit)})
    return findings


def measure_required(contracts_dir, repo_root, contract_name=None):
    root, measurements, findings, checked = Path(repo_root).resolve(), [], [], 0
    try:
        directory = Path(contracts_dir).resolve()
        paths = [path for path in sorted(directory.iterdir()) if path.name.endswith('.md')
                 and not path.name.startswith('TEMPLATE-')
                 and (not contract_name or path.name == str(contract_name) + '.md')]
        if not paths:
            raise ValueError('BUDGET_COVERAGE: required selector has no contracts')
        for path in paths:
            checked += 1
            try:
                measurement = _required_measurement(path, root)
                measurements.append(measurement)
                findings.extend(_required_overruns(measurement))
            except (OSError, ValueError) as error:
                rule, _, message = str(error).partition(':')
                findings.append({'file': path.name, 'rule': rule if rule.startswith('BUDGET_')
                                 else 'BUDGET_CONTRACT', 'message': message or str(error)})
    except (OSError, ValueError) as error:
        findings.append({'file': str(contracts_dir), 'rule': 'BUDGET_COVERAGE', 'message': str(error)})
    return {'schema_version': 1, 'status': 'FAIL' if findings else 'PASS',
            'contracts_checked': checked,
            'functions_measured': sum(len(row['functions']) for row in measurements),
            'measurements': measurements, 'findings': findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contracts_dir", nargs="?", default="knowledge/contracts")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", help="validate only one task contract")
    parser.add_argument('--required', action='store_true', help='require supported, positive measured coverage')
    parser.add_argument('--json', action='store_true', help='emit the required measurement receipt as JSON')
    args = parser.parse_args(argv)
    if args.required:
        report = measure_required(args.contracts_dir, args.repo_root, args.contract)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 0 if report['status'] == 'PASS' else 1
    if args.json:
        parser.error('--json requires --required')
    findings = validate_directory(args.contracts_dir, args.repo_root, args.contract)
    for finding in findings:
        print(finding)
    print("OK: budgets dentro de limites" if not findings else
          "FAIL: {} budget(s) fuera de limites".format(len(findings)))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
