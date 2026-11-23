---
type: 'Task Contract'
title: "Perimetro completo de renombres"
description: "Contar las dos rutas alteradas por un renombre al aplicar touch_only."
tags: ['audit', 'integration', 'quality']
task: change-audit-rename-endpoints
intent: "Aplicar el perimetro a origen y destino de un renombre entre commits."
target: scripts/validate_change_contract.py
signature: "def _changed_paths(root, base_ref, head_ref)"
test_command: "python -m unittest tests.test_change_audit_p1"
test_runner: python-unittest
oracle_files: ["tests/test_change_audit_p1.py", "requirements-change-audit.txt"]
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: "tests/test_change_audit_p1.py"
tests_sha256: '25adf1208f3186aaf1474d3981fc6d6ec2ea83e25b1d82de1d01117f355b228a'
touch_only: ["scripts/validate_change_contract.py"]
deps_allowed: ["git", "tree-sitter"]
forbids: ['llm']
---

## Intent
Aplicar el perimetro a origen y destino de un renombre entre commits. El alcance sigue [auditoria de cambios](change-contract-languages.md).

## Interface
validate_change_contract.py calcula todas las rutas alteradas del intervalo Git aunque diff.renames cambie. La CLI conserva los codigos y OUT_OF_PERIMETER.

## Invariants
Las adiciones que mantienen el archivo origen no agregan al perimetro rutas intactas. Conservar lectura de commits, listas delimitadas por NUL y la comprobacion de archivos de prueba protegidos.

## Examples
- Mover un archivo desde una ruta excluida a otra permitida devuelve OUT_OF_PERIMETER.
- Copiar al destino permitido conservando el origen pasa el mismo control.

## Do / Don't
- DO: reusar el punto de entrada y los controles existentes.
- DON'T: Evitar cambiar el analizador Git global o los perfiles de CI.

## Tests
El oraculo commitea una copia y un movimiento reales, confirma R100 en Git y exige el mismo veredicto del auditor con renombres activados o desactivados.

## Constraints
Aprobar el SHA del baseline antes de implementar. PARAR y reportar si se
requiere cambiar controles remotos, el runtime confiable u oraculos previos.
