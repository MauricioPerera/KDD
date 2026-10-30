#!/usr/bin/env python3
"""Run small deterministic Python mutants against one frozen test command."""

import argparse
import ast
import copy
import os
from pathlib import Path
import shutil
import shlex
import stat
import subprocess
import sys
import tempfile

from validate_contracts import parse_frontmatter, relative_artifact
from process_tree import run as run_process


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
        tokens = shlex.split(value, posix=os.name != "nt")
        if os.name == 'nt':
            tokens = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
        return tokens
    except ValueError as exc:
        raise ValueError("test_command invalido: {}".format(exc)) from exc


def _copy_inputs(root, destination):
    agents = os.path.abspath(os.path.join(root, '.agents'))
    def ignore(directory, names):
        excluded = {name for name in names if name in ('.git', '__pycache__')
                    or name.endswith(('.pyc', '.pyo'))}
        if os.path.abspath(directory) == agents:
            excluded.add('logs')
        return excluded
    shutil.copytree(root, destination, ignore=ignore)


def _execute(command, directory, timeout):
    try:
        completed = run_process(command, cwd=directory, capture_output=True, timeout=timeout)
        return {'exit_code': completed.returncode, 'timeout': False}
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'timeout': True}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {'exit_code': None, 'timeout': False, 'error': str(exc)}


def _control(command, root, destination, stage, timeout):
    try:
        _copy_inputs(root, destination)
        result = _execute(command, destination, timeout)
    except (OSError, ValueError) as exc:
        result = {'exit_code': None, 'timeout': False, 'error': str(exc)}
    return dict(result, stage=stage,
                status='PASS' if result['exit_code'] == 0 else 'INCONCLUSIVE')


def _target_path(root, relative):
    if relative_artifact(str(root), relative) is None:
        raise ValueError('MUTATION_PATH: exact relative target inside the project required')
    path = root
    for part in relative.split('/'):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            if not relative.lower().endswith('.py'):
                return root / relative
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('MUTATION_PATH: target aliases and reparse points are unsupported')
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('MUTATION_PATH: target must be a regular file with one link')
    return path


def _reject(reason):
    return dict(status='REJECT', reason=reason, detected=0, survived=0,
                inconclusive=0, mutants=[], controls=[])


def audit_contract(contract_path, repo_root, timeout=120):
    with open(contract_path, "r", encoding="utf-8") as fh:
        data, _body = parse_frontmatter(fh.read())
    if not isinstance(data, dict):
        return _reject('MUTATION_INPUT: task contract metadata required')
    target_rel = data.get("target", "")
    try:
        root = Path(repo_root).resolve(strict=True)
        target = _target_path(root, target_rel)
    except (OSError, ValueError) as error:
        return _reject(str(error))
    if not target_rel.lower().endswith(".py"):
        return {"status": "SKIP", "reason": "target no Python", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    with open(target, "r", encoding="utf-8") as fh:
        source = fh.read()
    mutants = mutation_sources(source)
    if not mutants:
        return {"status": "SKIP", "reason": "sin operador aplicable", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    command = _command(data["test_command"])
    outcomes, controls = [], []
    with tempfile.TemporaryDirectory(prefix="kdd-mutant-") as temporary:
        if Path(temporary).resolve().is_relative_to(root):
            return _reject('MUTATION_PATH: mutation copies must be outside the project')
        for stage in ('original', 'copy'):
            control = _control(command, root, os.path.join(temporary, stage), stage, timeout)
            controls.append(control)
            if control['status'] != 'PASS':
                return {'status': 'FAIL', 'detected': 0, 'survived': 0, 'inconclusive': 0,
                        'mutants': [], 'controls': controls}
        for index, mutant in enumerate(mutants):
            directory = os.path.join(temporary, 'mutant-' + str(index))
            try:
                _copy_inputs(root, directory)
                destination = _target_path(Path(directory).resolve(strict=True), target_rel)
                with open(destination, "w", encoding="utf-8") as fh:
                    fh.write(mutant['source'])
                result = _execute(command, directory, timeout)
            except (OSError, ValueError) as exc:
                result = {'exit_code': None, 'timeout': False, 'error': str(exc)}
            status = ('INCONCLUSIVE' if result['exit_code'] is None else
                      'DETECTED' if result['exit_code'] else 'SURVIVED')
            outcomes.append({"operator": mutant["operator"], "status": status})
    counts = {status: sum(item["status"] == status for item in outcomes)
              for status in ("DETECTED", "SURVIVED", "INCONCLUSIVE")}
    return {"status": "PASS" if not counts["SURVIVED"] and not counts["INCONCLUSIVE"] else "FAIL",
            "detected": counts["DETECTED"], "survived": counts["SURVIVED"],
            "inconclusive": counts["INCONCLUSIVE"], "mutants": outcomes, 'controls': controls}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = audit_contract(args.contract, args.repo_root)
    except (OSError, ValueError, KeyError) as error:
        result = _reject(str(error))
    if result['status'] == 'REJECT':
        print('REJECT mutation: ' + result.get('reason', 'invalid contract'))
        return 2
    for control in result.get('controls', []):
        print('control {}: {} exit={} timeout={}'.format(
            control['stage'], control['status'], control['exit_code'], control['timeout']))
    for mutant in result.get("mutants", []):
        print("{}: {}".format(mutant["operator"], mutant["status"]))
    print("mutation-audit: {} detected, {} survived, {} inconclusive".format(
        result["detected"], result["survived"], result["inconclusive"]))
    return 1 if args.strict and result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
