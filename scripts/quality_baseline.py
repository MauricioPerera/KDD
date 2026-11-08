#!/usr/bin/env python3
"""Create a deterministic, read-only manifest for an approved quality baseline."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from verify_quality import Rejected, approved_commit, safe_path, unique_object, validate_policy


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            timeout=30, check=False)
    if result.returncode:
        raise Rejected("Git operation failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _sha256(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def build_baseline(repo_root, policy_path, approved_ref):
    root = Path(repo_root).resolve(strict=True)
    safe_path(root, policy_path)
    commit = approved_commit(root, approved_ref)
    raw_policy = _git(root, "show", commit + ":" + policy_path)
    policy = validate_policy(root, json.loads(raw_policy, object_pairs_hook=unique_object))
    protected = {}
    for name in policy["protected"]:
        safe_path(root, name)
        content = _git(root, "show", commit + ":" + name)
        protected[name] = {"sha256": _sha256(content), "bytes": len(content)}
    return {"approved_ref": commit, "policy": policy_path,
            "policy_sha256": _sha256(raw_policy), "protected": protected}


def _prepare_review(args):
    from baseline_review import ReviewError, verify_review
    try:
        with open(args.review, encoding='utf-8') as stream:
            result = verify_review(args.repo_root, args.base_ref, args.candidate_ref, stream.read(262145))
    except (ReviewError, OSError, UnicodeError) as error:
        print('REJECT review: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['review_ready'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy")
    parser.add_argument("--approved-ref")
    parser.add_argument('--base-ref')
    parser.add_argument('--candidate-ref')
    parser.add_argument('--review')
    args = parser.parse_args(argv)
    review_flags = (args.base_ref, args.candidate_ref, args.review)
    if any(value is not None for value in review_flags):
        if not all(review_flags) or args.policy is not None or args.approved_ref is not None:
            parser.error('review mode requires base-ref, candidate-ref and review, without policy or approved-ref')
        return _prepare_review(args)
    if args.policy is None or args.approved_ref is None:
        parser.error('approved mode requires policy and approved-ref')
    try:
        result = build_baseline(args.repo_root, args.policy, args.approved_ref)
    except (Rejected, OSError, subprocess.SubprocessError) as error:
        print("REJECT baseline: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
