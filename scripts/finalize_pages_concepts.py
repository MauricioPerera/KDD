"""Scope and verify the generated concept tool before delivering a Pages bundle."""
import argparse
import json
from pathlib import Path
import re
import runpy


def scope_generated_concept(output: Path) -> None:
    """Make the pinned publisher's generated tool usable under the Pages URL."""
    tool = output / "skills/get_concept/tool.js"
    if tool.is_symlink() or not tool.resolve().is_relative_to(output.resolve()):
        raise ValueError("Unsafe generated concept tool")
    source = tool.read_text(encoding="utf-8")
    mapping = re.search(r"^var CONCEPTS = (.+);$", source, re.MULTILINE)
    result = '    return { id: args.id, markdown: r.body };'
    if mapping is None or source.count(result) != 1:
        raise ValueError("Unexpected get_concept from the pinned Pages publisher")
    concepts = json.loads(mapping[1])
    if not isinstance(concepts, dict) or any(
        not isinstance(url, str) or not url.startswith(("/knowledge/", "/KDD/knowledge/"))
        for url in concepts.values()
    ):
        raise ValueError("Unexpected get_concept URL outside the knowledge bundle")
    scoped = {key: "/KDD" + url.removeprefix("/KDD") for key, url in concepts.items()}
    source = source[:mapping.start(1)] + json.dumps(scoped, ensure_ascii=True) + source[mapping.end(1):]
    guard = '    if (r.truncated) throw new Error("Concept document truncated by publisher host");'
    if guard not in source:
        source = source.replace(result, guard + "\n" + result)
    tool.write_text(source, encoding="utf-8", newline="\n")


def load_pages_builder(repo: Path) -> dict:
    return runpy.run_path(str(repo / "site/build.py"))


def finalize_pages_concepts(repo: Path, output: Path) -> None:
    repo = repo.resolve(strict=True)
    output = output.resolve(strict=True)
    if not output.is_dir() or output.is_relative_to(repo):
        raise ValueError("Pages output must be a directory outside the repository")
    builder = load_pages_builder(repo)
    scope_generated_concept(output)
    builder["run_publisher"](repo, output, "publish")
    builder["run_publisher"](repo, output, "publish", "--check")
    builder["validate_under_prefix"](repo, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    cli = parser.parse_args()
    finalize_pages_concepts(Path(__file__).resolve().parents[1], cli.output)


if __name__ == "__main__":
    main()
