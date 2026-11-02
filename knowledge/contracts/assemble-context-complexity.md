---
type: 'Task Contract'
title: 'Reducir complejidad del ensamblador de contexto'
description: 'Cumplir el presupuesto del ensamblador preservando slots y guardrails.'
tags: ['context', 'quality', 'budget', 'integration']
task: assemble-context-complexity
intent: 'Eliminar excesos de complejidad sin alterar la seleccion y proteccion de contexto.'
target: scripts/assemble_context.py
signature: 'def assemble(contract: dict, task: str, base_dir: str) -> dict:'
test_command: 'python -m unittest tests.test_assemble_context_complexity'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_assemble_context_complexity.py
tests_sha256: '4dfd39b591238201e8874c7db7ec1b317ccd73c9a8a7ffef559591e2a065af9e'
touch_only: ['scripts/assemble_context.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

## Intent
Eliminar los cuatro hallazgos existentes del [ensamblador](assemble-context.md),
un componente de la [validacion](../validacion.md), sin elevar sus limites.

## Interface
Conservar la firma y el resultado de `assemble`, la CLI, sus codigos de salida,
mensajes y salida determinista. Conservar la excepcion `GuardrailAbort` con su
resultado parcial. Helpers privados pueden reorganizarse dentro del mismo archivo.

## Invariants
- Aplicar a todas las funciones el presupuesto vigente: complejidad ciclomatica
  maxima 10 y anidamiento maximo 4, incluidos helpers nuevos. No cambiar el
  medidor, elevar limites, excluir funciones ni mover logica a otro modulo.
- Conservar validacion, errores, prioridades, costos, limites, compactacion,
  firmas, ranking, fallback, corte por nodo y reporte honesto de seleccion.
- Mantener `regex_deny` con regex reales, aborto y modo report; `reference_check`
  y los guardrails configurados conservan su comportamiento y orden. No cambiar
  datos, configuracion, oraculos previos, dependencias ni capacidades del target.
- Conservar Ubuntu, Windows, el inventario existente y las dos pasadas de la
  suite. Ningun hallazgo global puede aparecer o agravarse con el cambio.

## Examples
- La CLI real devuelve el mismo reporte y firma dos veces para archivos iguales.
- Una tarea con una credencial sintetica y `regex_deny` aborta sin escribir en
  los nodos; en modo report se informa y devuelve exito.
- Una tarea que coincide con varios nodos conserva ranking, corte e inventario.

## Do / Don't
- DO probar filesystem y CLI reales, diagnosticos y errores sin efectos.
- DON'T relajar el presupuesto ni sustituir guardrails o pruebas por mocks.

## Tests
El oraculo nuevo verifica el presupuesto anterior y diez integraciones con
archivos, procesos, ranking, recorte, firma, presupuesto, errores y guardrails.
Los 41 casos existentes del ensamblador y prefijos permanecen sin modificar.

## Constraints
PARAR y reportar si corregir exige cambiar oraculos no revisados, runtime,
workflows, protecciones o modificar la semantica de un contrato anterior.
