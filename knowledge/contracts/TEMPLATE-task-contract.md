---
type: 'Task Contract'
title: '<titulo corto de la tarea>'
description: '<que hace, en 1 frase>'
tags: ['<tag1>', '<tag2>']

task: <nombre-kebab-case>
intent: "<UNA sola frase con UN verbo. 'y ademas...' la rompe.>"
target: <ruta/al/archivo.py>
signature: "<def firma(arg: tipo) -> tipo:>"
test_command: "<comando que corre SOLO los tests de esta tarea, ej. 'python -m unittest tests/test_x.py'>"
budget:
  max_cyclomatic_complexity: <numero, empeza en 5-8 para funciones simples>
  max_nesting_depth: <numero, 2-3 salvo razon documentada>
tests: "<ruta/al/archivo/de/tests>"
tests_sha256: "<64 chars hex — generalo con: python scripts/validate_contracts.py --hash <ruta/al/archivo/de/tests>>"
touch_only: ['<ruta/al/archivo.py>']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: <titulo corto de la tarea>

## Intent
<Que resuelve esta tarea y por que. 2-4 lineas. Enlaza a un nodo OKF si
corresponde, ej. [la especificacion OKF](../OKF-SPEC.md).>

## Interface
```
<firma completa: def nombre(args) -> tipo_retorno:>
```

## Invariants
- <propiedad que SIEMPRE debe cumplirse, independiente del input>
- <ej: la funcion no lanza excepciones / el output es siempre una lista>

## Examples
- `<llamada("input1")>` -> `<output esperado>`
- `<llamada("input2")>` -> `<output esperado>`
- `<caso limite, ej. input vacio>` -> `<output esperado>`

## Do / Don't
- DO: <patron esperado, ej. usar f-strings>
- DON'T: <algo prohibido explicito, ej. no usar red/subprocess>

## Tests
(Los tests estan en `<ruta declarada en 'tests' arriba>` — se escriben
ANTES de delegar la implementacion; son el oraculo congelado, sellado por
`tests_sha256`.)

## Constraints
- PARAR y reportar si necesitas conectarte a la red.
- PARAR y reportar si el `intent` resulta imposible de cumplir sin violar
  `touch_only` o `forbids`.

---

<!--
COMO USAR ESTA PLANTILLA (borrar este bloque en tu copia):

1. Copiala con un nombre real: `cp knowledge/contracts/TEMPLATE-task-contract.md
   knowledge/contracts/mi-tarea.md`
2. Escribi PRIMERO el archivo de tests declarado en `tests:` (el oraculo
   congelado) — antes de tocar el target. Esa es la Capa 0: quien define
   "exito" nunca es quien implementa.
3. Sella el hash: `python scripts/validate_contracts.py --hash <ruta/tests>`
   y pegalo en `tests_sha256`.
4. Crea un stub vacio en `target` (para que el archivo exista).
5. Reemplaza TODOS los placeholders `<...>` de este archivo.
6. Corre `python scripts/validate_contracts.py knowledge/contracts` — debe
   dar 0 errores antes de delegar la implementacion a nadie.
7. Guia completa paso a paso: `knowledge/quickstart.md`.

Esta plantilla NO es un contrato real: `TEMPLATE-*.md` se excluye del gate
(`scripts/validate_contracts.py`, ver `_collect_files`) igual que
`specs/TEMPLATE-CONTRACT.md` se excluye de `validate_specs.py`. No la borres
al instanciar el proyecto: `scripts/init_project.py --apply` NO la toca
(no esta en su `MANIFEST` de artefactos de ejemplo).
-->
