---
type: 'Task Contract'
title: 'Claves de cache con identidad fisica de raiz'
description: 'Evitar canonicalizaciones repetidas sin compartir objetos entre repositorios distintos.'
tags: ['git', 'performance', 'integrity', 'integration']
task: task-root-identity
intent: 'Reducir el coste medido de _key conservando identidad y frescura del repositorio.'
target: scripts/task_git.py
signature: 'def _key(root, kind, revision, *parts):'
test_command: 'python -m unittest tests.test_task_root_identity'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 4
  lines_max: 160
  params_max: 5
tests: tests/test_task_root_identity.py
tests_sha256: '45701e3d42ab61decf99878cda3996024354833c9f054c3542b8077fc5f505ce'
touch_only: ['scripts/task_git.py']
deps_allowed: ['stdlib', 'task_evidence', 'task_model', 'validate_contracts']
forbids: ['network', 'llm']
---

## Intent
Eliminar el coste demostrado en el [objetivo de post-init](../postinit-windows-runtime.md)
sin cambiar las lecturas ordenadas ni la evidencia Git.

## Interface
Conservar la firma y la tupla de namespace: identidad de raiz, kind, revision
y parts. La identidad privada puede ser fisica para directorios existentes;
no es una ruta para I/O ni una autorizacion. Cien claves del mismo directorio
regular requieren como maximo dos canonicalizaciones Path.resolve.

## Invariants
- Observar la identidad del directorio actual en cada consulta, sin cachear
  stat ni congelar enlaces, cwd o refs. Una sustitucion de la raiz distingue
  los repositorios aunque su camino y los OID sean iguales.
- Aliases que apuntan al mismo repositorio comparten identidad; al redirigir
  el alias a otro repositorio, no reutilizar sus blobs ni sus pruebas.
- Si stat falla, no es un directorio o no hay identidad fisica util, conservar
  la canonicalizacion y los errores anteriores. No inventar una identidad global.
- Mantener kind, revision y parts distintos, los alcances anidados y el descarte
  de object_cache al salir. No agregar cache de contenido, resultados o refs.
- Conservar presupuesto 62, timeouts, dos pasadas, matriz y oraculos anteriores.

## Examples
- Dos clones con el mismo OID no comparten contenido cuando uno pierde un objeto.
- La raiz es movida y reemplazada: una lectura nueva falla ante el objeto ausente.
- Un sistema con inode cero usa la ruta canonical compatible.

## Do / Don't
- DO usar Git real y aliases nativos para comprobar la frontera entre raices.
- DON'T adelantar lecturas, omitir verificaciones o cachear la primera ruta observada.

## Tests
El oraculo comprueba repositorios reales, reemplazo de directorio, redireccion
de aliases, roots relativos, salida del alcance y fallback, ademas del coste
estructural de canonicalizacion sin una asercion fragil de tiempo de pared.

## Constraints
PARAR y reportar si se requiere cambiar otro oraculo, runtime, limite o proteccion
sin su revision especifica. El baseline necesita aprobacion antes de implementar.
