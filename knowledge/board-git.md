---
type: 'Concept'
title: 'KDD Board con tareas Git'
description: 'Tareas Git y revisiones por SHA en Board.'
tags: ['kdd-board', 'git', 'tasks']
---

# KDD Board con Git

Ejecutar `./scripts/run_board.ps1` o `bash scripts/run_board.sh` con Node 24,
Python 3.11+ y Git. Abrir la URL autenticada. [Raiz](contracts/board-project-root.md)
y [onboarding](contracts/board-empty-onboarding.md). El [diario](git-tasks.md) lee `main`.

## Operar tareas

La [API del diario](contracts/board-git-journal.md) usa `KDD_PYTHON` (default `python`).
Consultar `GET /api/board/contracts` para el catalogo y `GET /api/tools` para los
esquemas WebMCP. Consultar `main` antes de reintentar una transicion.
[Detalle](contracts/board-task-snapshot.md), [interfaz](contracts/board-git-ui.md),
[errores HTTP y WebMCP](contracts/board-webmcp-errors.md),
[catalogo](contracts/board-contract-refresh.md) y [recuperacion](contracts/board-polling-recovery.md).

## Retomar una revision

Guardar `selection.json` en `.agents/logs/board-reviews/TASK-ID/` con SHA completos.

```json
{"current":{"base_commit":"<BASE>","candidate_commit":"<CANDIDATO>"},"previous":[]}
```

Guardar `<CANDIDATO>.json` con el v1 original. Pulsar **Consultar revision**
o leer `GET /api/tasks/ID/review-handoff`. Mover la seleccion anterior a
`previous` al cambiar de SHA.
[Relevo](contracts/board-review-handoff.md) y [aprobacion humana](baseline-risk-review.md).

## Vault y modo legacy

El vault `.kdd-board/vault.env` usa texto plano y exige exclusion Git persistente.
[Migracion](contracts/board-vault-isolation.md), [reinicio](contracts/board-secret-restart.md)
y [evidencia legacy](contracts/task-oracle-execution-proof.md).
