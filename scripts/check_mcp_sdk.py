"""Proposed interface; implementation awaits human oracle approval."""
import sys


class McpSdkError(ValueError):
    """The configured MCP SDK profile cannot be verified."""


def validate_report(data, expected_ids, expected_version):
    raise McpSdkError('MCP_NOT_IMPLEMENTED: oracle review required')


def run_smoke(repo_root, *, report_path=None, expected_commit=None):
    raise McpSdkError('MCP_NOT_IMPLEMENTED: oracle review required')


def main(argv=None):
    print('FAIL: MCP_NOT_IMPLEMENTED: oracle review required', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
