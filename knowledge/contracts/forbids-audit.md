---
type: 'Task Contract'
title: 'Auditor de forbids: lo declarado vs lo realmente impedido'
description: 'Auditor ADVISORY que compara el forbids de cada task contract contra lo que esta efectivamente impedido. Hoy verifica unsafe en Rust (denegacion a nivel compilador); el resto de las capacidades se reportan como no verificables en vez de callar. NO es gate de CI ni entra en GATE_SPECS.'
tags: ['ccdd', 'forbids', 'rust', 'advisory', 'infra']

task: forbids-audit
intent: "Auditar si el forbids declarado en un contrato esta realmente impedido."
target: scripts/audit_forbids.py
signature: "def audit_contract(contract_path, repo_root) -> list"
test_command: "python -m unittest tests/test_audit_forbids.py"
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: "tests/test_audit_forbids.py"
tests_sha256: "22a71647ad72d1838b6a3518e02c14fdbfed2cb84a437a4773275520fddf369c"
touch_only: ['scripts/audit_forbids.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Auditor de forbids (forbids-audit)

## Intent
El campo `forbids` de un task contract enumera capacidades prohibidas al
implementador (`network`, `subprocess`, `llm`, `unsafe`), pero **nadie
verificaba su contenido**: `tc_lint` solo avisa si la lista esta vacia. Un
contrato podia declarar `forbids: ['unsafe']` sobre un proyecto Rust que
permite `unsafe` sin que ningun gate lo notara — la prohibicion era
decorativa. Hallazgo real: el propio proyecto de prueba de esta plantilla lo
declaraba sin imponerlo.

Este auditor cierra la mitad mecanica del hueco, y **hace explicita la otra
mitad**: si una capacidad no tiene verificador, lo dice
(`FORBID_UNVERIFIED`) en vez de callar. Un `forbids` que pasa limpio deja de
significar "todo verificado" y pasa a significar "esto verificado, esto
todavia no". Ver [validacion.md](../validacion.md).

## Interface
```
def audit_contract(contract_path, repo_root) -> list
```

## Invariants
- Solo LEE archivos: sin `subprocess`, sin red, sin LLM.
- `FORBID_UNVERIFIED` nunca cambia el exit code, ni con `--strict`: es una
  limitacion del auditor, no un incumplimiento del contrato.
- Sin `--strict` el exit code es SIEMPRE 0 (advisory, igual que `audit_seals`).
- Con `--strict`, exit 1 solo si hay reglas DURAS (`FORBID_UNSAFE_PRESENT`).
- Si el crate deniega `unsafe` a nivel compilador, no se reporta nada aunque
  el target lo use: rustc rechaza la compilacion, o sea que la prohibicion SI
  esta impuesta y el fallo de build es el enforcement.
- `unsafe_code` (el nombre del lint) nunca cuenta como uso de la keyword
  `unsafe`.
- Los findings salen ordenados por `(contract, rule, msg)`.

## Examples
- Contrato con `forbids: ['unsafe']`, `language: rust`, crate sin denegacion y
  target que NO usa `unsafe` -> `FORBID_UNSAFE_UNENFORCED` (WARNING).
- Igual pero el target USA `unsafe` -> `FORBID_UNSAFE_PRESENT` (ERROR duro).
- Igual con `unsafe_code = "deny"` en `[lints.rust]` del `Cargo.toml` -> sin
  findings.
- Contrato con `forbids: ['network']` -> `FORBID_UNVERIFIED` (INFO): no hay
  verificador para esa capacidad.

## Do / Don't
- DO: tratar la ausencia de verificador como informacion, no como aprobacion.
- DO: preferir la denegacion a nivel compilador (`unsafe_code = "deny"` o
  `#![forbid(unsafe_code)]`) sobre el scan del archivo: cubre el crate entero.
- DON'T: promoverlo a gate de Nivel 1 agregandolo a
  `mcp_gate_dispatch.GATE_SPECS` — eso hace crecer `LEVEL1_GATES` y rompe el
  oraculo congelado del preflight (19 gates exactos). Promoverlo es su propio
  contrato, con ambos oraculos re-sellados.
- DON'T: usar `tomllib` para leer el `Cargo.toml`: fijaria un piso de Python
  3.11 en una plantilla que se distribuye a terceros. El parser de secciones
  minimo alcanza para las claves que hacen falta.

## Tests
Los tests estan en `tests/test_audit_forbids.py` — oraculo congelado, sellado
por `tests_sha256`, con fixtures solo en tmpdir (no dependen de este repo).

## Constraints
- PARAR y reportar si verificar una capacidad exigiera ejecutar codigo,
  compilar o salir a la red: este auditor solo lee archivos.
- PARAR y reportar si el `intent` exigiera tocar algo fuera de
  `touch_only` (`scripts/audit_forbids.py`).
