---
type: 'Task Contract'
title: 'Cobertura de Python medida en la primera pasada de CI'
description: 'Publicar mediciones de lineas y ramas por sistema y rechazar informes de hallazgos incompletos.'
tags: ['coverage', 'quality', 'ci']
task: ci-measured-coverage
intent: 'Distinguir evidencia de cobertura ejecutada de un informe incompleto.'
target: .github/workflows/validate.yml
language: yaml
signature: 'measure_coverage(validate, matrix.os, first_pass)'
test_command: 'python -m unittest tests.test_ci_measured_coverage'
test_runner: python-unittest
oracle_files: ['tests/test_ci_measured_coverage.py', 'tests/coverage_isolated_probe.py', 'tools/ci-coverage/requirements.txt']
budget:
  cyclomatic_max: 14
  nesting_max: 4
tests: tests/test_ci_measured_coverage.py
tests_sha256: '7fe5b1a930b3d88e353d5117de110ff9986ddeebf60d9b2c8b77f4d2bce63fe9'
touch_only: ['.github/workflows/validate.yml', 'scripts/validate_test_coverage_findings.py', 'scripts/ci_coverage.py', 'knowledge/validacion.md', 'knowledge/data_models/test_coverage_findings.md']
deps_allowed: ['stdlib', 'coverage.py']
forbids: ['llm']
---

## Intent

Medir cobertura de codigo Python sin agregar otra pasada ni sustituir el
inventario de casos de CI. Los [hallazgos cualitativos](../data_models/test_coverage_findings.md)
usan un formato distinto de la medicion de lineas y ramas.

## Interface

El validador de hallazgos devuelve 2 si existe un informe que incumple el
esquema. Una ausencia en una capa opcional sigue siendo INFO. La medicion
del CI nativo usa una dependencia fijada por version y hashes, un directorio
por job fuera del checkout y reportes JSON por SO, SHA, run e intento.

## Invariants

- El informe de hallazgos exige documentType, schemaVersion, scanId y una
  lista findings explicita. Cada entrada cumple los campos y tipos del
  esquema. El ejemplo completo y una lista vacia valida pasan segun las
  reglas de remediacion; ausencia de lista, null y tipos incorrectos fallan.
- Medir solo la primera de las dos invocaciones existentes del runner confiable
  en Ubuntu y Windows. Mantener el comando, los workers y los inventarios.
  Medir tambien procesos Python descendientes aislados con -I. No ampliar el
  runtime confiable ni instrumentar la segunda pasada.
- Publicar lineas y ramas de Python para scripts, src, site y tools/kdd-adoption
  del checkout, con sus denominadores. La medicion no atribuye cobertura al
  tablero TypeScript. El JSON identifica el SHA, SO y la pasada medida.
- La preparacion y agregacion nunca reutilizan datos de otros intentos.
  Datos ausentes, vacios o ilegibles impiden publicar cobertura valida.
  El reporte es una medicion inicial, sin imponer un porcentaje arbitrario.
- La matriz de Board, pruebas de contratos, dos inventarios y Pages conservan
  sus verificaciones. Los proyectos que consumen el workflow reutilizable no
  reciben una instalacion nueva por defecto.

## Tests

Procesos reales del validador con informes completos e incompletos.
Comprobar el cableado de las dos pasadas. Como verificacion de integracion de
la instrumentacion, ejecutar un runner Python aislado con un hijo aislado que
cubre ramas distintas, combinar los datos reales en Ubuntu y Windows con el probe explicito y
comprobar los denominadores y que la segunda pasada no escribe fragmentos.

## Examples
- Falta findings en un informe presente: exit 2.
- Dos ramas ejercitadas en procesos diferentes: dos ramas cubiertas en el informe.

## Do / Don't
- DO medir las ramas de procesos Python aislados.
- DON'T tratar un inventario de casos o un reporte ejemplo como cobertura.

## Constraints
Conservar Ubuntu, Windows, las dos pasadas y el bundle confiable fijado.
PARAR y reportar si la instrumentacion requiere cambiar el runner fijado o agregar una pasada.
