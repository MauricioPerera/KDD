---
type: 'Task Contract'
title: 'Preparacion local de revisiones de baseline con Codex VPS'
description: 'Vincular evidencia Git y respuestas del VPS a un borrador KDD v1 verificable.'
tags: ['baseline', 'review', 'git', 'integration']
task: vps-baseline-review
intent: 'Entregar evidencia exacta a los revisores y conservar sus dictamenes y procedencia.'
target: scripts/prepare_baseline_review.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_vps_baseline_review'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 85
  params_max: 5
tests: tests/test_vps_baseline_review.py
tests_sha256: '4c514b5ce550a5a29ff45df683b229dfa8ab583998bc93b2abdb4ee586768667'
oracle_files: ['tests/test_vps_baseline_review.py', 'tests/test_baseline_risk_review.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py']
touch_only: ['scripts/prepare_baseline_review.py']
deps_allowed: ['stdlib', 'baseline_review']
forbids: ['network', 'llm']
---

## Intent

Piloto local optativo para la [revision anterior al baseline](../baseline-risk-review.md).
Preparar el material antes de convocar a los especialistas y conservar la
[revision externa](../quality-approval.md) como decision humana.

## Interface

- `prepare_baseline_review.py prepare --base-ref SHA --candidate-ref SHA` emite
  `{packet, packet_sha256, requestId}`. Admite `--repo-root DIR`, `--source
  REVISION:RUTA` repetible y `--execution ARCHIVO.json`. El paquete contiene
  `schema_version: 1`, `policy_version: "kdd-vps-baseline-review-v1"`, los tres
  OID, el piso y los cambios de `inspect_change`, `diff_b64`, `sources` y
  `execution`. Cada fuente contiene `revision`, `path`, `mode`, `oid`,
  `sha256` y `content_b64`. Se incluyen ambos lados presentes de cada cambio.
  `execution` es null o un recibo local con `candidate_commit`, `argv` como
  lista, `status` (passed, failed o infrastructure_error), `exit_code`
  entero, y `stdout`/`stderr` de texto. Identifica el mismo candidato. El
  estado passed exige codigo cero y failed exige codigo distinto de cero.
  Se conserva el recibo declarado.
- `prepare_baseline_review.py assemble --packet ARCHIVO --handoff ARCHIVO`
  admite `--repo-root DIR` y emite `{draft, provenance, verification}`.
  `draft` tiene el esquema v1 existente. `verification` es el resultado de
  `verify_review`. Cero significa listo para solicitar aprobacion, uno deja
  el borrador con los hallazgos que impiden declararlo listo, dos rechaza una
  entrada invalida sin resultado parcial.
- El handoff es un objeto con `requestId`, `runId` del dialogo, `author`,
  `risk`, `risk_rationale`, `risk_factors` y `turns`. Cada turno contiene
  `id`, `reviewer`, `result` (respuesta individual de codex_result) y
  `opening` (registro de apertura del coordinador, o null). Un resultado
  completado aporta `runId`, `conversationId`, `threadId`, `status`,
  `output` y `error`. El output es JSON con `sha`, `packet_sha256`,
  `lenses`, `read_set` y `findings`. Los turnos de dialogo pueden entregar
  ese JSON como texto en `{message,next}`. El resultado debe tener estado
  `completed` y error nulo. Se rechazan los resultados incompletos o fallidos.
  Se conserva tambien el formato archivado
  `{sha,lenses,findings}` para diagnostico, asignandole lectura vacia y
  contexto fresco falso y estado `not_run` en el v1. No se consume el estado de aceptacion del dialogo.
- `opening` exige `runId`, `conversationId`, `threadId` exactos para el turno
  y `launch_mode` con valor `exec`. Es un dato local proporcionado por el
  coordinador que observo el lanzamiento sin reanudar un hilo. Su ausencia
  deja `fresh_context` falso. Se rechazan identidades de turno, conversacion
  o hilo reutilizadas entre revisores. Las respuestas deben ser de agentes.
- `provenance` conserva el identificador de solicitud y dialogo, el SHA-256
  canonico de paquete, handoff y v1, y por revisor el turno, conversacion,
  hilo, apertura, hash UTF-8 de su salida e indicacion del eco del paquete.

## Invariants

- El paquete se genera desde objetos Git, sin checkout, hooks, diff externo,
  textconv ni ejecucion del candidato. La CLI deshabilita la carga diferida
  de Git durante todo el proceso y falla si falta un objeto local. Las rutas
  adicionales son exactas y
  las fuentes son blobs regulares. Una fuente ausente o no regular se rechaza.
  El diff usa OID completos y atributos del arbol candidato, con opciones
  fijas. Los cambios locales de core.abbrev y .gitattributes no lo alteran.
- El ensamblador regenera el paquete desde Git y compara el contenido antes
  de confiar en el hash, aun si un tercero recalculo un hash coherente.
- JSON canonico es UTF-8, sin espacios, claves ordenadas y sin NaN. El SHA-256
  cubre esos bytes. El requestId es UUID v5 (namespace URL) del texto
  `kdd-vps-baseline-review/<policy_version>/<candidate_commit>/<packet_sha256>`.
  Repetir exactamente los artefactos conserva solicitud, borrador y procedencia.
- Toda lectura o evidencia de un hallazgo debe referenciar una fuente del
  paquete. El requestId del handoff debe coincidir con el del paquete. Toda
  respuesta debe nombrar el SHA exacto. El hash de las respuestas modernas
  debe coincidir con el del paquete.
  Las perspectivas bloqueadas se conservan en el v1.
- La procedencia enlaza registros declarados por el coordinador. No autentica
  personas, ni prueba la lectura efectiva, ni deduce apertura de un ID distinto.
- La transferencia del paquete y su entrega al revisor son pasos explicitos.
  No se agrega red, scheduler, procesos de modelos en CI ni escritura
  de archivos, refs, protecciones o registros de aprobacion.

## Examples

- Dos respuestas enlazadas y las fuentes cubiertas -> v1 listo y procedencia
  separada. Una perspectiva blocked -> `LENS_BLOCKED`, incluso si el dialogo
  se cerro con el objetivo aceptado.
- Un turno historico con dictamen bloqueado -> conservar el bloqueo y dejar
  explicita la falta de prueba de entrega y apertura.
- Un turno declara una ruta que existe en el commit pero falta en el paquete,
  o la evidencia se altera y se vuelve a sellar -> rechazo.

## Do / Don't

- DO conservar paquete y recibos fuera del commit y usar el verificador v1
  para decidir si se puede solicitar revision humana.
- DON'T incluir metadatos VPS en el v1 ni convertir un resultado de
  infraestructura en evidencia de pruebas exitosas.

## Tests

Integraciones con Git real, cambios solo locales, el verificador y ambas
operaciones CLI. Ejercitan asociaciones incorrectas y la conservacion de
bloqueos historicos. Los datos de transporte de prueba son sinteticos.

## Constraints

PARAR y reportar si falta revision del commit exacto de contrato y oraculo antes de implementar.
Reutilizar el verificador, el esquema v1 y la cola idempotente del VPS.
