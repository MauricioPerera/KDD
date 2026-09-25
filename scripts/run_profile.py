#!/usr/bin/env python3
"""Run a named KDD validation profile with deterministic command ordering."""

import argparse
import os
import re
import subprocess
import sys


_MINIMAL = (
    ("contracts", ("python", "scripts/validate_contracts.py", "knowledge/contracts")),
    ("suite", ("python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")),
)
_STANDARD = (
    _MINIMAL[0],
    ("approved_baseline", ("python", "scripts/validate_baseline.py", "--all", "--approved-ref", "@approved_ref@")),
    _MINIMAL[1],
    ("contract_tests", ("python", "scripts/validate_test_commands.py", "knowledge/contracts", ".")),
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


def _with_approved_ref(profile, approved_ref):
    if not approved_ref or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", approved_ref):
        raise ValueError("standard/strict requieren --approved-ref con el SHA completo de un commit aprobado")
    return [(step, tuple(approved_ref if arg == "@approved_ref@" else arg for arg in command))
            for step, command in profile]


def _with_budget_contract(profile, budget_contract):
    for index, (step, _command) in enumerate(profile):
        if step == "budgets":
            profile[index] = (step, ("python", "scripts/validate_budgets.py",
                                     "knowledge/contracts", "--repo-root", ".",
                                     "--contract", budget_contract))
            break
    return profile


def build_profile(name, mutation_contract=None, budget_contract=None, approved_ref=None):
    if (mutation_contract or budget_contract) and name != "strict":
        raise ValueError("--mutation-contract y --budget-contract requieren el perfil strict")
    try:
        profile = list(_PROFILES[name])
    except KeyError as exc:
        raise ValueError("perfil desconocido: {} (use minimal, standard o strict)".format(name)) from exc
    if name != "minimal":
        profile = _with_approved_ref(profile, approved_ref)
    if mutation_contract:
        profile.append(("mutation", ("python", "scripts/mutation_audit.py",
                                      mutation_contract, "--repo-root", ".", "--strict")))
    if budget_contract:
        profile = _with_budget_contract(profile, budget_contract)
    return profile


def _run_command(command, cwd):
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"exit_code": 1, "output": str(exc)}
    return {"exit_code": completed.returncode,
            "output": (completed.stdout or "") + (completed.stderr or "")}


def _is_skipped(step, output):
    if "INFO [PATH_MISSING]" in output or output.lstrip().startswith("SKIP:"):
        return True
    if step == "contract_tests":
        return bool(re.search(r"^SKIP \[(?:product|infrastructure)\]", output, re.MULTILINE))
    if step == "preflight":
        return bool(re.search(r"^Skipped: [1-9][0-9]*", output, re.MULTILINE))
    return False


def _result_item(step, command, outcome):
    exit_code = outcome["exit_code"] if isinstance(outcome, dict) else outcome
    output = outcome.get("output", "") if isinstance(outcome, dict) else ""
    status = "FAIL" if exit_code != 0 else ("SKIP" if _is_skipped(step, output) else "PASS")
    category = ("product_and_infrastructure" if step == "contract_tests" else
                "suite_unspecified" if step == "suite" else "infrastructure")
    suite_skips = re.search(r"^OK \(skipped=([0-9]+)\)", output, re.MULTILINE) if step == "suite" else None
    return {"step": step, "category": category, "status": status,
            "command": list(command), "exit_code": exit_code, "output": output,
            "skipped_tests": int(suite_skips.group(1)) if suite_skips else 0}


def run_profile(name, repo_root, mutation_contract=None, budget_contract=None, runner=None,
                approved_ref=None):
    runner = runner or _run_command
    results = []
    for step, command in build_profile(name, mutation_contract, budget_contract, approved_ref):
        item = _result_item(step, command, runner(command, repo_root))
        results.append(item)
        if item["exit_code"] != 0:
            return {"profile": name, "ok": False, "results": results, "failed_at": step}
    return {"profile": name, "ok": True, "results": results, "failed_at": None}


def _print_item(item):
    detail = " ({} tests SKIP)".format(item["skipped_tests"]) if item["skipped_tests"] else ""
    print("{} [{}]: {}{}".format(item["step"], item["category"], item["status"], detail))
    if item["step"] != "contract_tests" and item["status"] == "PASS":
        return
    lines = item["output"].splitlines()
    if item["status"] != "FAIL":
        lines = [line for line in lines if line.startswith(("PASS [", "FAIL [", "Summary:", "SKIP ", "Skipped:")) or
                 (item["status"] == "SKIP" and "INFO [PATH_MISSING]" in line)]
    for line in lines:
        print("  " + line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(_PROFILES), default="standard")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--mutation-contract", help="contract to mutate in strict mode")
    parser.add_argument("--budget-contract", help="contract whose budget is enforced in strict mode")
    parser.add_argument("--approved-ref", help="full commit SHA approved outside the implementing agent")
    args = parser.parse_args(argv)
    try:
        result = run_profile(args.profile, os.path.abspath(args.repo_root),
                             args.mutation_contract, args.budget_contract,
                             approved_ref=args.approved_ref)
    except ValueError as exc:
        parser.error(str(exc))
    for item in result["results"]:
        _print_item(item)
    counts = {status: sum(item["status"] == status for item in result["results"])
              for status in ("PASS", "FAIL", "SKIP")}
    print("Summary: PASS={PASS} FAIL={FAIL} SKIP={SKIP}".format(**counts))
    suite_skips = sum(item["skipped_tests"] for item in result["results"])
    if suite_skips:
        print("Skipped tests inside suite: {}".format(suite_skips))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
