"""CCDD v0.3 compatibility CLI; implementation follows reviewed contracts."""
import json
import sys


def main():
    print(json.dumps({'status': 'INVALID', 'findings': ['NOT_IMPLEMENTED']}))
    return 2


if __name__ == '__main__':
    sys.exit(main())
