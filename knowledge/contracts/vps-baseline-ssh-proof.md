---
type: 'Task Contract'
title: 'Prueba de entrega y apertura en el servidor Codex VPS'
description: 'Cotejar el paquete, las filas de turnos y los eventos de ejecucion sin confiar en el modelo.'
tags: ['baseline', 'vps', 'provenance']
task: vps-baseline-ssh-proof
intent: 'Obtener recibos independientes del modelo por SSH en el VPS autorizado.'
target: scripts/vps_review_ssh.py
signature: 'def main(argv=None):'
test_command: 'python -m unittest tests.test_vps_baseline_ssh_proof'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 85
  params_max: 5
tests: tests/test_vps_baseline_ssh_proof.py
tests_sha256: '0458bf73e2d81966401d502471ed4240796417a564c8574d1d78864dd1273d58'
oracle_files: ['tests/test_vps_baseline_ssh_proof.py', 'tests/__init__.py']
touch_only: ['scripts/vps_review_ssh.py']
deps_allowed: ['stdlib']
forbids: ['llm']
---

## Intent

Aportar los recibos del [coordinador](vps-baseline-automation.md) con la
tecnica comprobada en el [piloto](../../docs/reports/CODEX-VPS-BASELINE-PILOT.md).

## Interface

`python scripts/vps_review_ssh.py --host HOST --request ARCHIVO.json
--worker-sha256 SHA --launcher-sha256 SHA`
recibe una llamada `upload` o `audit` del coordinador y emite el JSON
`{action_id,result}`. HOST es el alias OpenSSH autorizado por el operador. Los hashes identifican
la version revisada del ejecutor y su lanzador en ese VPS.

`upload` recibe `requestId,sha256,content_b64`. Guarda los bytes canonicos
en una ruta privada por solicitud y devuelve `handle,sha256,bytes` tras
leerlos de nuevo, junto con el hash `epoch` de la identidad del despliegue.
`audit` recibe `requestId,upload,turns`. `turns` identifica
los `runId,conversationId,threadId` completos. Devuelve `sha256,bytes,epoch,turns`.
Cada fila de turno agrega `payload_sha256,output_sha256,prior_jobs,started,
completed,launch_mode` a los tres IDs. El servicio del piloto usa
`codex-webhook.service`, tabla `codex_webhook_jobs` y unidades
`codex-turn@RUN.service`. El origen de stdin y la decision de reanudar se
cotejan con el ejecutor desplegado.

## Invariants

- El upload valida hash antes de escribir y tras la lectura. Repetir una
  solicitud con bytes identicos conserva el recibo. Rechazar colisiones y
  rutas que salgan del directorio privado de la solicitud.
- El audit relee el paquete. SQLite se abre en solo lectura. Las filas deben
  coincidir con los tres IDs, completadas y sin error. Correlacionar inicio
  y fin del turno en el journal con los tres IDs, desde la entrega. Upload
  y audit validan ambos hashes, la unidad activa y la identidad de su
  invocacion. La huella incluye metadatos de los archivos del despliegue
  y de la unidad de turnos. Distinto epoch invalida la apertura, incluso
  si el contenido vuelve al mismo hash. Con cero trabajos anteriores,
  el codigo fijado implica exec. Una conversacion
  con trabajos previos produce modo no acreditado. Ningun
  `threadId` devuelto por el modelo acredita apertura por si solo.
- SSH comprueba la identidad del host, sin cambiar la configuracion del
  servicio y sin copiar credenciales o contenido de la base a stdout.

## Examples

- Mismo paquete y dos filas completas con eventos -> hashes y aperturas.
- Paquete alterado, recibo ajeno o journal sin apertura -> error.

## Do / Don't

Preservar solo metadatos y hashes en la salida del audit. El operador
confia en el host, sus archivos y su journal. El conector autenticado
lleva las solicitudes al modelo.

## Tests

Archivos privados, SQLite real, correlacion de eventos y rechazos dirigidos.
El ensayo remoto valida el servicio y el journal reales por separado.

## Constraints

PARAR y reportar si falta acceso al servicio
autorizado. El modo de prueba local no contacta con el VPS en CI.
