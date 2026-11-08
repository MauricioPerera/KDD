#!/usr/bin/env python3
"""Interface for a risk-proportional review; implementation awaits baseline review."""
import argparse
import json
import sys


class ReviewError(ValueError):
    """The review inputs or Git objects cannot be validated."""


def inspect_change(repo_root, base_ref, candidate_ref):
    """Inspect exact Git identities and derive a risk floor."""
    raise ReviewError('REVIEW_PENDING: approved implementation not installed')


def verify_review(repo_root, base_ref, candidate_ref, review_json):
    """Verify an externally supplied review without granting approval."""
    raise ReviewError('REVIEW_PENDING: approved implementation not installed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--base-ref', required=True)
    parser.add_argument('--candidate-ref', required=True)
    parser.add_argument('--review')
    args = parser.parse_args(argv)
    try:
        if args.review:
            with open(args.review, encoding='utf-8') as stream:
                result = verify_review(args.repo_root, args.base_ref,
                                       args.candidate_ref, stream.read())
        else:
            result = inspect_change(args.repo_root, args.base_ref, args.candidate_ref)
    except (ReviewError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if not args.review or result['review_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
