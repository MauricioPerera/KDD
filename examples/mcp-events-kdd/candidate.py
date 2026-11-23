"""Materialize the commit-message pilot's bounded proposal in its worktree."""

import ast
import json
import sys
from pathlib import Path


TARGET = Path("scripts/validate_commit_message.py")
ANCHOR = "    # Determine message source"
NODES = (
    ast.Expression, ast.BoolOp, ast.Or, ast.And, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Is, ast.IsNot, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.Call, ast.Name, ast.Load, ast.Constant,
)


def check_guard(guard):
    if not isinstance(guard, str) or not guard.isascii() or len(guard) > 180 or not guard.isprintable():
        raise ValueError("Expected a short single-line Python predicate")
    tree = ast.parse(guard, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, NODES):
            raise ValueError("The predicate must be a pure comparison")
        if isinstance(node, ast.Name) and node.id not in {"length", "type", "int"}:
            raise ValueError("The predicate has an undeclared name")
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name) or node.func.id != "type"
            or len(node.args) != 1 or not isinstance(node.args[0], ast.Name)
            or node.args[0].id != "length" or node.keywords
        ):
            raise ValueError("Only type(length) may be called")


def candidate_bytes(proposal):
    if set(proposal) != {"guard", "diagnostic"}:
        raise ValueError("Expected a guard and diagnostic")
    guard, diagnostic = proposal["guard"], proposal["diagnostic"]
    check_guard(guard)
    if (
        not isinstance(diagnostic, str) or not diagnostic.isascii()
        or not diagnostic.isprintable() or len(diagnostic) > 120
        or "max_subject_length" not in diagnostic
    ):
        raise ValueError("The diagnostic must name the setting in plain ASCII")
    source = TARGET.read_bytes()
    newline = "\r\n" if b"\r\n" in source else "\n"
    check = [
        "    length = config['max_subject_length']",
        f"    if {guard}:",
        f"        print({('ERROR [CONFIG_INVALID] ' + diagnostic)!r}, file=sys.stderr)",
        "        print()",
        '        print("Resumen: 1 error(es), 0 warning(s)")',
        "        return 1",
        "",
        ANCHOR,
    ]
    anchor = ANCHOR.encode("ascii")
    if source.count(anchor) != 1 or b"    length = config[" in source:
        raise ValueError("Expected the unmodified CLI entry point")
    candidate = source.replace(anchor, newline.join(check).encode("ascii"))
    ast.parse(candidate.decode("utf-8"))
    return candidate


if __name__ == "__main__":
    candidate = candidate_bytes(json.load(sys.stdin))
    if sys.argv[1:] == ["--preview"]:
        sys.stdout.buffer.write(candidate)
    elif not sys.argv[1:]:
        TARGET.write_bytes(candidate)
    else:
        raise SystemExit("Usage: candidate.py [--preview]")
