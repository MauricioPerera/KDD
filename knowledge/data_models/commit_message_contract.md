---
type: 'Data Model'
title: 'Convención de formato de mensaje de commit'
description: 'La gramática Conventional Commits que scripts/validate_commit_message.py verifica, la tabla de severidad calibrada contra commitlint, y la frontera mecánico/juicio en git — incluida la referencia cruzada al patrón "verificar y mergear" que ya existe sin nombre.'
tags: ['git', 'commits', 'gate', 'example']
---

# Convención de mensaje de commit (dominio de ejemplo)

`scripts/validate_commit_message.py` mide lo MECÁNICO de un mensaje de commit — su
gramática, nunca si explica bien el *por qué* del cambio. Misma frontera que el dominio
editorial ([Contrato 23](../../docs/reports/CONTRACT-23-REPORT.md)) y el de UX
([Contrato 30](../../docs/reports/CONTRACT-30-REPORT.md)).

## La gramática (Conventional Commits v1.0.0)

```
tipo(scope)?!?: descripción

cuerpo opcional, separado por una línea en blanco
```

`examples/git/commit-convention.json` declara los tipos aceptados (`feat`, `fix`, `docs`,
`refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`), si el scope es obligatorio,
y el largo máximo del header — como DATO, no hardcodeado en el script.

## Severidad (calibrada contra `commitlint`, no inventada)

| Regla | Severidad | Por qué |
|---|---|---|
| `HEADER_MALFORMED` | ERROR | el header no tiene la estructura mínima parseable |
| `TYPE_UNKNOWN` | ERROR | el tipo no está en la lista declarada |
| `SCOPE_REQUIRED` | ERROR | la convención exige scope y no está |
| `BLANK_LINE_MISSING` | ERROR | regla real de Git mismo: el cuerpo se separa del header por una línea en blanco |
| `SUBJECT_TOO_LONG` | WARNING | `commitlint` lo trae como regla configurable, no hard error |
| `SUBJECT_TRAILING_PERIOD` | WARNING | regla real de `commitlint` (`subject-full-stop`), mismo nivel |

## Frontera declarada (fuera de este gate)

- **Si el commit es realmente un breaking change y lo declaró bien** (`!` o footer
  `BREAKING CHANGE:`): no se puede verificar desde el texto del mensaje solo — exigiría
  conocer el diff real. Fuera de alcance.
- **Plantillas de PR/issue reales en GitHub, o verificar PRs vía API**: exige red, fuera
  del nivel 1 por doctrina (mismo argumento del servidor MCP vivo en
  [Contrato 25](../../docs/reports/CONTRACT-25-REPORT.md)).
- **Si el mensaje explica bien el motivo, si el commit merece existir**: juicio humano.
- **"Verificar un PR y hacer o no merge"**: esto YA EXISTE como patrón sin nombre nuevo —
  CI verde en ambas patas antes de cerrar un contrato (cada contrato de esta sesión) y
  rama protegida + 2 checks obligatorios en `ccdd-gate`. Este contrato no lo reconstruye,
  solo deja la referencia cruzada explícita.

## Honestidad de alcance

Esta herramienta es OPT-IN — NO es paso de CI de este repo. El propio historial de KDD
(`C30: ...`, `release: vX.Y.Z ...`, `docs: ...`) no sigue Conventional Commits; es una
convención informal de esta sesión, no un estándar documentado. Forzar esta convención
retroactivamente sobre el historial real sería absurdo. `examples/git/commit-convention.json`
es un artefacto de EJEMPLO (removido por `init_project`), no la política de este repo.
