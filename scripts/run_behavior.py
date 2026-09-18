#!/usr/bin/env python3
"""Execute a validated behavior/v1 contract through trusted adapters.

The adapter registry belongs to the reviewer/CI configuration, never to the
candidate. This command intentionally remains opt-in: validation alone is a
safe Level 1 check; executing arbitrary candidates needs an explicit boundary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from behavior_contract import evaluate, validate


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _approved_json(path, expected, label):
    # Parse precisely the bytes checked, not a second read of a mutable path.
    content = Path(path).read_bytes()
    if not expected or hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(label + "_HASH_MISMATCH")
    return json.loads(content)


def _registry(path, expected):
    data = _approved_json(path, expected, "ADAPTER_REGISTRY")
    if not isinstance(data, dict) or data.get("schema") != "kdd-behavior-adapters/v1":
        raise ValueError("ADAPTER_REGISTRY_INVALID")
    adapters = data.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise ValueError("ADAPTER_REGISTRY_EMPTY")
    names = set()
    for item in adapters:
        if not isinstance(item, dict) or set(item) != {"name", "tool", "source", "command"}:
            raise ValueError("ADAPTER_INVALID")
        if any(not isinstance(item[key], str) or not item[key] for key in ("source", "name", "tool")):
            raise ValueError("ADAPTER_INVALID")
        source = Path(item["source"])
        if not isinstance(item["name"], str) or item["name"] in names or source.is_absolute() or ".." in source.parts:
            raise ValueError("ADAPTER_INVALID")
        if not isinstance(item["command"], list) or not item["command"] or not all(isinstance(x, str) for x in item["command"]):
            raise ValueError("ADAPTER_INVALID")
        names.add(item["name"])
    return adapters


def _run(command, root, values):
    env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    completed = subprocess.run(command, cwd=root, input=json.dumps(values), text=True,
                               encoding="utf-8", errors="replace", capture_output=True,
                               timeout=30, env=env)
    if completed.returncode:
        raise ValueError("ADAPTER_EXIT_{}".format(completed.returncode))
    output = json.loads(completed.stdout)
    if not isinstance(output, list) or len(output) != len(values) or any(type(x) is not int for x in output):
        raise ValueError("ADAPTER_PROTOCOL")
    return output


def execute(root, contract_path, registry_path, *, contract_sha256=None, adapters_sha256=None):
    report = {"status": "ERROR", "guarantee": "bounded_exhaustive_execution", "universal_proof": False,
              "started_at": datetime.now(timezone.utc).isoformat(), "adapters": []}
    try:
        root, contract_path, registry_path = Path(root).resolve(), Path(contract_path).resolve(), Path(registry_path).resolve()
        contract = _approved_json(contract_path, contract_sha256, "CONTRACT")
        issues = validate(contract)
        if issues:
            raise ValueError(issues[0][0])
        adapters = _registry(registry_path, adapters_sha256)
        def check_integrity(source=None, source_hash=None):
            if _hash(contract_path) != contract_sha256 or _hash(registry_path) != adapters_sha256:
                raise ValueError("APPROVED_INPUT_CHANGED")
            if source is not None and _hash(source) != source_hash:
                raise ValueError("SOURCE_CHANGED")
        check_integrity()
        report.update({"contract_sha256": contract_sha256, "registry_sha256": adapters_sha256,
                       "domain": contract["domain"], "batch_size": contract["cases"]["batch_size"]})
        values = range(contract["domain"]["min"], contract["domain"]["max"] + 1)
        for adapter in adapters:
            entry = {"name": adapter["name"], "status": "ERROR", "source": adapter["source"], "cases_checked": 0, "counterexamples": []}
            report["adapters"].append(entry)
            source = (root / adapter["source"]).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                entry["error"] = "SOURCE_MISSING"
                continue
            tool = shutil.which(adapter["tool"])
            if not tool:
                entry["status"], entry["error"] = "UNSUPPORTED", "TOOL_MISSING"
                continue
            entry["source_sha256"] = _hash(source)
            command = [part.replace("{tool}", tool).replace("{source}", str(source)) for part in adapter["command"]]
            entry["command"] = command
            try:
                for start in range(0, len(values), report["batch_size"]):
                    check_integrity(source, entry["source_sha256"])
                    batch = list(values[start:start + report["batch_size"]])
                    output = _run(command, root, batch)
                    check_integrity(source, entry["source_sha256"])
                    for value, result in zip(batch, output):
                        if evaluate(contract["property"], value, result) is not True and len(entry["counterexamples"]) < 5:
                            entry["counterexamples"].append({"input": value, "result": result})
                    entry["cases_checked"] += len(batch)
                    if entry["counterexamples"]:
                        break
                entry["status"] = "PASS" if entry["cases_checked"] == len(values) and not entry["counterexamples"] else "FAIL"
            except (ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                entry["error"] = str(exc)
        report["status"] = "PASS" if report["adapters"] and all(x["status"] == "PASS" for x in report["adapters"]) else "FAIL"
    except (ValueError, OSError) as exc:
        report["error"] = str(exc)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--contract-sha256", required=True, help="Independently reviewed SHA-256 of the behavior contract")
    parser.add_argument("--adapters", required=True)
    parser.add_argument("--adapters-sha256", required=True, help="Reviewed SHA-256 of the trusted adapter registry")
    parser.add_argument("--evidence")
    args = parser.parse_args(argv)
    report = execute(args.root, args.contract, args.adapters,
                     contract_sha256=args.contract_sha256, adapters_sha256=args.adapters_sha256)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.evidence:
        Path(args.evidence).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
