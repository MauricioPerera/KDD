---
type: 'Task Contract'
title: 'Coordinacion local de revisiones de baseline con Codex VPS'
description: 'Conservar los pasos del piloto y comprobar su evidencia antes de emitir el v1.'
tags: ['baseline', 'review', 'integration']
task: vps-baseline-automation
intent: 'Automatizar el piloto de revision antes del baseline con un coordinador reanudable.'
target: scripts/run_vps_baseline_review.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_vps_baseline_automation'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 85
  params_max: 5
tests: tests/test_vps_baseline_automation.py
tests_sha256: '4db126e9a52a3a9b2060be743219f458fc3149b9a6b187144dca680e28117c5f'
oracle_files: ['tests/test_vps_baseline_automation.py', 'tests/test_baseline_risk_review.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/run_vps_baseline_review.py']
deps_allowed: ['stdlib', 'prepare_baseline_review', 'baseline_review']
forbids: ['network', 'llm']
---

## Intent

Coordinar el [piloto de Codex VPS](../../docs/reports/CODEX-VPS-BASELINE-PILOT.md)
con el conector existente y la [revision v1](vps-baseline-review.md).

## Interface

`python scripts/run_vps_baseline_review.py --repo-root DIR --packet PACKET
--plan PLAN --state ARCHIVO next` emite
`{kind:"call",action_id,operation,input}` o
`{kind:"done",runId,draft,provenance,verification}`.
`record --response JSON` aplica `{action_id,result}` y devuelve JSON
`{kind:"recorded",action_id}`. La salida final usa 0 si KDD da
`review_ready`, 1 si queda bloqueada y 2 para errores de evidencia o estado.

PLAN contiene `author,risk,risk_rationale,risk_factors,reviewers`. Cada
revisor contiene `name,lenses,sources` y opcionalmente `excerpts`.
Las fuentes completas usan el formato de read_set del
contrato v1. Dos participantes con nombres distintos cubren las tres
lentes y todas las rutas cambiadas. El operador usa su conector para
`codex_send`, `codex_result` y `codex_dialogue`, y el
[transporte SSH](vps-baseline-ssh-proof.md) para `upload` y `audit`.
`codex_send` recibe solo `message`. Los mensajes incluyen las fuentes
asignadas completas, el SHA y hash, una plantilla JSON final y el delimitador `--- EVIDENCIA KDD ---`. Los extractos opcionales eligen una fuente del paquete y un intervalo
inclusivo `revision,path,start_line,end_line` (lineas desde 1). Se marcan como
`EXTRACTO RUTA INICIO-FIN` y quedan fuera del read_set. Incluir estado, codigo y evidencia
acotada del recibo de ejecucion, si existe. Si las fuentes completas y su
contexto superan 8.000 unidades UTF-16, este perfil detiene la preparacion
antes de la transferencia. Puede usarse el flujo manual para ese candidato.

El coordinador realiza upload, turnos nuevos y sondeo, audit, dialogo,
sondeo hasta cierre, repeticion exacta del dialogo y otro resultado.
La guia operativa describe como el host encadena next, llamada y record
sin intervencion humana entre operaciones.
El reintento exige `duplicate: true`, el runId original y resultados
identicos. El inicio de dialogo fija `topic,requestId,participants,handoff`
con el esquema del conector. El v1 se genera con el ensamblador existente.

## Invariants

- Verificar el paquete contra Git y validar plan y mensajes antes de emitir
  operaciones. Cada read_set y evidencia de hallazgo debe pertenecer a lo entregado
  completo al revisor. Mantener Git sin carga diferida ni red.
- Vincular el estado duradero a paquete y plan. Escribir el estado de forma
  atomica y serializar accesos al mismo archivo. Un recibo ajeno se rechaza.
  Retomar con el mismo archivo. Una colision de requestId con otro cuerpo
  no acredita el reintento. Un turno fallido o un cierre agotado bloquean
  el flujo y conservan la evidencia para diagnostico.
- Registrar una apertura pendiente antes de emitirla. Ante resultado incierto
  de `codex_send`, detenerse hasta registrar su recibo original.
- Exigir recibo de upload del hash y tamano exactos y un mismo epoch del
  despliegue desde la entrega hasta el audit. Exigir prueba de audit para
  cada turno con identidades, hashes de entrada y salida y `launch_mode: exec`.
  El eco del modelo por si solo es insuficiente.
- Conservar respuestas originales y hallazgos. La decision humana sigue la
  [politica de calidad](../quality-approval.md).

## Examples

- Git y oraculo completos, hashes y arranques acreditados y dialogo repetido
  con mismo resultado -> v1 listo y procedencia.
- Hash distinto, hilo reutilizado o runId distinto al repetir -> error.
- Lente bloqueada -> v1 bloqueado y resultado 1.

## Do / Don't

Conservar los recibos fuera de Git. Usar el comando solo en un flujo
solicitado por el operador. El CI ejecuta pruebas locales sin cuentas VPS.

## Tests

CLI, repositorios Git reales y respuestas con el esquema del conector. El
ensayo remoto se ejecuta por separado con el conector y el servidor reales.

## Constraints

PARAR y reportar si falta evidencia de entrega, apertura o reintento.
La revision opera sobre un candidato pendiente de aprobacion humana.
El contrato necesita su propia aprobacion antes de implementar. Sin
integracion en CI ni escrituras de aprobaciones.
