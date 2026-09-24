#!/usr/bin/env python3
"""Enforce declared complexity budgets for Python task targets.

Deterministic, stdlib-only, and intentionally independent from external
complexity packages. Non-Python targets are reported as skipped because this
gate only claims Python metrics.
"""

import argparse
import ast
import os
import sys

from validate_contracts import Finding, parse_frontmatter


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


def _budget_findings(contract_name, target, budget):
    findings = []
    try:
        with open(target, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=target)
    except (OSError, SyntaxError) as exc:
        return [Finding(contract_name, "BUDGET_PARSE", str(exc))]

    for function in _functions(tree):
        name = "{}:{}".format(contract_name, function.name)
        metrics = {
            "cyclomatic_max": _cyclomatic(function),
            "nesting_max": _nesting(function),
            "lines_max": (function.end_lineno - function.lineno + 1),
            "params_max": _parameters(function),
        }
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contracts_dir", nargs="?", default="knowledge/contracts")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--contract", help="validate only one task contract")
    args = parser.parse_args(argv)
    findings = validate_directory(args.contracts_dir, args.repo_root, args.contract)
    for finding in findings:
        print(finding)
    print("OK: budgets dentro de limites" if not findings else
          "FAIL: {} budget(s) fuera de limites".format(len(findings)))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
