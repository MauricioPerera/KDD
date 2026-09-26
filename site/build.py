"""Build the public KDD Pages bundle from a single tracked Git revision."""

from __future__ import annotations

import argparse
import json
import http.server
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path


PUBLIC_PREFIXES = (
    "knowledge/",
    "docs/reports/",
    ".agents/skills/",
    "examples/quality-approval/",
    "examples/modelar-verification/",
)
PUBLIC_FILES = {".agents/AGENTS.md"}
STATIC_FILES = (
    "index.html", "support.html", "assets/kdd-logo.svg",
    "llms-skills.json", "knowledge/index.html",
    "knowledge/architecture/index.html", "knowledge/contracts/index.html",
    "knowledge/data_models/index.html",
)
RUN_URL = re.compile(r"https://github\.com/MauricioPerera/KDD/actions/runs/[0-9]+\Z")


def tracked_public_files(repo: Path) -> list[Path]:
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached"], cwd=repo
    ).decode("utf-8").split("\0")
    return [Path(name) for name in paths if name and
            (name in PUBLIC_FILES or name.startswith(PUBLIC_PREFIXES))]


def prefix_manifest(manifest: dict) -> dict:
    for item in manifest["published"]:
        for key in ("url", "tool_url"):
            if key in item:
                item[key] = "/KDD/" + item[key].removeprefix("/KDD/").lstrip("/")
    memory = manifest.get("memory", {})
    if "snapshot_url" in memory:
        memory["snapshot_url"] = "/KDD/" + memory["snapshot_url"].removeprefix("/KDD/").lstrip("/")
    return manifest


def update_landing(html: str, reports: int, gates: int, tests: int, ci_url: str) -> str:
    values = {"report-count": reports, "gate-count": gates, "test-count": tests}
    for element_id, count in values.items():
        pattern = rf'(<span class="n" id="{element_id}">)[^<]*(</span>)'
        html, changed = re.subn(pattern, rf'\g<1>{count}\g<2>', html)
        if changed != 1:
            raise ValueError(f"Missing unique landing count: {element_id}")
    pattern = r'(<a id="ci-evidence-link" href=")[^"]*(")'
    html, changed = re.subn(pattern, rf'\g<1>{ci_url}\g<2>', html)
    if changed != 1:
        raise ValueError("Missing unique CI evidence link")
    return html


def run_publisher(repo: Path, output: Path, *args: str) -> None:
    cli = repo / "site/node_modules/@rckflr/llms-skills/bin/llms-skills.mjs"
    if not cli.is_file():
        raise FileNotFoundError("Run npm ci in site/ before building Pages")
    subprocess.run(["node", str(cli), *args], cwd=output, check=True)


def validate_under_prefix(repo: Path, output: Path) -> None:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output), **kwargs)

        def translate_path(self, path):
            if not path.startswith("/KDD/"):
                return str(output / "__invalid_prefix__")
            return super().translate_path(path.removeprefix("/KDD"))

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/KDD/llms.txt"
        run_publisher(repo, output, "validate", url, "--strict")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def build_pages(repo_root: str, output_dir: str, ci_run_url: str) -> dict:
    """Build a fresh Pages artifact and return its evidence counts."""
    repo = Path(repo_root).resolve()
    output = Path(output_dir).resolve()
    if not RUN_URL.fullmatch(ci_run_url):
        raise ValueError("CI run URL must belong to MauricioPerera/KDD")
    if output.exists():
        raise FileExistsError(output)
    if output == repo or repo in output.parents:
        raise ValueError("Output must be separate from source")
    source_files = tracked_public_files(repo)
    for rel in source_files:
        source = repo / rel
        if source.is_symlink() or not source.is_file() or repo not in source.resolve().parents:
            raise ValueError(f"Unsafe public source: {rel}")
    output.mkdir(parents=True)
    for rel in source_files:
        destination = output / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / rel, destination)
    for name in STATIC_FILES:
        source = repo / "site" / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Missing or unsafe static source: {name}")
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (output / ".nojekyll").write_text("", encoding="utf-8")

    sys.path.insert(0, str(repo))
    try:
        from scripts.mcp_gate_dispatch import LEVEL1_GATES
        gates = len(LEVEL1_GATES)
    finally:
        sys.path.pop(0)
    tests = int(subprocess.check_output(
        [sys.executable, "-c", "import unittest; print(unittest.defaultTestLoader.discover('tests', pattern='test_*.py').countTestCases())"],
        cwd=repo, text=True,
    ).strip())
    reports = len(list((output / "docs/reports").glob("CONTRACT-*-REPORT.md")))
    landing = output / "index.html"
    landing.write_text(update_landing(landing.read_text(encoding="utf-8"), reports, gates, tests, ci_run_url), encoding="utf-8")

    run_publisher(repo, output, "memory", "knowledge")
    manifest = output / "llms-skills.json"
    manifest.write_text(json.dumps(prefix_manifest(json.loads(manifest.read_text(encoding="utf-8"))), indent=2) + "\n", encoding="utf-8")
    run_publisher(repo, output, "publish")
    run_publisher(repo, output, "publish", "--check")
    validate_under_prefix(repo, output)
    return {"reports": reports, "gates": gates, "tests": tests, "ci_run_url": ci_run_url, "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--ci-run-url", required=True)
    arguments = parser.parse_args()
    print(json.dumps(build_pages(str(Path(__file__).resolve().parent.parent), arguments.output, arguments.ci_run_url)))
