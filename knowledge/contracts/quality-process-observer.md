---
type: 'Task Contract'
title: 'Identidad estable del observador de procesos de calidad'
description: 'Eliminar consultas tardias por PID conservando la deteccion real de fugas y los vecinos independientes.'
tags: ['processes', 'windows', 'fixtures', 'integration']
task: quality-process-observer
intent: 'Estabilizar la observacion del objeto propio en el oraculo de contencion.'
target: tests/test_quality_process_lifecycle.py
signature: 'class QualityProcessLifecycle(unittest.TestCase):'
test_command: 'python -m unittest tests.test_quality_process_identity'
test_runner: python-unittest
test_timeout: 180
budget:
  cyclomatic_max: 40
  nesting_max: 8
  lines_max: 180
  params_max: 5
tests: tests/test_quality_process_identity.py
tests_sha256: 'd46c903d4881d35e5fa20d8339b43ec22a2ce4f0eb6297f9f76197a58588a701'
oracle_files: ['tests/test_quality_process_identity.py']
touch_only: ['tests/test_quality_process_lifecycle.py']
deps_allowed: ['stdlib', 'git', 'test_quality_process_lifecycle']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo de identidad estable](../process-observer-identity.md)
sin alterar la [barrera de produccion](process-exit-barrier.md) ni sustituir
el [oraculo de calidad](quality-process-lifecycle.md) por una declaracion.

## Interface
Conservar QualityProcessLifecycle, sus doce metodos, invoke, assert_contained
y el CLI real de calidad. El fixture agrega un observador privado y readiness
confirmado antes de que puedan terminar los hijos y nietos originales.

## Invariants
- Retener el objeto propio vivo antes de confirmar readiness. La consulta
  final usa ese objeto, sin volver a resolver un PID liberado en Windows/Linux.
- Exigir terminacion inmediata al retornar calidad. No esperar durante la
  asercion ni realizar retries para transformar una fuga en un aprobado.
- Conservar hijos, nietos, vecinos, dos rondas, escrituras tardias, archivos
  protegidos y cada metodo y asercion anterior. Una fuga deliberada se rechaza.
- Fallar ante errores nativos y cerrar recursos en exito y excepcion. La
  limpieza del fixture no puede actuar antes de la observacion de contencion.
- Mantener Ubuntu/Windows, ambas suites, post-init y todos los timeouts. No
  cambiar scripts, runtime, workflows, variables ni protecciones.

## Examples
- Dos generaciones originales terminan: sus objetos retenidos estan senalados.
- Un vecino ajeno sigue vivo y completa su trabajo tras liberarlo.
- Un helper deliberadamente inseguro devuelve PASS dejando hijos vivos: el
  mismo oraculo real rechaza el resultado y luego limpia sus procesos propios.

## Do / Don't
- DO registrar APIs nativas reales antes/despues y cerrar todos sus recursos.
- DON'T simular reciclado de PID, ocultar errores, relajar aserciones o tiempos.

## Tests
Cinco integraciones reales cubren identidad retenida, vecino, fuga deliberada,
errores de observacion y cierre de recursos. La instrumentacion cuenta llamadas
reales, sin falsificar su resultado. La copia inicializada ejecuta los mismos
controles sin Git del repositorio fuente. Los doce casos previos se conservan.

## Constraints
El fixture objetivo es un oraculo congelado. Su propuesta y sello se revisan
junto con este contrato antes de adoptarlos, segun
[quality-approval](../quality-approval.md). PARAR y reportar si el runtime
tambien requiere cambios o si se necesita adoptar otro baseline, publicar,
cambiar un workflow, una variable remota o una proteccion sin autorizacion.
