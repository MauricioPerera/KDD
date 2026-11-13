---
type: 'Task Contract'
title: 'Evidencia obligatoria en nuevas aprobaciones de calidad'
description: 'Rechazar comandos libres como unica evidencia de una aprobacion que requiere oraculos ejecutados.'
tags: ['quality', 'oracles', 'ci']
task: quality-required-oracle-evidence
intent: 'Exigir evidencia de oraculos en una nueva aprobacion de calidad.'
target: scripts/verify_quality.py
language: python
signature: 'def main():'
test_command: 'python -m unittest tests.test_quality_required_oracle_evidence'
test_runner: python-unittest
oracle_files: ['tests/test_quality_required_oracle_evidence.py', 'tests/test_quality_oracle_reviews.py', 'tests/test_mutation_control_evidence.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_quality_required_oracle_evidence.py
tests_sha256: 'dc91d489886c7d556e1e5d849586213d231f201d41389c40dc0942097ec647c6'
touch_only: ['scripts/verify_quality.py', 'scripts/init_project.py', '.github/workflows/validate.yml', 'knowledge/quality-approval.md']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

Aplicar [oraculos revisados](../oracle-assurance.md) a la aprobacion de calidad
de una entrega nueva. Dos salidas cero de un comando libre solo acreditan que
el comando termino.

## Interface

La CLI de verify_quality agrega --require-oracle-reviews. La API approve
admite un argumento opcional solo por nombre require_oracle_reviews. El
workflow reutilizable expone quality_require_oracle_reviews. En el workflow
de un proyecto recien inicializado el valor por defecto es estricto y puede
migrarse una politica historica con un opt-out explicito. El workflow de la
plantilla conserva su SKIP si no se solicita calidad y falta politica.

## Invariants

- En modo estricto, ausencia de politica, referencia aprobada o inventario
  oracle_reviews no vacio falla. La politica viene del objeto Git aprobado.
- ORACLE_REQUIRED identifica una politica historica en modo estricto y bloquea
  antes de ejecutar checks libres. Con inventario valido se reutiliza la revision
  congelada y sus controles sanos, contramuestras y casos esperados en las dos
  iteraciones. Un oraculo fallido o inconcluso bloquea la aprobacion.
- El workflow pasa la opcion al ejecutor correspondiente. El proyecto
  inicializado y cualquier ruta estricta extraen el ejecutor del commit aprobado
  original sin reemplazos Git. Un ejecutor
  historico que desconoce la opcion no puede aprobar en modo estricto.
- Los consumidores historicos pueden conservar su contrato de CLI y salida
  con el modo compatible. Un PASS de ese modo acredita solo sus checks libres,
  integridad y perimetro.
- La seleccion externa de referencias y las protecciones de GitHub conservan
  sus reglas. El bundle fijado de CI conserva sus seis archivos.

## Tests

Repositorios Git temporales, politica congelada, una regresion que el test
real rechaza y una politica de comandos que siempre salen cero. El caso sano
ejecuta la revision real con contramuestra. Los controles de CI verifican la
ruta estricta aun con configuracion incompleta y la compatibilidad historica.

## Examples
- Aprobacion estricta sin oracle_reviews devuelve ORACLE_REQUIRED.
- Politica valida con dos recibos reales y checks en verde aprueba.

## Do / Don't
- DO leer y ejecutar el oraculo de la politica revisada.
- DON'T derivar ejecucion de un nombre de categoria o del exit code libre.

## Constraints
Conservar el modo historico explicito, ambos sistemas y dos pasadas.
PARAR y reportar si el cambio exige sustituir la referencia aprobada o el runtime confiable.
