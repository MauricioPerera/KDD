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
Reconocer la dependencia externa en la clausula import_require_clause de TypeScript. El alcance sigue [politica multilenguaje](change-contract-languages.md).

## Interface
El auditor detecta el especificador del nodo AST import foo igual a require de paquete y aplica la misma politica de import existente. Los alias a simbolos locales no se tratan como paquetes.

## Invariants
Conservar las versiones fijadas del parser, el diagnostico DEP_UNDECLARED y las reglas para rutas relativas, modulos internos y paquetes aprobados.

## Examples
- Un paquete no declarado en deps_allowed produce DEP_UNDECLARED aunque ya figure en package.json.
- Un paquete permitido y un alias al simbolo importado mantienen un veredicto favorable.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar heuristicas por texto o ampliar el alcance a semantica de Rust.

## Tests
Ejecutar la CLI contra commits reales de un proyecto TypeScript aislado con el parser fijado. Probar la asignacion externa prohibida, el control permitido y el alias interno.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
