#!/usr/bin/env python3
"""Run a named KDD validation profile with deterministic command ordering."""

import argparse
import os
import subprocess
import sys


_MINIMAL = (
    ("contracts", ("python", "scripts/validate_contracts.py", "knowledge/contracts")),
    ("suite", ("python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")),
)
_STANDARD = _MINIMAL + (
    ("specs", ("python", "scripts/validate_specs.py", "specs")),
    ("okf", ("python", "scripts/validate_okf.py", "knowledge")),
    ("ascii", ("python", "scripts/lint_ascii.py", "scripts")),
    ("rules", ("python", "scripts/validate_rules.py", "examples/rules")),
    ("skills", ("python", "scripts/validate_skills.py", "skills", ".agents/skills")),
    ("changelog", ("python", "scripts/validate_changelog.py")),
    ("secrets", ("python", "scripts/scan_secrets.py", "src")),
)
_PROFILES = {
    "minimal": _MINIMAL,
    "standard": _STANDARD,
    "strict": _STANDARD + (
        ("budgets", ("python", "scripts/validate_budgets.py", "knowledge/contracts", "--repo-root", ".")),
        ("seal_audit", ("python", "scripts/audit_seals.py", "knowledge/contracts", "--strict")),
        ("forbids_audit", ("python", "scripts/audit_forbids.py", "knowledge/contracts", "--strict")),
        ("preflight", ("python", "scripts/preflight.py", "--agent")),
    ),
}


def build_profile(name, mutation_contract=None):
    if mutation_contract and name != "strict":
        raise ValueError("--mutation-contract requiere el perfil strict")
    try:
        profile = list(_PROFILES[name])
    except KeyError as exc:
        raise ValueError("perfil desconocido: {} (use minimal, standard o strict)".format(name)) from exc
    if mutation_contract:
        profile.append(("mutation", ("python", "scripts/mutation_audit.py",
                                      mutation_contract, "--repo-root", ".", "--strict")))
    return profile


def _run_command(command, cwd):
    completed = subprocess.run(command, cwd=cwd)
    return completed.returncode


def run_profile(name, repo_root, mutation_contract=None, runner=None):
    runner = runner or _run_command
    results = []
    for step, command in build_profile(name, mutation_contract):
        exit_code = runner(command, repo_root)
        results.append({"step": step, "command": list(command), "exit_code": exit_code})
        if exit_code != 0:
            return {"profile": name, "ok": False, "results": results, "failed_at": step}
    return {"profile": name, "ok": True, "results": results, "failed_at": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(_PROFILES), default="standard")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mutation-contract", help="contract to mutate in strict mode")
    args = parser.parse_args(argv)
    result = run_profile(args.profile, os.path.abspath(args.repo_root), args.mutation_contract)
    for item in result["results"]:
        print("{}: {}".format(item["step"], "PASS" if item["exit_code"] == 0 else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
