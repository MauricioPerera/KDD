# Piloto KDD con MCP Events

El orquestador local delega una tarea del [validador de mensajes de commit](../../knowledge/contracts/commit-message-length-config.md)
a ALPHA y pide una revisión Goldfish de solo lectura a DELTA. Ambos encargos
comparten un hilo. Cada agente recibe un encargo autocontenido. El oráculo
congelado y los comandos se quedan en el worktree.

El receptor del VPS comprueba la firma del webhook y guarda el evento. El
orquestador sigue por SSH el journal de ese receptor de confianza. Lee la
respuesta una vez, después de observar `task.replied` con el par, el ID de la
tarea y el hilo esperados. Guarda el ID de cada evento, las huellas de los
insumos, la propuesta, el dictamen y la salida real de los comandos. La
revisión de DELTA se conserva como evidencia separada del veredicto de los
oráculos. Los hallazgos requieren revisión antes de cerrar el encargo.

La [evaluación de impacto en KDD](../../docs/reports/KDD-MCP-EVENTS-IMPACTO.md)
documenta la comparación con invocación directa y el costo de coordinación.

## Ejecutar

Usar un worktree limpio de la rama del piloto en el commit de la infraestructura,
previo al candidato que modifica el validador. Se requiere Node.js 24, Python,
Git y acceso SSH al VPS con permiso para seguir el journal del receptor. En la
federación, el propietario que envía las tareas debe tener ALPHA y DELTA como
pares. Las suscripciones del receptor y el runner local de DELTA deben estar
activos. Cargar `KDD_MCP_OWNER_TOKEN` en el entorno privado del proceso.
Para modelos locales lentos, ajustar `inferenceTimeoutMs` en el runner.
El plazo de respuesta del orquestador se puede fijar con
`KDD_MCP_REPLY_TIMEOUT_MS`. Conservar margen para entregar el webhook.

```text
node examples/mcp-events-kdd/run.mjs HOST https://WORKER/agent/mcp OWNER_ID ABSOLUTE_EVIDENCE_PATH
```

La ruta de evidencia debe ser nueva y estar fuera del worktree. El candidato
queda como diff para inspección y el propio orquestador compara su perímetro
con el contrato. El piloto admite únicamente una expresión pura y un mensaje
de diagnóstico para este punto de inserción. La promoción del baseline es una
operación separada.

## Reanudar

Usar los mismos argumentos y el mismo worktree, añadiendo `--resume`.
El SQLite junto al informe es el estado de la ejecución. El JSON permite
inspeccionar una copia del último punto guardado. Conservar ambos archivos
SQLite y sus archivos auxiliares durante el reinicio.

El orquestador recupera el hilo, los IDs de tareas, las respuestas y el
cursor del journal. Una respuesta confirmada se reutiliza tras la reentrega
del mismo evento. Si se perdió un recibo de envío, se puede reintentar con el
mismo ID y el mismo mensaje. Las comprobaciones con salida guardada se
reutilizan. Una comprobación interrumpida antes de guardar su salida puede
volver a ejecutarse. Conservar el journal del receptor durante la interrupción
para poder recuperar las observaciones pendientes.

Ejecutar `node --test examples/mcp-events-kdd/recovery.test.mjs` para los
controles locales. El [contrato de recuperación](../../knowledge/contracts/kdd-mcp-events-recovery.md)
describe las condiciones del piloto.
