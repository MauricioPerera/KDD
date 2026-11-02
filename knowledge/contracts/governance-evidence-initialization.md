---
type: 'Task Contract'
title: 'Inicializacion sin evidencia de cierre de KDD heredada'
description: 'Retirar solo el JSON companero opcional del cierre 34 dentro del plan y transaccion del inicializador.'
tags: ['governance', 'initialization', 'evidence']

task: governance-evidence-initialization
intent: 'Retirar solo la evidencia JSON companera opcional del cierre 34.'
target: scripts/init_project.py
signature: 'def init_project(repo_dir, apply, name, repository=None) -> dict:'
test_command: 'python -m unittest tests.test_governance_evidence_initialization'
budget:
  cyclomatic_max: 10
  nesting_max: 4
tests: tests/test_governance_evidence_initialization.py
tests_sha256: '63cddda2e596f01b8ca9534c736e198dd4973ae05e3b9c857b2f6a6b762462c7'
touch_only: ['scripts/init_project.py']
deps_allowed: ['stdlib', 'bootstrap_transaction']
forbids: ['network', 'subprocess', 'llm']
---

## Intent

Completar exclusivamente la compatibilidad del
[reporte 34](governance-report-initialization.md), segun la
[propuesta KG-5](../context-learning-provenance.md). El cierre exige JSON
companero por el [contrato de completion](completion-evidence.md).

## Interface

Agregar solo docs/reports/CONTRACT-34-EVIDENCE.json al plan de limpieza opcional
explicito. Conservar API, CLI, firmas, manifests requeridos y presupuestos.
Ausencia de esa ruta no bloquea ni inventa evidencia o cierre.

## Invariants

- Presente regular -> dry-run la lista una sola vez sin cambios; apply la retira
  con el reporte y la spec, dentro del precheck y transaccion existentes.
- Ausente -> no incluirla en removed ni exigir su presencia.
- No regular/alias o falta otra entrada requerida -> abortar antes de borrar.
- Conservar evidencia de otros numeros/proyectos byte por byte; sin glob.
- No cambiar oraculos anteriores ni crear el reporte/evidencia reales del cierre.
- Preservar los 33 pares historicos, digests, rollback y fronteras vigentes.

## Examples

- JSON 34 sintetico presente -> plan una vez y apply sin identidad KDD heredada.
- JSON 34 ausente -> inicializar; JSON 35 propio -> conservar bytes.
- Directorio en ruta exacta -> rechazo previo sin borrar archivos.

## Do / Don't

- DO extender solo la ruta exacta revisada, opcional y transaccional.
- DON'T derivar permisos del patron CONTRACT-* ni modificar otro gate.

## Tests

Seis casos nuevos de tests/test_governance_evidence_initialization.py usan
copias temporales reales. Se conservan todos los oraculos anteriores, incluido
el baseline KG-5 aprobado d10ae37136da409df99c5010986efad78f878df6.

## Constraints

PARAR y reportar si hace falta otra fuente, oraculo o dependencia, elevar
budgets o cambiar workflows/protecciones. Esta ruta nueva necesita revision
propia; las aprobaciones anteriores se conservan. Implementar solo despues
del CI dual-OS 2x correcto de KG-4, junto a KG-5.
