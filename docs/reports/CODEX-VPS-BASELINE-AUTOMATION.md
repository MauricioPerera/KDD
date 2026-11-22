# Revisión de baseline con Codex VPS

Una sesión de Codex con el conector **Codex VPS Demo** puede llevar una
revisión desde el paquete de Git hasta el borrador v1 validado por KDD.
El responsable revisa ese borrador y decide si aprueba el SHA. El
coordinador se ejecuta a solicitud del operador, fuera del CI.

## Preparar una revisión

1. Identificar la base y el candidato por sus SHA completos. Ejecutar los
   oráculos pertinentes y conservar su resultado, incluso en fase roja.
   `scripts/prepare_baseline_review.py prepare` admite un recibo
   `--execution` para el candidato con los campos
   `candidate_commit, argv, status, exit_code, stdout, stderr`.
2. Guardar el resultado de `prepare` en `packet.json` con UTF-8, en un
   directorio de evidencia ignorado por Git. Examinar el diff, las versiones
   de las fuentes incluidas y el recibo. Confirmar que se pueden enviar al
   VPS autorizado. Los archivos de contexto adicionales entran al paquete
   con `--source REVISION:RUTA`.
3. Escribir un `plan.json` con `author, risk, risk_rationale, risk_factors,
   reviewers`. Asignar a dos revisores todas las rutas cambiadas y las
   lentes `simplicity, implementation, oracle`. Cada entrada tiene
   `name, lenses, sources`. Las fuentes completas son pares
   `{"revision":"candidate","path":"ruta"}`. Para una ruta eliminada,
   usar `base`. Un extracto opcional en `excerpts` añade
   `start_line, end_line` al par de revisión y ruta; solo da contexto.

Cada mensaje admite hasta 8.000 unidades UTF-16. Si un candidato excede
ese tamaño con sus fuentes completas repartidas, el coordinador se detiene
antes del envío. Para candidatos más grandes sigue disponible el
[procedimiento del piloto](CODEX-VPS-BASELINE-PILOT.md).

## Ejecutar en Codex

En una sola solicitud para Codex, indicar el checkout, el paquete, el plan,
el archivo de estado, el alias SSH ya autorizado y los dos SHA-256
revisados del worker y lanzador. Pedir que siga este bucle hasta `done`
o un fallo y que conserve los recibos originales en el directorio de
evidencia. El host usa el conector autenticado de la sesión.

```sh
python scripts/run_vps_baseline_review.py --repo-root DIR --packet packet.json --plan plan.json --state state.json next
```

| `operation` | Acción de la sesión |
| --- | --- |
| `upload`, `audit` | Guardar la llamada completa como `call.json`. Ejecutar `python scripts/vps_review_ssh.py --host HOST --request call.json --worker-sha256 SHA --launcher-sha256 SHA`. |
| `codex_send` | Invocar la herramienta homónima con `input` exacto. La solicitud abre una conversación nueva. |
| `codex_result` | Consultar el `runId` exacto. Esperar entre sondeos mientras figure `queued` o `running`. |
| `codex_dialogue` | Invocar con `input` exacto, también en la repetición. |

Para SSH, guardar la salida JSON directamente como `receipt.json`.
Para MCP, conservar el resultado de la herramienta y envolverlo como
`{"action_id":"ID_DE_LA_LLAMADA","result":RESULTADO}`. Si la
herramienta da error, conservar la respuesta y detenerse. El coordinador
valida cada recibo antes de emitir la próxima acción.

```sh
python scripts/run_vps_baseline_review.py --repo-root DIR --packet packet.json --plan plan.json --state state.json record --response receipt.json
```

Usar el mismo paquete, plan y estado al retomar. Si la sesión interrumpe
un `codex_send` antes de registrar su recibo, la apertura queda pendiente
hasta recuperar el recibo original. Las operaciones de lectura y el
inicio del diálogo con su clave pueden repetirse. Si el archivo
`state.json.lock` quedó tras terminar el proceso, comprobar que su PID
ya no ejecuta ese flujo antes de quitar el archivo.

## Qué comprobar al cierre

- `provenance.upload` conserva la identidad, tamaño, SHA-256 y huella del
  despliegue. El paquete se guarda por solicitud en el VPS, en
  `/var/lib/kdd-vps-review`, con acceso privado.
- `provenance.audit` coteja la misma huella y los hashes del paquete y
  de los turnos. Los IDs corresponden a filas completas y eventos de
  apertura y cierre del journal. La apertura exige cero trabajos previos
  y el código revisado que selecciona `exec`.
- `provenance.replay` acredita `duplicate: true` y el mismo `runId`.
  El coordinador vuelve a consultar el resultado y compara la respuesta
  completa con la original.
- Guardar `draft` como `review-v1.json`. `verification.review_ready`
  es el veredicto del verificador de KDD. Puede ser falso si quedan
  hallazgos o una lente bloqueada. El código de salida de `done` es 0
  para revisión lista, 1 para bloqueada y 2 para errores de evidencia o
  estado. Presentar el borrador y el SHA al revisor humano.
  [Política de aprobación](../../knowledge/quality-approval.md)

La prueba SSH utiliza el acceso preexistente al host y un lector
`sudo -n` del servicio, SQLite y el journal. La copia remota se conserva
como evidencia y sigue la política de retención del operador. El resultado
de la auditoría devuelve identificadores y hashes.
[Contrato del coordinador](../../knowledge/contracts/vps-baseline-automation.md) ·
[Contrato SSH](../../knowledge/contracts/vps-baseline-ssh-proof.md)
