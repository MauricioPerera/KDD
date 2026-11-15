---
type: 'Task Contract'
title: 'Lectura agrupada de blobs aprobados en adopcion'
description: 'Agrupa cuerpos de archivos administrados por etapa de adopcion con integridad de la referencia.'
tags: ['adoption', 'git', 'performance', 'oracle']
task: adoption-approved-blob-batch
intent: 'Reducir arranques repetidos de Git en la comprobacion de archivos administrados.'
target: tools/kdd-adoption/validate.py
signature: 'def check_approved_paths(reference, paths):'
test_command: 'python -m unittest tests.test_adoption_approved_blob_batch'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 3
  lines_max: 150
  params_max: 5
tests: tests/test_adoption_approved_blob_batch.py
tests_sha256: '90a864704ca86b98c9a216cdcea60dd055ed9a51d16f832a6f1990d23b3f4af2'
oracle_files: ['tests/test_adoption_approved_blob_batch.py', 'tests/__init__.py']
touch_only: ['tools/kdd-adoption/validate.py']
deps_allowed: ['stdlib', 'git']
forbids: ['network', 'llm']
---

## Intent

Reducir las lecturas de archivos administrados de la
[adopcion aprobada](adoption-trusted-pr.md). Los mismos controles se invocan
al resolver el pin, tras preparar Python y despues de cada pasada del oraculo.

## Interface

Con una a cuatro rutas admitidas, una comprobacion realiza tres consultas
de metadatos (aprobado, HEAD e indice) y un lote de cuerpos Git. La salida
conserva los bytes aprobados de cada archivo. El lanzador se mantiene
autonomo y conserva el orden de las comprobaciones por etapa.

## Invariants

- Los modos regulares y el OID coinciden en los tres estados antes de aceptar
  el cuerpo. Se mantienen los controles de rutas del checkout, incluidos
  enlaces y cambios que `git status` no muestra.
- El lote lee por OID sin reemplazos y valida identidad, tipo, tamano,
  separadores y fin exacto de respuesta. No acredita archivos si falta un
  objeto o el lote es inconsistente. Conserva la normalizacion LF/CRLF.
- No reutilizar ni metadatos ni bytes entre invocaciones. En produccion no
  depender de un script auxiliar instalado aparte del lanzador administrado.
- Conservar regresiones existentes y ambas pasadas en Windows y Ubuntu,
  con cobertura en la primera y 600 segundos en `init-project`.

## Examples

- Cuatro archivos administrados coinciden, incluso si el checkout cambia LF
  por CRLF. El resultado contiene el cuerpo original del commit.
- El ultimo archivo cambia entre comprobaciones con assume-unchanged y la
  segunda comprobacion falla.

## Do / Don't

Medir los procesos sobre Git real. Preservar el reporte y las identidades
por contrato aun cuando las lecturas Git se agrupen.

## Tests

Repositorios Git reales con cuatro rutas, caracteres y bytes adversariales,
una entrada de indice modificada, cambios locales y reemplazos de objetos.

## Constraints

PARAR y reportar si se requiere modificar runtime fijado, workflows, timeout
o protecciones. Verificar el tiempo del post-init completo por separado.
