---
type: 'Task Contract'
title: 'Ejemplo multi-lenguaje: greet en Node.js'
description: 'Contrato de EJEMPLO (no infraestructura) que demuestra, en codigo real y verde en CI, que el sellado tests_sha256 y el perimetro touch_only son agnosticos de lenguaje: mismo scripts/validate_contracts.py --hash de siempre, sobre un archivo .js, con un test_command que corre node --test.'
tags: ['ccdd', 'template', 'multi-lenguaje']

task: example_node_greet
intent: "Demostrar un task contract completo en un lenguaje no-Python (Node.js), verde en CI."
target: examples/multi-lang/node/greet.js
signature: "function greet(name)"
test_command: "node --test examples/multi-lang/node/greet.test.js"
budget:
  max_cyclomatic_complexity: 2
  max_nesting_depth: 1
tests: "examples/multi-lang/node/greet.test.js"
tests_sha256: "6166d4b2051722084c04d4ee4cd2821fc052513fecc1ac0ddec23f808eb51610"
touch_only: ['examples/multi-lang/node/greet.js']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: Ejemplo multi-lenguaje (Node.js greet)

## Intent
Cerrar el gap identificado en la auditoria tecnica de KDD: "el multi-lenguaje
es una promesa de nivel 2 sin ningun ejemplo vivo en el repo". Este
contrato es exactamente eso — un ejemplo vivo, no infraestructura del
gate. Prueba tres afirmaciones concretas del multi-lenguaje documentado en
[validacion.md](../validacion.md#gate-multi-lenguaje) usando las
herramientas de SIEMPRE de este repo, sin ningun cambio:

1. **El sellado `tests_sha256` es agnostico de lenguaje.** El hash de
   `greet.test.js` se genero con el mismo comando que cualquier oraculo
   Python del repo: `python scripts/validate_contracts.py --hash
   examples/multi-lang/node/greet.test.js`.
2. **`touch_only` (perimetro) es agnostico de lenguaje.** `fnmatch` sobre
   rutas repo-relativas no le importa la extension del archivo.
3. **`test_command` corre verbatim.** `node --test <ruta>` es el comando
   real que corre en CI via
   [test-command-gate](./test-command-gate.md) — no hay traduccion ni
   wrapper Python de por medio.

Lo que este ejemplo NO prueba (limitacion documentada, no bug): la
validacion de `signature` por parser nativo (Nivel 1 solo verifica que el
campo exista como texto no vacio; la validacion real de firma por
lenguaje — aridad generica via tree-sitter — es Nivel 2/MCP, ver
[validacion.md](../validacion.md#gate-multi-lenguaje)).

## Interface
```javascript
function greet(name) {
  // devuelve "Hello, <name>!"
}
module.exports = { greet };
```

## Invariants
- La funcion no lanza excepciones para ningun `string` de entrada
  (incluye vacio y caracteres especiales).

## Examples
- `greet("Ana")` -> `"Hello, Ana!"`
- `greet("")` -> `"Hello, !"`
- `greet("O'Brien")` -> no lanza excepcion.

## Do / Don't
- DO: usar `node:test` + `node:assert/strict` (nucleo de Node.js, sin
  `npm install`, sin dependencias externas — mismo espiritu que
  `deps_allowed: []`).
- DON'T: agregar `package.json`/dependencias npm — este ejemplo debe
  seguir corriendo con Node solo, sin paso de instalacion.

## Tests
(Los tests estan en `examples/multi-lang/node/greet.test.js`, oraculo
congelado con `node:test`.)

## Constraints
- Sin red, sin subprocess (`forbids`).
- `touch_only`: unicamente `examples/multi-lang/node/greet.js`.
- Es un contrato de EJEMPLO (como `sample_task.md`), no infraestructura:
  esta en el `MANIFEST` de `scripts/init_project.py` y se borra con
  `--apply` junto con los demas dominios de ejemplo.
- PARAR y reportar si necesitas conectarte a la red.

## Criterios de aceptacion
- [ ] `node --test examples/multi-lang/node/greet.test.js` sale en 0.
- [ ] `python scripts/validate_contracts.py knowledge/contracts` sigue en
      0 errores con este contrato incluido.
