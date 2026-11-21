---
type: 'Task Contract'
title: 'Lecturas Git por lote sin evidencia cacheada'
description: 'Reducir procesos Git conservando verificaciones de estado mutable e historia.'
tags: ['quality', 'maintenance', 'verification']
task: git-read-batching
intent: 'Reducir procesos Git conservando verificaciones de estado mutable e historia.'
target: scripts/task_git.py
language: python
signature: 'def read_nodes(root, ref='main'):'
test_command: 'python -m unittest tests/test_git_read_batching.py'
budget:
  cyclomatic_max: 14
  nesting_max: 4
  lines_max: 150
  params_max: 5
tests: tests/test_git_read_batching.py
tests_sha256: '3b91f91b2c53533a6e3f18c74c110af55dfe4ce063fa3f7a96a1a23cacf2df49'
touch_only: ['scripts/task_git.py', 'scripts/validate_tasks.py', 'scripts/verify_quality.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent
Aplicar el [objetivo y protocolo de cierre](../pending-improvements.md) y
conservar la [aprobacion independiente](../quality-approval.md).

## Interface
Agrupar blobs; cache solo raiz+SHA dentro de una operacion; volver a leer refs/indice/working tree. Limites medibles de procesos y equivalencia exacta de resultados.

## Invariants
Cumplir los criterios normativos de [pendientes](../pending-improvements.md)
para este componente. Oraculos, politica, SHA aprobado y controles remotos
solo cambian mediante revision explicita; ningun PASS sustituye esa revision.
Mantener compatibilidad con los contratos anteriores salvo extension documentada.

## Examples
- Doce tareas confirmadas -> lectura correcta con <=5 procesos Git.
- Otra invocacion tras mover main o alterar indice -> estado nuevo o rechazo, nunca PASS viejo.

## Do / Don't
- DO: usar procesos/objetos reales en temporales y conservar sus salidas.
- DON'T: sustituir una verificacion real por texto PASS, mocks de Git o skips.

## Tests
Oraculo sellado en tests/test_git_read_batching.py. Los casos negativos deben comprobar la
ausencia de efectos y distinguir una asercion esperada de un error de entorno.
Los escenarios, mediciones y limites viven en [pendientes](../pending-improvements.md).
El contador debe registrar procesos Git reales sin sustituir la clase Popen,
que el ejecutor aprobado de Windows usa para contener los procesos hijos.

## Constraints
PARAR y reportar si se necesita cambiar oraculos no revisados, ampliar
permisos sobre archivos protegidos o modificar una proteccion remota.
El budget es declarativo sin Nivel 2. Los tests no publican repositorios
ni registran aprobaciones sobre el repositorio de trabajo.
