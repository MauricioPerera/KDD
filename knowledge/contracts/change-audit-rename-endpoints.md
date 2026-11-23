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
Cotejar ambos extremos con el [perimetro](change-contract-languages.md).

## Interface
La CLI audita todas las rutas alteradas aunque diff.renames cambie.

## Invariants
Conservar NUL, codigos de salida y filtro de oraculos protegidos.

## Examples
- Mover desde afuera devuelve OUT_OF_PERIMETER.
- Copiar dejando el origen intacto pasa.

## Do / Don't
- DO: reusar los controles ya versionados.
- DON'T: alterar perfiles o plazos.

## Tests
Git real con R100, copia y los dos perfiles de deteccion.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si requiere
cambiar oraculos previos, runtime confiable o protecciones.
