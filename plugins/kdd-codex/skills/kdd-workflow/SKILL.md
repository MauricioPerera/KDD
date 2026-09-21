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
