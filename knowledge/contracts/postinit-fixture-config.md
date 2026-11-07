---
type: 'Task Contract'
title: 'Preparacion local de fixtures sin procesos de configuracion'
description: 'Aplicar ajustes constantes con el helper existente y conservar cada prueba real y su historia independiente.'
tags: ['ci', 'windows', 'performance', 'fixtures']
task: postinit-fixture-config
intent: 'Reducir procesos auxiliares en la suite inicializada sin reducir cobertura.'
target: tests/test_task_approval_identity.py
signature: "def project(self, algorithm='sha1'):"
test_command: 'python -m unittest tests.test_postinit_fixture_config'
test_runner: python-unittest
budget:
  cyclomatic_max: 40
  nesting_max: 8
tests: tests/test_postinit_fixture_config.py
tests_sha256: '03e2e975df68e3cb64cca231591a423dc537a1292780e445d53939485976028a'
touch_only: ['tests/test_task_approval_identity.py', 'tests/test_task_history_read_cost.py', 'tests/test_task_worktree_integration.py', 'tests/test_generated_task_evidence.py', 'tests/test_ci_trusted_execution.py', 'tests/test_group_contracts.py', 'tests/test_traceability_contract_batch.py', 'tests/test_traceability_model.py', 'tests/test_baseline_git_batch.py', 'tests/test_baseline_inventory_batch.py', 'tests/test_git_reader_ref_cache.py', 'tests/test_verify_quality_complexity.py', 'tests/test_guard_pr_baseline.py', 'tests/test_trusted_change_review.py', 'tests/test_verify_quality.py']
deps_allowed: ['stdlib', 'git', 'test_fixture_preparation']
forbids: ['network', 'llm']
---

## Intent
Reducir el trabajo de [preparacion](../postinit-windows-headroom.md) mediante
el helper local existente, sin cambiar el producto ni las obligaciones de prueba.

## Interface
Los quince fixtures mantienen sus interfaces. Sustituir exclusivamente los
ajustes constantes iniciales por `configure_git` existente; los repositorios
generales efimeros usan `ephemeral=True`. Conservar valores previos de autor,
email, autocrlf, firma y detach. No cambiar usos que leen configuracion o que
ejercitan deliberadamente una mutacion de configuracion.

## Invariants
- Preparar cada repo propio despues de Git init/clone, antes de su primer
  commit. Config regular, local y con un enlace; conservar el rechazo de aliases.
- Cero procesos Git para setters constantes de preparacion; no crear procesos
  de mantenimiento automatico en esos fixtures. Los dos oraculos dedicados de
  ciclo de mantenimiento conservan su modo real habilitado y sincronico.
- Conservar Git init, clone y sus opciones, objetos, ramas, commits, escenarios,
  scripts copiados, oraculos ejecutados, cierres, evidencias, limites y limpieza.
  No compartir resultados, repositorios mutables ni trabajo entre casos.
- Conservar todos los metodos de prueba y sus cuerpos/asserts. Los cambios se
  limitan a imports y metodos auxiliares de preparacion; actualizar sus sellos.
- No modificar globals, configuracion ajena, runtime, workflow ni workers.
  La copia inicializada sin .git debe ejercitar las mismas integraciones.

## Examples
- Un clon conserva nombre/email y todos los refs sin cuatro Git config hijos.
- Mutar y cerrar un clon no cambia archivos, refs ni config de su fuente o hermano.
- Modo general: maintenance.auto=false y gc.auto=0; modo dedicado sin cambios.

## Do / Don't
- DO usar Git real, audit hooks y Trace2; contar preparacion separada de lecturas.
- DON'T eliminar casos, mocks de resultados Git, caches nuevas, esperas o checks.

## Tests
El oraculo integra preparaciones reales de los fixtures existentes, comprueba
sus ajustes mediante Git, su ausencia de setters subprocess, mantenimiento,
aislamiento y compatibilidad desde una copia inicializada sin .git.

## Constraints
Revisar el diff exacto de los quince oraculos congelados antes de adoptarlo.
PARAR y reportar si requiere otro fixture, cambiar limites, runtime o protecciones.
No declarar ahorro remoto ni cerrar el objetivo antes de las tres muestras.
