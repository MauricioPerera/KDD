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
5. The optional hooks send no prompts, tool arguments, file contents, or secrets. They do not block, approve, or rewrite Codex operations.

When an operator has configured a relay, report lifecycle progress through its signed events. Otherwise continue normally without network delivery.
