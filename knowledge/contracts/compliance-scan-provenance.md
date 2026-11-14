---
type: 'Task Contract'
title: 'Atribución verificable de evidencia requerida de licencias'
description: 'Vincula el informe de licencias, sus insumos Git y el registro externo revisado del escaneo.'
tags: ['compliance', 'ci', 'evidence']
task: compliance-scan-provenance
intent: 'Impedir que un informe de licencias sin procedencia acredite el control del producto.'
target: scripts/optional_evidence.py
signature: 'def evaluate_layers(layers, required, environ, summary=False):'
test_command: 'python -m unittest tests.test_goldfish_compliance'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 180
  params_max: 5
tests: tests/test_goldfish_compliance.py
tests_sha256: 'ccc361d9c1e2809df3858ff76e83abd2ac996527efa3db407951bfca2ea0cd3f'
oracle_files: ['tests/test_goldfish_compliance.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/optional_evidence.py', '.github/actions/validate-contracts/action.yml', 'knowledge/data_models/compliance_findings.md', '.agents/skills/kdd-compliance-scan/SKILL.md']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent

El [validador de licencias](../data_models/compliance_findings.md) comprueba la
política sobre las entradas del informe. La capa requerida también acredita un
escaneo revisado de los insumos específicos del producto.

## Interface

Usar `scan-manifest.json` al lado de `findings.json`. Su objeto v1 exige las
claves `schema_version` (1), `source_ref` (SHA completo), `tool`
(`name` y `version`), `inputs` (mapa no vacío de rutas relativas a SHA-256
de bytes Git) y `findings_sha256` (SHA-256 UTF-8 con LF canónico). La única
clave opcional es `text_inputs`, un inventario de rutas únicas dentro de
`inputs`, que el revisor acredita como texto UTF-8 sin NUL.
La referencia revisada proviene de `KDD_COMPLIANCE_APPROVED_REF` o, cuando no
se proporciona, `KDD_APPROVED_BASELINE_REF`. Exigir una de esas referencias
externas; HEAD por sí solo no constituye aprobación. La acción compuesta admite
`compliance-approved-ref` y necesita historia del checkout suficiente para
demostrar las relaciones de ancestro. Ambas fases de CI verifican procedencia.

## Invariants

- Leer escaneo, referencia revisada y candidato como commits Git, sin reemplazos.
  El escaneo es ancestro de la aprobación y la aprobación del candidato. El
  candidato de CI es `GITHUB_SHA` y coincide con HEAD. La CLI local usa HEAD.
  La aprobación puede ser el propio SHA candidato si viene del revisor externo.
- El manifiesto y el informe son archivos regulares protegidos por identidad de
  contenido en el SHA revisado, el candidato y los bytes utilizados por el gate.
  Rechazar rutas ambiguas que escapen del checkout, enlaces, objetos no regulares,
  JSON ambiguo o alteraciones de SHA. Canonizar LF solo para los dos JSON.
  El informe de cumplimiento debe declarar la lista `findings`, incluso vacía.
- Para cada insumo declarado exigir un blob regular con el hash exacto en
  el SHA escaneado, revisado y actual. Comparar la copia local con esos bytes
  y admitir LF/CRLF equivalentes solo para las rutas revisadas en `text_inputs`.
  Los atributos del checkout no deciden esa excepción. Las rutas del
  manifiesto delimitan la cobertura. La revisión externa comprueba alcance,
  procedencia del scanner y suficiencia semántica antes de aprobar su SHA.
- Un resultado opcional sin manifiesto puede seguir evaluándose por el validador
  estructural y el resumen lo marca SKIP. Evidencia requerida sin procedencia
  válida da FAIL antes de aceptar el outcome. Un informe vacío con escaneo
  revisado y vigente puede pasar. Las otras capas conservan sus estados.

## Examples

- Un auditor ejecuta el scanner del proyecto y un revisor fija un commit que
  contiene informes y manifiesto. PASS con los mismos insumos y outcome success.
- Renombrar un ejemplo, inventar una procedencia en el candidato o cambiar un
  insumo revisado: FAIL en la capa requerida.

## Do / Don't

Conservar la separación entre ejecución del scanner y validación del informe.
Los hashes y la revisión atribuyen los insumos declarados. La cobertura de
dependencias fuera de ese inventario exige revisión del proyecto.
Mantener la verificación de procedencia dentro de `scripts/optional_evidence.py`,
que ya protege `trusted-pr-gate`.

## Tests

Repositorios Git temporales con manifiestos de dependencias, un productor
ejecutado en el fixture y los entry points reales de ambas fases de CI.

## Constraints

PARAR y reportar si se necesita convertir referencias externas en autoaprobación
o ampliar la revisión a otras capas para cerrar este contrato.
