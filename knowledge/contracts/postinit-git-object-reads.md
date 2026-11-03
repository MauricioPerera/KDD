---
type: 'Task Contract'
title: 'Lecturas Git acotadas para auditorias del proyecto inicializado'
description: 'Reducir el costo de lecturas de objetos y modos sin reutilizar resultados de pruebas.'
tags: ['git', 'bootstrap', 'performance', 'integration']
task: postinit-git-object-reads
intent: 'Reducir procesos Git de una auditoria real manteniendo sus controles de integridad.'
target: scripts/task_git.py
signature: 'def object_cache():'
test_command: 'python -m unittest tests.test_postinit_git_object_reads'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_postinit_git_object_reads.py
tests_sha256: '2a92b283bd6ca7d8512d969f81fbfa6901100969cea681b13ee17dcf2379daf6'
oracle_files: ['tests/test_postinit_git_object_reads.py', 'tests/test_traceability_model.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/task_git.py', 'scripts/traceability_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts', 'traceability_model', 'validate_tasks']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste de Git observado en el post-init de Windows sin cambiar los
oraculos, repetir menos pruebas ni convertir el timeout en exito.

## Interface
Conservar las interfaces y resultados publicos de `object_cache`, `blob`,
`blobs`, `validate_snapshot`, `validate_range` y `build_trace`. Una consulta de
snapshot, rango y trazabilidad de una tarea cerrada usa como maximo 45 procesos
Git reales dentro de una operacion, medida en el fixture de este contrato.

## Invariants
- Leer objetos y modos del commit resuelto; rechazar objetos ausentes, corruptos,
  rutas ambiguas, enlaces, submodulos y contenido incompleto sin exito parcial.
- Las referencias moviles se resuelven otra vez aunque compartan operacion; el
  cache es por repositorio, OID nativo y alcance de `object_cache`, nunca global.
- Conservar los errores observables y su orden, el historial completo, el
  perimetro y las pruebas de integridad; no cachear fallos ni resultados de tests.
- Todo proceso Git iniciado termina al cerrar el alcance, tambien ante excepcion;
  cualquier entrada no soportada o Git incompatible usa una via segura equivalente.
- Mantener los 600 segundos, Ubuntu/Windows, inventario y ambas suites completas.
  El post-init real y el CI del mismo head deben medirse sin ampliar el plazo.

## Examples
- Una tarea cerrada mantiene evidencia valida con no mas de 45 procesos Git.
- Mover `main` dentro de una operacion devuelve el blob de la nueva referencia.
- Un objeto eliminado antes de otra operacion produce fallo, nunca exito parcial.

## Do / Don't
- DO usar repositorios Git reales, Trace2 y una tarea realmente cerrada.
- DON'T reutilizar resultados de pruebas o auditar solamente el ultimo commit.

## Tests
El oraculo verifica el presupuesto en una auditoria real, refs moviles, datos de
tamano variable, objetos ausentes y cierre de procesos. Se conservan los
oraculos anteriores y las regresiones historicas de modos e importaciones.

## Constraints
PARAR y reportar si cumplir exige modificar un oraculo anterior, runtime
confiable, workflow o proteccion sin una revision y autorizacion especificas.
El baseline de contrato y oraculo requiere revision humana antes de implementar.
No declarar resuelto el timeout sin post-init y CI remotos completos.
