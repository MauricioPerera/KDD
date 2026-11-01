"""Group contract CLI; interface reserved for the approved implementation."""
import json
import sys


def main():
    print(json.dumps({'ok': False, 'verdict': 'INVALID', 'stage': 'preflight',
                      'detail': 'group contracts not implemented'}))
    return 2


if __name__ == '__main__':
    sys.exit(main())
