---
type: 'Task Contract'
title: 'Identidad de oraculos en las dos pasadas de adopcion'
description: 'Rechazar una aprobacion de adopcion si cambia el inventario real aunque los conteos sean iguales.'
tags: ['adoption', 'oracle', 'ci', 'integration']
task: adoption-oracle-pass-identity
intent: 'Acreditar los mismos casos Python por contrato en dos ejecuciones aprobadas.'
target: tools/kdd-adoption/validate.py
signature: 'def validate_checkout(record, directory, reference):'
test_command: 'python -m unittest tests/test_adoption_oracle_pass_identity.py'
test_runner: python-unittest
budget:
  cyclomatic_max: 16
  nesting_max: 3
tests: tests/test_adoption_oracle_pass_identity.py
tests_sha256: 'e10e7c34f9f60d1c9cbecd3fddf7566742105f9bdedf21924033f9258fd0bba5'
oracle_files: ['tests/test_adoption_oracle_pass_identity.py', 'tests/adoption_remediation_support.py', 'tests/test_adoption_trusted_pr.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt']
touch_only: ['tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md', 'scripts/unittest_oracle_runner.py', 'scripts/oracle_execution.py', 'scripts/validate_test_commands.py']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Reforzar la [adopcion con referencia aprobada](adoption-trusted-pr.md).
Dos selecciones distintas de unittest pueden ejecutar el mismo numero de
casos. Su igualdad se comprueba por contrato a partir del runner fijado.

## Interface

`validate_test_commands.py CONTRACTS ROOT --oracle-receipt ARCHIVO` genera
un comprobante JSON `{"schema_version": 1, "contracts": [...]}`. Cada
elemento contiene `path` relativo a ROOT en formato POSIX y `ids`, una lista
ordenada y sin duplicados de identificadores de casos iniciados. El modo
exige contratos ejecutados con `python-unittest`, salida exitosa sin
omisiones, IDs validos para cada archivo ejecutado y coherencia con el
conteo del runner. Solo cuentan casos de los modulos seleccionados en el
comando. Un `load_tests` que ademas ejecuta un caso de otro archivo falla
aunque dicho archivo figure en el inventario como helper aprobado. Los
IDs provienen de eventos reales de unittest. El gate termina con error si
no puede acreditar el inventario completo. El comprobante requiere ejecucion
propia por contrato y rechaza el uso conjunto de `--deduplicate`.

El lanzador nuevo solicita un comprobante fresco por cada pasada aprobada,
fuera del checkout. Valida esquema, rutas exactas de todos los contratos,
IDs no vacios y unicos por contrato, y compara los pares ruta/IDs ignorando
el orden de ejecucion. Un reporte ausente o invalido falla con un diagnostico
de evidencia. Un pin sin este soporte requiere una actualizacion explicita.
El registro exitoso conserva `oracle_passes` y `executed_tests` y agrega
`oracle_inventory` con la lista canonica de contratos y sus IDs.

## Invariants

- El mismo ID en dos contratos distintos es valido. Repetir un ID dentro de
  un contrato falla. Un conteo igual o el mismo conjunto global no acredita
  los mismos casos por contrato.
- Activar el registro de IDs exclusivamente con `--oracle-receipt` y
  mantener las filas `executed`, `skipped` y `ok` del recorder. El modo
  ordinario conserva el contenido y la forma de su evidencia.
- La comparacion aprobada usa el comprobante estructurado, sin extraer
  identidad ni veredicto del stdout de las pruebas. El host y el oraculo
  Python aprobado conservan el limite de confianza de `oracle_execution`.
- Se conservan las comprobaciones de adopcion, los sellos, los checks de
  calidad y la verificacion del inventario despues de cada pasada.
- Una instalacion historica conserva su lanzador. En un lanzador nuevo sin
  referencia se mantiene el piloto historico de una pasada y su salida. Las
  invocaciones sin el nuevo argumento del gate conservan su API. El workflow
  generado conserva Ubuntu y Windows y ambas pasadas aprobadas.

## Examples

- Pasadas con `test_a` y `test_b` en orden inverso → mismo inventario.
- Pasadas de un caso cada una con IDs diferentes → fallo.
- Reporte ausente aunque el gate anterior haya salido con 0 → fallo.

## Do / Don't

- DO reutilizar la instrumentacion y la evidencia del runner gestionado.
- DON'T volver a una comparacion de conteos en una ejecucion aprobada.

## Tests

Ejecutar el paso generado de Actions y el lanzador local en Git real. Usar
un `load_tests` sellado que alterna casos, invierte orden, repite IDs o
intercambia casos entre dos contratos. Comprobar el fallo con un pin que
solo genera evidencia historica, uno que omite el segundo comprobante y
un `load_tests` que ejecuta un caso adicional de otro modulo. Conservar el
control local de una sola pasada.

## Constraints

PARAR y reportar si se necesita relajar una comprobacion o modificar el
workflow del consumidor. La referencia `KDD_TRUSTED_RUNTIME_REF` de la
suite oficial sigue fijada. El cambio opt-in se usa desde el pin del
lanzador de adopcion.

El gate, el instrumento y el recorder son fuentes de oraculos existentes.
El baseline previo fija contratos y pruebas para implementar. Antes de
publicar se revisa la referencia final con los bytes nuevos de esas tres
fuentes, preservando los demas oraculos, y se registra por separado la
[revision de rutas protegidas](trusted-ci-change-review.md) del arbol final.
