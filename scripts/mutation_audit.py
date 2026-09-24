#!/usr/bin/env python3
"""Run small deterministic Python mutants against one frozen test command."""

import argparse
import ast
import copy
import os
import shutil
import shlex
import subprocess
import sys
import tempfile

from validate_contracts import parse_frontmatter


class _FirstMutation(ast.NodeTransformer):
    def __init__(self, operator):
        self.operator = operator
        self.changed = False

    def visit_Constant(self, node):
        if self.operator == "invert-bool" and not self.changed and isinstance(node.value, bool):
            self.changed = True
            return ast.copy_location(ast.Constant(value=not node.value), node)
        return self.generic_visit(node)

    def visit_Compare(self, node):
        if self.operator == "flip-comparison" and not self.changed and node.ops:
            flips = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
                     ast.Lt: ast.GtE, ast.GtE: ast.Lt,
                     ast.Gt: ast.LtE, ast.LtE: ast.Gt}
            operator_type = type(node.ops[0])
            if operator_type in flips:
                node = copy.deepcopy(node)
                node.ops[0] = flips[operator_type]()
                self.changed = True
                return node
        return self.generic_visit(node)

    def visit_If(self, node):
        if self.operator == "negate-branch" and not self.changed:
            node = copy.deepcopy(node)
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            self.changed = True
            return node
        return self.generic_visit(node)


def mutation_sources(source):
    results = []
    tree = ast.parse(source)
    for operator in ("invert-bool", "flip-comparison", "negate-branch"):
        mutant = _FirstMutation(operator)
        mutated_tree = mutant.visit(copy.deepcopy(tree))
        if mutant.changed:
            results.append({"operator": operator,
                            "source": ast.unparse(ast.fix_missing_locations(mutated_tree)) + "\n"})
    return results


def _command(value):
    try:
        return shlex.split(value, posix=os.name != "nt")
    except ValueError as exc:
        raise ValueError("test_command invalido: {}".format(exc)) from exc


def audit_contract(contract_path, repo_root, timeout=120):
    with open(contract_path, "r", encoding="utf-8") as fh:
        data, _body = parse_frontmatter(fh.read())
    if not isinstance(data, dict):
        return {"status": "REJECT", "detected": 0, "survived": 0, "inconclusive": 0, "mutants": []}
    target_rel = data.get("target", "")
    if not target_rel.lower().endswith(".py"):
        return {"status": "SKIP", "reason": "target no Python", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    target = os.path.join(repo_root, target_rel)
    with open(target, "r", encoding="utf-8") as fh:
        source = fh.read()
    mutants = mutation_sources(source)
    if not mutants:
        return {"status": "SKIP", "reason": "sin operador aplicable", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    command = _command(data["test_command"])
    outcomes = []
    for mutant in mutants:
        temp = tempfile.mkdtemp(prefix="kdd-mutant-")
        try:
            shutil.copytree(repo_root, temp, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", ".agents"))
            mutated_target = os.path.join(temp, target_rel)
            with open(mutated_target, "w", encoding="utf-8") as fh:
                fh.write(mutant["source"])
            try:
                completed = subprocess.run(command, cwd=temp, capture_output=True,
                                           timeout=timeout, check=False)
                status = "DETECTED" if completed.returncode else "SURVIVED"
            except subprocess.TimeoutExpired:
                status = "INCONCLUSIVE"
            outcomes.append({"operator": mutant["operator"], "status": status})
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    counts = {status: sum(item["status"] == status for item in outcomes)
              for status in ("DETECTED", "SURVIVED", "INCONCLUSIVE")}
    return {"status": "PASS" if not counts["SURVIVED"] and not counts["INCONCLUSIVE"] else "FAIL",
            "detected": counts["DETECTED"], "survived": counts["SURVIVED"],
            "inconclusive": counts["INCONCLUSIVE"], "mutants": outcomes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    result = audit_contract(args.contract, args.repo_root)
    for mutant in result.get("mutants", []):
        print("{}: {}".format(mutant["operator"], mutant["status"]))
    print("mutation-audit: {} detected, {} survived, {} inconclusive".format(
        result["detected"], result["survived"], result["inconclusive"]))
    return 1 if args.strict and result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
