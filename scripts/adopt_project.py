"""Entry point for the proposed KDD adoption command."""

import sys


def main(argv=None):
    """Report the pre-implementation state."""
    print("ADOPTION_NOT_IMPLEMENTED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
