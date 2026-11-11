"""Add pinned KDD validation to an existing consumer with a reversible file plan."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

try:
    from .bootstrap_transaction import filesystem_transaction
except ImportError:
    from bootstrap_transaction import filesystem_transaction


ASSETS = Path(__file__).resolve().parents[1] / "tools" / "kdd-adoption"
MANAGED = (".github/workflows/kdd-validate.yml", ".kdd/validate.py", ".kdd/validator.lock")


class Rejected(ValueError):
    """The requested adoption does not fit the supported file plan."""


def git(root, *args):
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, timeout=30, check=False,
    )
    if result.returncode:
        raise Rejected("ADOPTION_ROOT: an existing Git repository with history is required")
    return result.stdout.decode("utf-8").strip()


def consumer_root(value):
    try:
        root = Path(value).resolve(strict=True)
    except OSError as error:
        raise Rejected("ADOPTION_ROOT: select an existing Git repository root") from error
    actual = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    if root != actual:
        raise Rejected("ADOPTION_ROOT: select the Git repository root")
    git(root, "rev-parse", "--verify", "HEAD^{commit}")
    return root


def contract_directory(root, value):
    relative = PurePosixPath(value)
    if (not value or value != value.strip() or "\\" in value or ":" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or relative.parts[:2] != ("knowledge", "contracts")):
        raise Rejected("ADOPTION_CONTRACTS: select an exact directory under knowledge/contracts")
    directory = local_directory(root, relative)
    files = sorted(path for path in directory.glob("*.md") if not path.name.startswith("TEMPLATE-"))
    if not files:
        raise Rejected("ADOPTION_CONTRACTS: at least one existing contract is required")
    sources = ["knowledge/index.md", *(path.relative_to(root).as_posix() for path in files)]
    with filesystem_transaction(root, sources):
        if not (root / "knowledge/index.md").is_file():
            raise Rejected("ADOPTION_CONTRACTS: prepare knowledge/index.md before adoption")
    return relative.as_posix()



def local_directory(root, relative):
    directory = root
    for part in relative.parts:
        directory = directory / part
        try:
            info = directory.lstat()
        except FileNotFoundError as error:
            raise Rejected("ADOPTION_CONTRACTS: the selected directory does not exist") from error
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise Rejected("ADOPTION_PATH: contract directory has a linked or invalid ancestor")
    return directory


def normalized(data):
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def payloads(contracts, pin):
    launcher = (ASSETS / "validate.py").read_text(encoding="utf-8")
    marker = 'CONTRACTS = Path("knowledge/contracts")'
    if launcher.count(marker) != 1:
        raise Rejected("ADOPTION_ASSET: the launcher template is invalid")
    launcher = launcher.replace(marker, "CONTRACTS = Path(" + json.dumps(contracts) + ")")
    return {
        MANAGED[0]: (ASSETS / "kdd-validate.yml").read_bytes(),
        MANAGED[1]: launcher.encode("utf-8"),
        MANAGED[2]: (pin + "\n").encode("ascii"),
    }


def file_plan(root, files):
    tracked = set(git(root, "ls-files", "-z", "--", *MANAGED).split("\0"))
    tracked.update(git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *MANAGED).split("\0"))
    plan = {"status": "planned", "create": [], "keep": []}
    with filesystem_transaction(root, files):
        for name, data in sorted(files.items()):
            plan[file_state(root, name, data, tracked)].append(name)
    return plan



def file_state(root, name, data, tracked):
    path = root / name
    if not path.exists():
        if name in tracked:
            raise Rejected("ADOPTION_CONFLICT: preserve the deleted managed path " + name)
        return "create"
    if normalized(path.read_bytes()) != normalized(data):
        raise Rejected("ADOPTION_CONFLICT: existing content differs at " + name)
    return "keep"


def apply(root, files, plan):
    with filesystem_transaction(root, files):
        for name in plan["create"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(files[name])
    plan["status"] = "applied" if plan["create"] else "unchanged"
    return plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--contracts-dir", required=True)
    parser.add_argument("--validator-commit", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", args.validator_commit):
            raise Rejected("ADOPTION_PIN: use a full lowercase 40-digit KDD commit SHA")
        root = consumer_root(args.repo_root)
        contracts = contract_directory(root, args.contracts_dir)
        files = payloads(contracts, args.validator_commit)
        plan = file_plan(root, files)
        result = apply(root, files, plan) if args.apply else plan
    except Rejected as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValueError as error:
        print("ADOPTION_PATH: " + str(error), file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as error:
        print("ADOPTION_WRITE: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
