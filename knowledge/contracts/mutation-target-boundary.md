---
type: 'Task Contract'
title: 'Destinos de mutacion confinados y contratos de rutas coherentes'
description: 'Rechazar targets absolutos o enlazados antes de escribir y conservar originales e indice.'
tags: ['mutation', 'security', 'integration']
task: mutation-target-boundary
intent: 'Cerrar la escritura del mutante fuera de su copia y validar rutas relativas.'
target: scripts/mutation_audit.py
language: python
signature: 'def audit_contract(contract_path, repo_root, timeout=120):'
test_command: 'python -m unittest tests/test_mutation_target_boundary.py'
budget:
  cyclomatic_max: 18
  nesting_max: 5
  lines_max: 220
  params_max: 5
tests: tests/test_mutation_target_boundary.py
tests_sha256: '4afb39ffca054503d1162775fc90880c761710124506dbd86e6b548d5c5683bb'
touch_only: ['scripts/mutation_audit.py', 'scripts/validate_contracts.py']
deps_allowed: ['stdlib', 'process_tree']
forbids: ['network', 'llm']
---
## Intent
Aplicar la [frontera de escritura](../audit-mutation-approval-ci.md).
## Interface
Conservar API y conteos. Target inseguro produce REJECT sin controles ni mutantes;
CLI rechazado devuelve no cero. El validador emite findings para target/tests inseguros.
## Invariants
Rechazar absolutos, drives, UNC, traversal y componentes enlazados/reparse antes
de copias/ejecucion; rechazar el target con varios hardlinks. Comprobar destino real. No alterar original, indice, refs o
canarios. Conservar targets relativos sanos, SKIP legitimos y controles existentes.
## Examples
- target absoluto dentro del proyecto: REJECT y bytes originales intactos.
- target relativo sano: controles verdes y detecciones verdaderas.
## Do / Don't
- DO usar archivos, enlaces, Git y procesos reales.
- DON'T resellar oraculos para ocultar escrituras o prometer sandbox.
## Tests
El oraculo usa contratos completos, canarios, hashes, indice y refs. Se ejecuta
tambien desde una copia sin Git; sus repos de prueba son propios.
## Constraints
PARAR y reportar si requiere un oraculo anterior, runtime o proteccion no revisado.
Los cambios de validate_contracts exigen revision final del bundle antes de publicar.
