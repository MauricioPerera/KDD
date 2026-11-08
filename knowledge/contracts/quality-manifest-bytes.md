---
type: 'Task Contract'
title: 'Hashes exactos de los blobs del manifiesto de calidad'
description: 'Identificar bytes aprobados sin normalizar el contenido del blob.'
tags: ['quality', 'baseline', 'binary', 'integration']
task: quality-manifest-bytes
intent: 'Identificar los bytes originales de cada blob aprobado.'
target: scripts/quality_baseline.py
signature: 'def build_baseline(repo_root, policy_path, approved_ref):'
test_command: 'python -m unittest tests.test_quality_manifest_bytes'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 4
  lines_max: 160
  params_max: 3
tests: tests/test_quality_manifest_bytes.py
tests_sha256: 'b8ffc0eb9e9070b9d9e571252ec4e80933c5cf3474bacb8a517fa5e6f37308d1'
oracle_files: ['tests/test_quality_manifest_bytes.py', 'tests/quality_review_fixture.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/quality_baseline.py']
deps_allowed: ['stdlib', 'verify_quality', 'baseline_review']
forbids: ['network', 'llm']
---

## Intent
Cumplir QBR-3 del [protocolo](../quality-board-audit-remediation.md) en el
[manifiesto historico](quality-baseline.md).

## Interface
Conservar las cuatro claves approved_ref, policy, policy_sha256 y protected;
cada archivo conserva sha256 y bytes. Cada SHA256 corresponde a los bytes
exactos del blob Git original. No agregar una deteccion heuristica de binarios.

## Invariants
- No normalizar CR, LF, CRLF, NUL ni decodificar/re-encodear un blob para hashearlo.
- policy_sha256 tambien identifica el JSON original, no una reserializacion.
- Leer el commit aprobado aunque difieran el indice o la copia de trabajo.
- No cambiar la comparacion normalizada de texto de verify_quality.
- Conservar APIs, claves y rechazos de referencias no canonicas.

## Examples
- Binarios del mismo tamano con CR frente LF -> hashes distintos.
- Binario sin NUL y bytes no UTF-8 -> SHA256 de sus bytes originales.
- Politica con CRLF -> SHA256 del JSON con CRLF almacenado en Git.

## Do / Don't
- DO comparar contra hashlib.sha256 de entradas conocidas y blobs Git reales.
- DON'T normalizar contenido para conservar un resultado antiguo incorrecto.

## Tests
Casos binarios con y sin NUL, texto CRLF, politica CRLF, copia local diferente,
blobs vacios/UTF-8 y forma JSON. La unica adaptacion previa permitida es la
escritura LF explicita del fixture detallada en el protocolo; conserva todas
sus pruebas y aserciones.

## Constraints
PARAR y reportar si falta aprobacion del baseline o se necesita cambiar otra API.
No tocar runtime, workflows, dependencias ni protecciones remotas.
