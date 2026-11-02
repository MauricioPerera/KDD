"""Trusted JSON transport for Board oracle execution; stdout is not evidence."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_execution import execute_oracle


def main():
    metadata = json.loads(sys.argv[1])
    result = execute_oracle(metadata, sys.argv[2], float(sys.argv[3]))
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
