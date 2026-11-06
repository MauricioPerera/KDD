---
type: 'Task Contract'
title: 'Reducir complejidad del validador OKF'
description: 'Cumplir los presupuestos del gate OKF conservando findings y CLI.'
tags: ['okf', 'quality', 'budget', 'integration']
task: validate-okf-complexity
intent: 'Eliminar excesos del gate OKF sin alterar su validacion determinista.'
target: scripts/validate_okf.py
signature: 'def validate_okf(knowledge_dir: str) -> list:'
test_command: 'python -m unittest tests.test_validate_okf_complexity'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_validate_okf_complexity.py
tests_sha256: '2e601604e2194a072d3da802912d09e3a5c2d1e6315a54f2a2ba3857ced19bfd'
touch_only: ['scripts/validate_okf.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

## Intent
Eliminar los cuatro hallazgos del [validador OKF](validate-okf.md), que aplica
la [especificacion](../OKF-SPEC.md) a la base de conocimiento.

## Interface
Conservar las firmas y resultados de `validate_okf` y `parse_frontmatter`, la
CLI, sus codigos de salida, diagnosticos y orden determinista. Los helpers
privados pueden reorganizarse dentro del mismo archivo.

## Invariants
- Aplicar a todas las funciones el presupuesto vigente: complejidad ciclomatica
  maxima 10 y anidamiento maximo 4, incluidos helpers nuevos. No cambiar el
  medidor, excluir funciones, elevar limites ni trasladar logica a otro archivo.
- Conservar el dialecto de frontmatter, tipos, tags y diagnosticos completos;
  enlaces internos, externos y codigo; e indexacion directa por archivo o
  hijos directos de carpeta. No introducir cache ni modificar archivos leidos.
- Conservar oraculos previos, dependencias y capacidades del target. Mantener
  Ubuntu, Windows, el inventario existente y las dos pasadas de la suite.
- No introducir ni agravar hallazgos en el diagnostico global de presupuestos.

## Examples
- Una base conforme produce un reporte identico en dos ejecuciones CLI.
- Un nodo anidado no alcanzable desde el indice produce `ORPHAN`, aunque otro
  nodo alcanzable lo enlace; al enlazarlo desde el indice deja de ser huerfano.
- Un enlace roto y otro a `.txt` generan dos findings `LINK`; ejemplos de
  enlaces dentro de codigo no producen findings.

## Do / Don't
- DO verificar filesystem y procesos reales, findings exactos y orden estable.
- DON'T relajar presupuestos o sustituir el validador por mocks o otro modulo.

## Tests
El oraculo nuevo comprueba el presupuesto anterior y ocho integraciones con
CLI, frontmatter anidado, enlaces, carpetas, reachability y mutaciones reales.
Las 21 pruebas anteriores del validador permanecen sin modificar.

## Constraints
PARAR y reportar si se requieren cambios de oraculos no revisados, runtime,
workflows, protecciones o la semantica de un contrato anterior.
