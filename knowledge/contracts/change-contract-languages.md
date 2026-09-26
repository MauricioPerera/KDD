---
type: 'Task Contract'
title: 'Adaptadores multilenguaje del auditor de cambios'
description: 'Analiza imports, manifiestos y funciones de JS/TS, Go y Rust con parsers fijados para auditar diffs de implementacion.'
tags: ['ccdd', 'diff', 'languages']
task: change-contract-languages
intent: 'Dar veredictos deterministas de dependencias y presupuesto para targets JS/TS, Go y Rust.'
target: scripts/change_contract_multilang.py
signature: 'def audit_source(target, before, after, policy, manifests) -> list:'
test_command: 'python -m unittest tests/test_validate_change_contract.py'
budget:
  cyclomatic_max: 18
  nesting_max: 5
  lines_max: 400
  params_max: 5
tests: 'tests/test_validate_change_contract.py'
tests_sha256: '632043378fd6e51585f2be9ecd7b8854d1597b82269c2715b03804283fd75a0f'
touch_only: ['scripts/change_contract_multilang.py']
deps_allowed: ['stdlib', 'tree_sitter', 'tree_sitter_javascript', 'tree_sitter_typescript', 'tree_sitter_go', 'tree_sitter_rust']
forbids: ['network', 'llm']
---

## Intent

Complementar el [auditor de cambios](./change-contract-audit.md) sin
declarar que un regex o un parser de Python entiende otros lenguajes. Los
parsers Tree-sitter se instalan con versiones fijas. Se leen solo blobs Git y
manifiestos; no se ejecuta codigo del candidato.

## Interface

`audit_source(target, before, after, policy, manifests)` devuelve findings
con `rule`, `path` y `msg`. `before` y `after` son bytes de los blobs del
target. `policy` contiene el `budget` y `deps_allowed` del contrato aprobado.
`manifests` contiene los textos base/candidato de `package.json`, `go.mod` o
`Cargo.toml` mas cercano al target.

## Invariants

- Las extensiones `.js`, `.jsx`, `.ts`, `.tsx`, `.go` y `.rs` tienen parser
  explicito. El AST con errores produce `CHECK_PARSE`.
- Imports externos nuevos y dependencias agregadas al manifiesto requieren
  `deps_allowed` del baseline. Imports relativos, Node `node:*`, Go stdlib y
  Rust `std`/`core`/`alloc`/`crate` no son dependencias externas.
- El manifiesto requerido debe existir y ser parseable. No se promete
  resolver dependencias transitivas ni imports construidos dinamicamente;
  construcciones dinamicas detectadas sin literal producen finding duro.
- Cada funcion del target se mide contra `cyclomatic_max`, `nesting_max`,
  `lines_max` y `params_max` declarados. Una macro Rust dentro de una funcion
  produce `BUDGET_UNSUPPORTED`, porque el AST deja opaco su cuerpo.
- El conteo de decisiones incluye switch/select y sus casos en Go, y
  while/for en Rust; esas ramas no pueden quedar fuera del presupuesto.
- Los formatos o construcciones no reconocidos fallan cerrado con un rule-id
  especifico. La salida es estable y no usa red.

## Examples

- JS con import `@acme/tool/sub`, `package.json` y `deps_allowed:
  ['@acme/tool']` -> PASS.
- Go con `github.com/acme/lib` en `go.mod` pero no permitido ->
  `DEP_UNDECLARED`.
- Rust con `println!` dentro de la funcion -> `BUDGET_UNSUPPORTED`.

## Do / Don't

- DO: distinguir parsing, dependencias y metricas en los findings.
- DON'T: tratar un AST con error o una macro opaca como PASS.

## Tests

El oraculo sellado `tests/test_validate_change_contract.py` usa repositorios
Git temporales para probar el adapter a traves del CLI del auditor.

## Constraints

- PARAR y reportar si un parser fijado no esta disponible en CI Linux o
  Windows.
- Fijar versiones en `requirements-change-audit.txt` y rechazar cambios
  al guard confiable sin revision independiente.
