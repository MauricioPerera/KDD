#!/usr/bin/env python3
"""Validate optional behavior/v1 JSON contracts without executing candidate code.

Usage: python scripts/validate_behavior.py [behavior_dir]
Missing directories and empty directories are optional and return success.
"""
import sys
from pathlib import Path
from behavior_contract import read_json, validate


def findings(directory):
    root = Path(directory)
    if not root.exists():
        return []
    result = []
    for path in sorted(root.rglob("*.behavior.json")):
        document, error = read_json(path)
        if error:
            result.append((path.as_posix(), "BHV_JSON", error))
        else:
            result.extend((path.as_posix(), rule, message) for rule, message in validate(document))
    return result


def main(argv):
    directory = argv[0] if argv else "behavior"
    result = findings(directory)
    if not Path(directory).exists():
        print("INFO: behavior directory absent; optional layer skipped")
    for path, rule, message in result:
        print("ERROR [{}] {}: {}".format(rule, path, message))
    print("Summary: {} error(s)".format(len(result)))
    return 1 if result else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
