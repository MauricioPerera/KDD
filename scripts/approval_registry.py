"""Reviewed interface only; implementation waits for the oracle baseline."""
import sys


class ApprovalError(ValueError):
    """An external approval cannot be selected safely."""


def resolve(repo_root, candidate_ref, registry_json, *, explicit_baseline=None,
            explicit_quality=None, require_quality=False):
    raise ApprovalError('APPROVAL_NOT_IMPLEMENTED: reviewed baseline required')


def main(argv=None):
    print('FAIL: APPROVAL_NOT_IMPLEMENTED: reviewed baseline required', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
