---
type: 'Task Contract'
title: 'Lecturas Git agrupadas para la procedencia de licencias'
description: 'Reduce arranques de Git durante las dos fases de la evidencia de compliance.'
tags: ['compliance', 'git', 'performance']
task: compliance-scan-git-batches
intent: 'Conservar las pruebas de procedencia con un coste acotado de procesos Git por lote.'
target: scripts/optional_evidence.py
signature: 'def evaluate_layers(layers, required, environ, summary=False):'
test_command: 'python -m unittest tests.test_compliance_scan_git_batches'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 180
  params_max: 4
tests: tests/test_compliance_scan_git_batches.py
tests_sha256: 'd1d2f486f3b4b4c8aa06a2279a9133e0cf0eef5224193dabad81cf0683da8a42'
oracle_files: ['tests/test_compliance_scan_git_batches.py', 'tests/test_goldfish_compliance.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/optional_evidence.py']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

El [protocolo de procedencia](compliance-scan-provenance.md) compara los
mismos insumos entre commits. Cada ruta actualmente inicia lecturas Git
individuales. Agruparlas reduce el coste incluso en inventarios pequeños.

## Interface

Conservar `optional_evidence.py check|summary`, las referencias externas, los
formatos y los estados. Con tres revisiones distintas y los dos JSON, cada
fase usa como máximo 15 procesos Git tanto con dos insumos como con 18, en
un lote de rutas cortas. Presupuestar hasta 4.096 bytes por grupo de rutas
para `ls-tree`, incluyendo tres bytes por nombre para separadores y comillas.
Con 30 rutas de aproximadamente 165 bytes y los dos insumos originales,
la fase admite hasta 20 procesos. Conservar todos los modos e insumos al
partir cada grupo.

## Invariants

- Leer los modos y confirmar rutas exactas en cada revisión pertinente.
  Obtener cuerpos por OID con la longitud declarada por Git. Índice,
  `.gitattributes`, sustitución Git y rutas ambiguas no alteran el resultado.
- Conservar el orden lógico de verificación. El manifiesto aprobado define
  los insumos. Cada fase observa en esa ejecución el checkout y los árboles
  correspondientes. No reutilizar lecturas o resultados entre fases.
- Los insumos Git conservan bytes exactos. Solo `text_inputs` admite LF y
  CRLF en el checkout. Rechazar archivos omitidos, modos no regulares,
  objetos ausentes y respuestas de Git inconsistentes o con datos sobrantes.
- Mantener la implementación dentro del script protegido que ya invoca CI.
  Usar procesos Git de lectura acotados y sin reemplazos ni descarga tardía.

## Examples

- Un insumo binario con NUL y saltos de línea conserva sus bytes y pasa.
- Si cambia el último insumo, el gate falla incluso cuando `git replace`
  dirige las lecturas normales a los bytes del commit aprobado.

## Do / Don't

Leer lotes con herramientas Git existentes. La revisión externa sigue fijando
la procedencia y el alcance que acredita el scanner.

## Tests

Medir lanzamientos reales en Trace2 por fase sobre repositorios Git con tres
commits distintos. Probar rutas con espacios, cuerpos binarios, reemplazos,
modo de enlace con el mismo OID y entradas ausentes al final de un lote.
Incluir una divergencia exclusiva del commit aprobado y una ruta de ejecución
que obligue a partir el argv.

## Constraints

PARAR y reportar si se requiere cambiar los workflows, el runtime confiable o
el perímetro de la revisión. El ahorro del post-init se mide por separado.
