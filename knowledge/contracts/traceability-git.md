---
type: 'Task Contract'
title: 'Derivar trazabilidad desde evidencia Git canonica'
description: 'Relacionar requisitos con tareas, commits y pruebas verificadas, detectando evidencia desfasada.'
tags: ['requirements', 'traceability', 'git', 'integration']
task: traceability-git
intent: 'Proyectar relaciones y vigencia desde una revision fija sin ejecutar ni modificar el proyecto.'
target: scripts/traceability_git.py
language: python
signature: 'def build_trace(repo_root, ref, manifest_path, require_verified=False):'
test_command: 'python -m unittest tests/test_traceability_git.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_traceability_git.py
tests_sha256: '7f80436d62f7d032fbec4c343d92e0af137297a07a5c0a69673741c765a19336'
touch_only: ['scripts/traceability_git.py', 'scripts/traceability_model.py']
deps_allowed: ['stdlib', 'traceability_model', 'task_git', 'task_model', 'task_evidence', 'validate_tasks', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent

Implementar la [arquitectura](../requirements-traceability.md) sobre el
[diario existente](../git-tasks.md), sin una segunda implementacion de cierres.

## Interface

build_trace resuelve ref una vez y devuelve el reporte JSON del modelo v1.
Solo subprocess Git de lectura. No ejecuta test_command, importa producto,
consulta GitHub, escribe archivos, cambia el indice o realiza checkout.

## Invariants

Comparar la huella propia contra approved_ref, validar snapshot e historial
canonicos y derivar evidencia del nodo Task. Verificado historico y vigente
se distinguen. Cambios de target, contrato, oraculo, requisito o bindings
invalidan vigencia; agregar requisitos ajenos no invalida enlaces anteriores.
Leer una revision anterior muestra su estado, sin consumir cambios locales.

## Examples

- Tarea real cerrada: link verified con SHA y evidencia originales.
- Target posterior cambiado: historical_verified=true y state=stale.
- Salto intermedio o evidencia resellada: rechazo por el diario canonico.
- Diario importado conservando commits: auditar su origen y mantener los SHA.

## Do / Don't

- DO: resolver blobs y modos regulares del commit observado.
- DON'T: tratar una URL de CI, un hash o el estado done por si solos como prueba.

## Tests

tests/test_traceability_git.py usa Git real, el coordinador real, un oraculo
ejecutado y commits de implementacion, integracion y cierre. Las mutaciones
no se simulan con mocks. El fixture compartido esta sellado por traceability-model.

## Constraints

La garantia tiene el alcance y limites del modelo; no acredita semantica de
producto o dependencias transitivas. La [extension historica](task-committed-artifacts.md)
autoriza task_git y validate_tasks para independizar la consulta del checkout.
PARAR y reportar si se necesitan otros modulos canonicos, un oraculo no revisado,
workflow, runtime o proteccion remota.
