"""Validate the consumer with the single KDD commit selected by its lock."""

import argparse
from contextlib import chdir
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://github.com/MauricioPerera/KDD.git"
CONTRACTS = Path("knowledge/contracts")
REQUIREMENTS = None
SOURCE_DIR = None
PIN = re.compile(r"[0-9a-f]{40}")
METHOD_EVIDENCE = re.compile(r"((?:[0-9a-f]{2})+):[0-9a-f]{64}")
MANAGED = (".github/workflows/kdd-validate.yml", ".kdd/validate.py", ".kdd/validator.lock")
POLICIES = ("quality/product.json", "quality.json")
REGULAR = {b"100644", b"100755"}
LOCKED_WHEEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.!+-]*"
                          r"(?:[ \t]+--hash=sha256:[0-9a-f]{64})+")


class Rejected(ValueError):
    """A precondition or a validation stage failed."""


def git(root, env, *args, binary=False):
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        env=env, capture_output=True, timeout=120, check=False,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise Rejected(f"Git {args[0]} failed ({result.returncode}): {detail}")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def git_environment():
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    paths = [entry for entry in os.get_exec_path(env)
             if Path(entry).is_absolute() and not Path(entry).resolve().is_relative_to(ROOT)]
    env.update(PATH=os.pathsep.join(paths), GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    return env


def blob_manifest(raw):
    manifest = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if kind != b"blob" or mode not in REGULAR:
            raise Rejected(f"Unsupported entry in the pinned tree: {name!r}")
        manifest[name.decode("utf-8")] = oid.decode("ascii")
    return manifest


def git_blob_hash(data):
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {len(data)}\0".encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def materialize(archive, manifest, destination):
    with tarfile.open(archive, "r:") as snapshot:
        for entry in snapshot:
            if entry.isdir():
                continue
            path = PurePosixPath(entry.name)
            if (not entry.isfile() or path.is_absolute()
                    or any(part == ".." or ":" in part or "\\" in part for part in path.parts)
                    or entry.name not in manifest):
                raise Rejected(f"Unexpected entry in the validator archive: {entry.name}")
            with snapshot.extractfile(entry) as source:
                data = source.read()
            if git_blob_hash(data) != manifest.pop(entry.name):
                raise Rejected(f"Validator blob differs from Git: {entry.name}")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
    if manifest:
        raise Rejected(f"Validator archive omits Git blob: {next(iter(manifest))}")


def fetch_validator(directory, pin):
    repository = directory / "git"
    repository.mkdir()
    env = git_environment()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    git(repository, env, "init", "--bare", "--template=")
    git(repository, env, "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules", ORIGIN, pin)
    actual = git(repository, env, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
    if actual != pin or git(repository, env, "cat-file", "-t", pin) != "commit":
        raise Rejected(f"Fetched validator {actual} does not match commit {pin}")
    return repository, env


def prepare_validator(directory, pin):
    repository, env = fetch_validator(directory, pin)
    manifest = blob_manifest(git(repository, env, "ls-tree", "-rz", "--full-tree", pin, binary=True))
    archive = directory / "validator.tar"
    git(repository, env, "archive", "--format=tar", f"--output={archive}", pin)
    validator = directory / "validator"
    materialize(archive, manifest, validator)
    return pin, validator


def checked_run(command, label, *, env, cwd=None):
    result = subprocess.run(
        command, env=env, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode:
        raise Rejected(f"{label} exited {result.returncode}")
    return result.stdout


def python_environment(python):
    env = git_environment()
    env["PATH"] = str(Path(python).parent) + os.pathsep + env["PATH"]
    return env


def run_gate(validator, name, *arguments, python=sys.executable):
    script = validator / "scripts" / name
    return checked_run([python, "-E", "-s", "-S", "-B", "-X", "utf8", str(script), *arguments],
                       name, env=python_environment(python))


def local_path(name, *, directory=False):
    value = str(name)
    if (not value or "\\" in value or ":" in value or any(ord(char) < 32 for char in value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise Rejected(f"Expected an exact internal path: {name}")
    path = ROOT
    parts = value.split("/")
    for index, part in enumerate(parts):
        path /= part
        info = path.lstat()
        expected = stat.S_ISDIR if directory or index + 1 < len(parts) else stat.S_ISREG
        if not expected(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Rejected(f"Expected a regular local path: {name}")
    return path


def selected_contracts():
    directory = local_path(CONTRACTS.as_posix(), directory=True)
    files = sorted(path for path in directory.glob("*.md") if not path.name.startswith("TEMPLATE-"))
    if not files:
        raise Rejected("The selected directory has no executable contracts")
    for path in files:
        local_path(path.relative_to(ROOT).as_posix())
    return files


def consumer_git(*args, binary=False):
    return git(ROOT, git_environment(), "--literal-pathspecs", *args, binary=binary)


def tree_entries(reference, *paths):
    entries = {}
    for row in consumer_git("ls-tree", "-z", reference, "--", *paths, binary=True).split(b"\0"):
        if row:
            metadata, path = row.split(b"\t", 1)
            mode, _, oid = metadata.split()
            entries[path.decode("utf-8")] = (mode, oid)
    return entries


def index_entries(paths):
    entries = {}
    for row in consumer_git("ls-files", "--stage", "-z", "--", *paths, binary=True).split(b"\0"):
        if row:
            metadata, path = row.split(b"\t", 1)
            mode, oid, stage = metadata.split()
            if stage != b"0":
                raise Rejected(f"Unmerged approved path: {path.decode('utf-8')}")
            entries[path.decode("utf-8")] = (mode, oid)
    return entries


def check_approved_paths(reference, paths):
    approved = tree_entries(reference, *paths)
    committed = tree_entries("HEAD", *paths)
    index = index_entries(paths)
    contents = {}
    for path in paths:
        entry = approved.get(path)
        if not entry or entry[0] not in REGULAR or entry != committed.get(path) or entry != index.get(path):
            raise Rejected(f"{path} must match its regular file in the approved reference")
        raw = consumer_git("cat-file", "blob", entry[1].decode("ascii"), binary=True)
        if local_path(path).read_bytes().replace(b"\r\n", b"\n") != raw.replace(b"\r\n", b"\n"):
            raise Rejected(f"{path} differs from the approved reference in the worktree")
        contents[path] = raw
    return contents


def approved_commit(reference, setting):
    if not PIN.fullmatch(reference):
        raise Rejected(f"{setting} must be a full approved consumer commit SHA")
    if consumer_git("rev-parse", "--verify", reference + "^{commit}") != reference:
        raise Rejected(f"{setting} must identify the exact approved commit")
    return reference


def quality_check(validator, *, adoption=None, python=sys.executable):
    reference = os.environ.get("KDD_QUALITY_APPROVED_REF", "")
    if not reference:
        local = any(os.path.lexists(ROOT / name) for name in POLICIES)
        if local or tree_entries("HEAD", *POLICIES) or (adoption and tree_entries(adoption, *POLICIES)):
            raise Rejected("KDD_QUALITY_APPROVED_REF must be a full approved consumer commit SHA")
        return None
    approved_commit(reference, "KDD_QUALITY_APPROVED_REF")
    policies = tree_entries(reference, *POLICIES)
    if len(policies) != 1:
        raise Rejected("Approved quality policy is absent or ambiguous")
    policy = next(iter(policies))
    check_approved_paths(reference, (policy,))
    run_gate(validator, "verify_quality.py", "--repo-root", str(ROOT), "--policy", policy,
             "--approved-ref", reference, python=python)
    return reference


def adoption_paths():
    return (*MANAGED, REQUIREMENTS) if REQUIREMENTS is not None else MANAGED


def validator_pin(reference):
    lock = ".kdd/validator.lock"
    if reference:
        approved_commit(reference, "KDD_ADOPTION_APPROVED_REF")
        try:
            consumer_git("merge-base", "--is-ancestor", reference, "HEAD")
        except Rejected as error:
            raise Rejected("The approved adoption commit must be an ancestor of the candidate") from error
        raw = check_approved_paths(reference, adoption_paths())[lock]
    else:
        raw = local_path(lock).read_bytes()
    pin = raw.decode("ascii").replace("\r\n", "\n").removesuffix("\n")
    if not PIN.fullmatch(pin):
        raise Rejected("validator.lock must contain one lowercase 40-digit commit SHA")
    return pin


# Reuse the pinned parser and inventory validation in a process started outside
# the checkout. It can read candidate files without importing consumer Python.
CHECK_CONTRACTS = r"""
from pathlib import Path
import sys

scripts, root, reference, *contracts = sys.argv[1:]
sys.path.insert(0, scripts)
from oracle_inventory import inventory_paths
from validate_contracts import parse_frontmatter

if reference:
    from validate_baseline import validate_baseline

for name in contracts:
    if reference:
        findings = validate_baseline(name, reference, root)
        if findings:
            raise SystemExit("\n".join(findings))
    metadata, _ = parse_frontmatter((Path(root) / name).read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("test_runner") != "python-unittest":
        raise SystemExit(f"{name}: expected test_runner python-unittest before executing an oracle")
    inventory_paths(metadata, required=True)
"""


def check_contracts(validator, contracts, reference):
    if reference:
        names = tree_entries(f"{reference}:{CONTRACTS.as_posix()}")
        expected = {name for name in names if name.endswith(".md") and not name.startswith("TEMPLATE-")}
        if expected != {Path(path).name for path in contracts} or any(
                names[name][0] not in REGULAR for name in expected):
            raise Rejected("Selected contracts differ from the approved reference")
    checked_run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", CHECK_CONTRACTS,
                 str(validator / "scripts"), str(ROOT), reference, *contracts],
                "Contract approval", env=python_environment(sys.executable))


def pip_requirements(path):
    # Write a canonical manifest outside the checkout. Pip never gets a chance
    # to interpret includes, URLs, options or different comment syntax.
    lines, options = [], []
    text = path.read_text(encoding="utf-8").replace("\\\n", "")
    for raw in text.splitlines():
        line = raw.partition("#")[0].strip()
        if not line:
            continue
        if line == "--no-index":
            options.append(line)
        elif line.startswith("--find-links "):
            value = line.removeprefix("--find-links ").strip().removeprefix("./")
            options.extend(("--find-links", local_path(value, directory=True).as_uri()))
        elif LOCKED_WHEEL.fullmatch(line):
            lines.append(line)
        else:
            raise Rejected(f"Unsupported locked wheel requirement: {line}")
    if not lines:
        raise Rejected("The wheel manifest must pin at least one dependency")
    return "\n".join(lines) + "\n", options


def source_directory():
    source = local_path(SOURCE_DIR, directory=True)
    for child in source.iterdir():
        if child.name.partition(".")[0].casefold() in {"sitecustomize", "usercustomize"}:
            raise Rejected(f"Unsupported Python startup module in source directory: {child.name}")
    return source


def prepare_python(directory):
    if REQUIREMENTS is None and SOURCE_DIR is None:
        return sys.executable
    source = source_directory() if SOURCE_DIR is not None else None
    locked = pip_requirements(local_path(REQUIREMENTS)) if REQUIREMENTS is not None else None
    environment = directory / "venv"
    venv.EnvBuilder(with_pip=locked is not None).create(environment)
    if os.name == "nt":
        python = str(environment / "Scripts" / "python.exe")
        packages = environment / "Lib" / "site-packages"
    else:
        python = str(environment / "bin" / "python")
        packages = environment / "lib" / "python3.11" / "site-packages"
    if locked is not None:
        requirements, options = locked
        manifest = directory / "requirements.txt"
        manifest.write_text(requirements, encoding="utf-8")
        env = {key: value for key, value in python_environment(python).items()
               if not key.upper().startswith("PIP_")}
        env["PIP_CONFIG_FILE"] = os.devnull
        checked_run([python, "-I", "-B", "-m", "pip", "--disable-pip-version-check", "--no-cache-dir",
                     "install", "--no-input", "--require-hashes", "--only-binary=:all:", "--no-deps",
                     *options, "-r", str(manifest)], "Locked wheel installation", env=env)
    if source is not None:
        # The generated line is ASCII even for a Unicode checkout path and
        # appends a path without importing anything from the checkout.
        with (packages / "kdd-source.pth").open("x", encoding="ascii") as stream:
            stream.write(f"import sys; sys.path.append({ascii(str(source))})\n")
    return python


def oracle_pass(validator, contracts, python):
    output = run_gate(validator, "validate_test_commands.py", str(ROOT / CONTRACTS), str(ROOT),
                      python=python)
    results = re.findall(r"^  oracle_execution: runner=(\S+) executed_tests=(\d+)$",
                         output, re.MULTILINE)
    if len(results) != len(contracts) or any(runner != "python-unittest" or int(count) < 1
                                            for runner, count in results):
        raise Rejected("Expected executed python-unittest evidence for every selected contract")
    return sum(int(count) for _, count in results)


def unique_receipt_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("Repeated key in oracle receipt")
    return value


def receipt_contracts(path, contracts):
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_receipt_object)
    except (OSError, ValueError) as error:
        raise Rejected("Missing or invalid oracle receipt; use a reviewed validator pin with receipt support") from error
    if (not isinstance(receipt, dict) or set(receipt) != {"schema_version", "contracts"}
            or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or not isinstance(receipt["contracts"], list)):
        raise Rejected("Invalid oracle receipt schema")
    expected = set(contracts)
    inventory = {}
    for item in receipt["contracts"]:
        if not isinstance(item, dict) or set(item) != {"path", "ids"}:
            raise Rejected("Invalid contract entry in oracle receipt")
        name, ids = item["path"], item["ids"]
        if not isinstance(name, str) or name not in expected or name in inventory:
            raise Rejected("Unexpected or repeated contract in oracle receipt")
        if (not isinstance(ids, list) or not ids
                or any(not isinstance(identity, str) or not identity.strip() for identity in ids)
                or ids != sorted(set(ids))):
            raise Rejected("Invalid case IDs in oracle receipt: " + name)
        inventory[name] = ids
    if inventory.keys() != expected:
        raise Rejected("Oracle receipt does not cover the selected contracts")
    return [{"path": name, "ids": inventory[name]} for name in sorted(inventory)]


def oracle_case_label(identity):
    evidence = METHOD_EVIDENCE.fullmatch(identity)
    if evidence:
        try:
            label = bytes.fromhex(evidence[1]).decode("utf-8")
        except UnicodeError:
            label = ""
        if label.strip():
            return label
    raise Rejected("Invalid case IDs in oracle receipt: missing bound-method fingerprint; "
                   "use a reviewed validator pin with receipt support")


def public_oracle_inventory(inventory):
    result = []
    for item in inventory:
        labels = [oracle_case_label(identity) for identity in item["ids"]]
        if len(labels) != len(set(labels)):
            raise Rejected("Duplicate oracle case IDs in " + item["path"])
        result.append({"path": item["path"], "ids": sorted(labels)})
    return result


def approved_oracle_passes(validator, contracts, python, reference, directory):
    inventories = []
    for number in (1, 2):
        receipt = directory / f"oracle-pass-{number}.json"
        run_gate(validator, "validate_test_commands.py", str(ROOT / CONTRACTS), str(ROOT),
                 "--oracle-receipt", str(receipt), python=python)
        check_approved_paths(reference, adoption_paths())
        current = [path.relative_to(ROOT).as_posix() for path in selected_contracts()]
        if current != contracts:
            raise Rejected("Selected contracts changed during oracle execution")
        check_contracts(validator, contracts, reference)
        inventory = receipt_contracts(receipt, contracts)
        public = public_oracle_inventory(inventory)
        inventories.append(inventory)
    if inventories[0] != inventories[1]:
        raise Rejected("Managed oracle passes executed different case IDs per contract")
    return public


def check_consumer():
    if sys.version_info[:2] != (3, 11):
        raise Rejected("The pilot requires Python 3.11")
    if Path(consumer_git("rev-parse", "--show-toplevel")).resolve() != ROOT:
        raise Rejected("The launcher is outside the consumer Git root")


def validate_checkout(record, directory, reference):
    record["stage"] = "consumer"
    check_consumer()
    record["consumer_sha"] = consumer_git("rev-parse", "--verify", "HEAD")
    record["dirty"] = bool(consumer_git("status", "--porcelain"))
    record["stage"] = "pin"
    pin = validator_pin(reference)
    record["requested_kdd_sha"] = pin
    record["stage"] = "resolve"
    actual, validator = prepare_validator(directory, pin)
    record["verified_kdd_sha"] = actual
    record["stage"] = "contract"
    files = selected_contracts()
    contracts = [path.relative_to(ROOT).as_posix() for path in files]
    record["contracts"] = [
        {"path": relative, "sha256": hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()}
        for relative, path in zip(contracts, files)
    ]
    check_contracts(validator, contracts, reference)
    run_gate(validator, "validate_contracts.py", "--repo-root", str(ROOT), str(ROOT / CONTRACTS))
    record["stage"] = "okf"
    run_gate(validator, "validate_okf.py", str(ROOT / "knowledge"))
    record["stage"] = "prepare"
    python = prepare_python(directory)
    if reference:
        record["adoption_approved_ref"] = reference
        check_approved_paths(reference, adoption_paths())
        if python != sys.executable:
            check_contracts(validator, contracts, reference)
    record["stage"] = "quality"
    record["quality_approved_ref"] = quality_check(validator, adoption=reference, python=python)
    record["stage"] = "oracle"
    if reference:
        inventory = approved_oracle_passes(validator, contracts, python, reference, directory)
        count = sum(len(item["ids"]) for item in inventory)
        record.update(oracle_inventory=inventory, oracle_passes=[count, count], executed_tests=count)
    else:
        count = oracle_pass(validator, contracts, python)
        record.update(oracle_passes=[count], executed_tests=count)


def validate(record):
    reference = record.get("requested_adoption_ref", "")
    with tempfile.TemporaryDirectory(prefix="kdd-pilot-") as temporary:
        directory = Path(temporary).resolve()
        if directory.is_relative_to(ROOT):
            raise Rejected("Validator temporary directory must be outside the consumer checkout")
        with chdir(directory):
            validate_checkout(record, directory, reference)


def review_from_pin(args, directory):
    check_consumer()
    if not args.approved_ref:
        raise Rejected("--approved-ref must identify a full approved consumer commit")
    pin = validator_pin(args.approved_ref)
    actual, validator = prepare_validator(directory, pin)
    script = validator / "scripts/baseline_review.py"
    if not script.is_file():
        raise Rejected("The pin lacks baseline_review.py; upgrade to a reviewed validator pin with review support")
    command = [sys.executable, "-I", "-B", "-X", "utf8", str(script),
               "--repo-root", str(ROOT), "--base-ref", args.base_ref, "--candidate-ref", args.candidate_ref]
    if args.review:
        command.extend(("--review", str(args.review)))
    if args.small_change:
        command.append("--small-change")
    if args.editorial_only:
        command.append("--editorial-only")
    completed = subprocess.run(command, env=python_environment(sys.executable), capture_output=True,
                               encoding="utf-8", timeout=180, check=False)
    if completed.returncode not in (0, 1):
        raise Rejected(completed.stderr.strip() or "The pinned reviewer did not return a verdict")
    result = json.loads(completed.stdout)
    if not isinstance(result, dict) or type(result.get("review_ready")) is not bool:
        raise Rejected("The pinned reviewer returned an invalid verdict")
    result["verified_kdd_sha"] = actual
    print(json.dumps(result, sort_keys=True))
    return completed.returncode


def review_main(argv):
    global ROOT
    parser = argparse.ArgumentParser(description="Inspect a change with the approved KDD pin")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--approved-ref", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--small-change", action="store_true")
    mode.add_argument("--review", type=Path)
    parser.add_argument("--editorial-only", action="store_true")
    args = parser.parse_args(argv)
    if args.editorial_only and not args.small_change:
        parser.error("--editorial-only requires --small-change")
    ROOT = args.repo_root.resolve()
    try:
        if args.review:
            args.review = args.review.resolve()
        with tempfile.TemporaryDirectory(prefix="kdd-review-") as temporary:
            directory = Path(temporary).resolve()
            if directory.is_relative_to(ROOT):
                raise Rejected("Reviewer temporary directory must be outside the consumer checkout")
            with chdir(directory):
                return review_from_pin(args, directory)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(str(error), file=sys.stderr)
        return 2


def main():
    global ROOT
    if sys.argv[1:2] == ["review"]:
        return review_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--approved-ref", default=os.environ.get("KDD_ADOPTION_APPROVED_REF", ""))
    args = parser.parse_args()
    ROOT = args.repo_root.resolve()
    record = {"contracts_dir": CONTRACTS.as_posix(), "python": sys.version.split()[0]}
    if args.approved_ref:
        record["requested_adoption_ref"] = args.approved_ref
    try:
        validate(record)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError, tarfile.TarError) as error:
        record.update(result="fail", error=str(error))
    else:
        record.update(stage="complete", result="pass")
    print("KDD_PILOT " + json.dumps(record, sort_keys=True), flush=True)
    return int(record["result"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
