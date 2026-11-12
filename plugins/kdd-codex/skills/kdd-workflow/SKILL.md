---
name: kdd-workflow
description: Use KDD contracts, deterministic validation, and evidence before changing a KDD project.
---

# KDD workflow for Codex

Use this skill for KDD repositories and task contracts.

1. Read the repository's `AGENTS.md`, the relevant `knowledge/contracts/` entry, and linked knowledge nodes.
2. Before implementation, run the deterministic contract validator and create or update a sealed regression oracle where the task requires one.
3. Keep state changes evidence-led: a task is not complete merely because an agent says so. Run the declared `test_command` and preserve its actual result.
4. Do not place credentials in task descriptions, comments, reports, webhook payloads, or prompts. Blind-vault metadata only proves presence, never confidentiality from executed code.
5. This public package is skill-only: it does not install hooks, start services, send data, or connect to external systems.

Use the repository's own approved tools only when they are already available in
the user's environment. Do not configure a relay or lifecycle delivery from
this package.

## Adopt validation in an existing Python repository

When a reviewed KDD checkout containing the adoption CLI is available, prepare the
consumer's OKF index and approved contracts first. Use Python 3.11 and Git.

Run the CLI from that KDD checkout with an explicit consumer root, contract
directory and full reviewed KDD commit SHA. Start with the read-only plan.

```text
python scripts/adopt_project.py --repo-root CONSUMER --contracts-dir knowledge/contracts --validator-commit KDD_COMMIT_SHA --plan
```

After the user accepts those three file additions, use the same command with
`--apply`. For an existing installation, use its current lock and the reviewed
new SHA in the installer's update plan. Review legacy launcher and workflow
changes separately before changing the pin.

For a project with an approved adoption commit, run the same consumer entry point
as the terminal and its GitHub Actions workflow. Use Python 3.11 from the
consumer root and supply the reviewed quality reference through the environment
when its policy requires one.

```text
python .kdd/validate.py --approved-ref CONSUMER_SHA
```

Compare the full `verified_kdd_sha` in `KDD_PILOT` with `.kdd/validator.lock`.
Check both `oracle_passes` and the exit code before reporting success. For a
project using the historical profile, report the validation it actually ran.
