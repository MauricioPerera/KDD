"""Add pinned KDD validation to an existing consumer with a reversible file plan."""

import argparse
from contextlib import chdir
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import stat
import subprocess
import sys
import tempfile

try:
    from .bootstrap_transaction import filesystem_transaction
except ImportError:
    from bootstrap_transaction import filesystem_transaction


ASSETS = Path(__file__).resolve().parents[1] / "tools" / "kdd-adoption"
MANAGED = (".github/workflows/kdd-validate.yml", ".kdd/validate.py", ".kdd/validator.lock")
LOCK = MANAGED[2]


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


def preparation_path(root, value, *, directory):
    if value is None:
        return None
    if (not value or value != value.strip() or "\\" in value or ":" in value
            or any(ord(char) < 32 for char in value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise Rejected("ADOPTION_PATH: use an exact relative preparation path")
    if directory:
        local_directory(root, PurePosixPath(value))
    else:
        with filesystem_transaction(root, (value,)):
            if not (root / value).is_file():
                raise Rejected("ADOPTION_PATH: missing wheel manifest " + value)
    return value


def payloads(contracts, pin, preparation):
    launcher = (ASSETS / "validate.py").read_text(encoding="utf-8")
    marker = 'CONTRACTS = Path("knowledge/contracts")'
    if launcher.count(marker) != 1:
        raise Rejected("ADOPTION_ASSET: the launcher template is invalid")
    launcher = launcher.replace(marker, "CONTRACTS = Path(" + json.dumps(contracts) + ")")
    for constant, value in preparation.items():
        if value is not None:
            marker = constant + " = None"
            if launcher.count(marker) != 1:
                raise Rejected("ADOPTION_ASSET: the preparation template is invalid")
            launcher = launcher.replace(marker, constant + " = " + json.dumps(value))
    return {
        MANAGED[0]: (ASSETS / "kdd-validate.yml").read_bytes(),
        MANAGED[1]: launcher.encode("utf-8"),
        LOCK: (pin + "\n").encode("ascii"),
    }


def file_plan(root, files, expected=None):
    tracked = set(git(root, "ls-files", "-z", "--", *MANAGED).split("\0"))
    tracked.update(git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD", "--", *MANAGED).split("\0"))
    plan = {"status": "planned", "create": [], "keep": []}
    if expected is not None:
        plan["update"] = []
    with filesystem_transaction(root, files):
        for name, data in sorted(files.items()):
            state = file_state(root, name, data, tracked, expected if name == LOCK else None)
            plan[state].append(name)
        if expected is not None and plan["create"]:
            raise Rejected("ADOPTION_CONFLICT: pin updates require a complete installation")
    return plan



def file_state(root, name, data, tracked, expected=None):
    path = root / name
    if not path.exists():
        if name in tracked:
            raise Rejected("ADOPTION_CONFLICT: preserve the deleted managed path " + name)
        return "create"
    existing = normalized(path.read_bytes())
    if expected is not None:
        if existing != (expected + "\n").encode("ascii"):
            raise Rejected("ADOPTION_CONFLICT: installed validator pin differs from the expected pin")
        return "keep" if existing == data else "update"
    if existing == normalized(data):
        return "keep"
    raise Rejected("ADOPTION_CONFLICT: existing content differs at " + name)


def replace_lock(path, data):
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, filename = tempfile.mkstemp(prefix=".validator.lock-", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply(root, files, plan, expected=None):
    with filesystem_transaction(root, files):
        for name in plan["create"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(files[name])
        if plan.get("update"):
            if file_state(root, LOCK, files[LOCK], {LOCK}, expected) != "update":
                raise Rejected("ADOPTION_CONFLICT: validator pin changed after planning")
            replace_lock(root / LOCK, files[LOCK])
    plan["status"] = "applied" if plan["create"] or plan.get("update") else "unchanged"
    return plan


def verify_validator_commit(pin):
    transport = runpy.run_path(str(ASSETS / "validate.py"))["fetch_validator"]
    try:
        with tempfile.TemporaryDirectory(prefix="kdd-pin-") as temporary:
            transport(Path(temporary), pin)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise Rejected(f"ADOPTION_PIN: cannot verify validator commit {pin}: {error}") from error


def install(args):
    try:
        root = Path(args.repo_root).resolve(strict=True)
    except OSError as error:
        raise Rejected("ADOPTION_ROOT: select an existing Git repository root") from error
    expected = args.expected_validator_commit
    if any(not re.fullmatch(r"[0-9a-f]{40}", pin)
           for pin in (args.validator_commit, expected) if pin is not None):
        raise Rejected("ADOPTION_PIN: use a full lowercase 40-digit KDD commit SHA")
    with tempfile.TemporaryDirectory(prefix="kdd-install-") as temporary:
        directory = Path(temporary).resolve()
        if directory.is_relative_to(root):
            raise Rejected("ADOPTION_PATH: installation temporary directory must be outside the consumer")
        with chdir(directory):
            consumer_root(root)
            contracts = contract_directory(root, args.contracts_dir)
            preparation = {
                "REQUIREMENTS": preparation_path(root, args.requirements_file, directory=False),
                "SOURCE_DIR": preparation_path(root, args.source_dir, directory=True),
            }
            files = payloads(contracts, args.validator_commit, preparation)
            plan = file_plan(root, files, expected)
            verify_validator_commit(args.validator_commit)
            if args.apply:
                apply(root, files, plan, expected)
    if args.requirements_file is not None or args.source_dir is not None:
        plan["preparation"] = {"requirements_file": args.requirements_file, "source_dir": args.source_dir}
    return plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--contracts-dir", required=True)
    parser.add_argument("--validator-commit", required=True)
    parser.add_argument("--expected-validator-commit")
    parser.add_argument("--requirements-file")
    parser.add_argument("--source-dir")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = install(args)
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
