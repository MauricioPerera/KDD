---
type: 'Task Contract'
title: "Dependencias TypeScript con import equals"
description: "Aplicar deps_allowed al import externo por asignacion de TypeScript."
tags: ['audit', 'integration', 'quality']
task: typescript-import-equals-audit
intent: "Reconocer la dependencia externa en la clausula import_require_clause de TypeScript."
target: scripts/change_contract_multilang.py
signature: "Auditoria de imports Tree-sitter para TypeScript y TSX"
test_command: "python -m unittest tests.test_change_audit_p1"
test_runner: python-unittest
oracle_files: ["tests/test_change_audit_p1.py", "requirements-change-audit.txt"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_change_audit_p1.py"
tests_sha256: '25adf1208f3186aaf1474d3981fc6d6ec2ea83e25b1d82de1d01117f355b228a'
touch_only: ["scripts/change_contract_multilang.py"]
deps_allowed: ["git", "tree-sitter"]
forbids: ['llm']
---

## Intent
Aplicar deps_allowed al import externo por asignacion.

## Interface
La regla [multilenguaje](change-contract-languages.md) lee import_require_clause.

## Invariants
Conservar parser fijado, rutas relativas y alias internos.

## Examples
- Paquete existente sin permiso produce DEP_UNDECLARED.
- El paquete permitido y el alias interno pasan.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
CLI real con commits TypeScript y lista de permisos.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
