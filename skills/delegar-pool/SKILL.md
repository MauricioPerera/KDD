---
name: delegar-pool
description: Cómo lanzar y verificar un dev efímero vía `pool exec` (poolside.ai) en modo headless, agnóstico a la tarea. Cubre el flag no documentado `--unsafe-auto-allow` (obligatorio en no-interactivo), formato de log NLJSON, dónde viven los logs/trayectorias reales para auditar, el riesgo real (bloques de razonamiento largos antes de fallar, no un cuelgue de aprobación) y la doctrina de verificación independiente. Úsala como capa base de mecánica de delegación, análoga a `delegar-ollama` pero para `pool` en vez de Ollama/GLM.
---

# Delegar a un dev efímero vía `pool exec` (headless) — mecánica agnóstica a la tarea

Patrón de lanzamiento reutilizable para `pool` (poolside.ai), análogo en rol a
[`delegar-ollama`](../delegar-ollama/SKILL.md) pero para el CLI `pool` en vez de
`ollama launch claude`. Esta skill NO sabe de CCDD ni de qué tarea estás
delegando — solo de cómo invocar `pool exec` sin perder tiempo ni confiar
ciegamente en su reporte. Verificado en vivo 2026-07-26 con contratos KDD
reales en Python y Rust.

## Rol (misma doctrina que `delegar-glm-ccdd`)
`pool` es un implementador efímero, no un par de confianza. Yo (el
orquestador) redacto el contrato + tests congelados, delego la implementación,
y **verifico el resultado yo mismo** — nunca confío en el exit code ni en el
resumen que `pool` imprime al final.

## Comando base
```bash
pool exec --unsafe-auto-allow -d <REPO_O_DIR> -f <prompt.txt> -o json > <log.txt> 2>&1
```
- **`--unsafe-auto-allow` OBLIGATORIO en no-interactivo.** Sin él, la primera
  acción que requiera aprobación (leer O escribir, no importa cuál) falla con
  `"approval required in non-interactive mode: encountered unexpected error"`
  y exit code 1. No existe modo headless sin este flag — no está en el
  README, pero sí en `pool exec --help`.
- Prompt en ARCHIVO (`-f`), nunca inline (`-p`) para instrucciones
  multilínea — mismo motivo que en `delegar-ollama` (comillas/escaping).
- `-o json` da NLJSON estructurado (`reasoning`/`thought`/`toolCall`/
  `toolCallResult`/`assistantMessage`) — más auditable que texto plano, no
  hace falta parsear logs crudos.
- `-d <dir>` fija el cwd de la sesión; no asumas que hereda el cwd del shell.
- Exit codes: `0` = tarea completa, `4` = fallo explícito reportado por
  `pool`, cualquier otro = error inesperado (incluida la falta de
  `--unsafe-auto-allow`).

## El riesgo real NO es que se cuelgue esperando aprobación
Verificado dos veces (lectura primero, escritura primero) SIN el flag: el
rechazo de aprobación es casi instantáneo (segundos), con error explícito, no
un cuelgue. **El riesgo real es el tiempo de razonamiento ANTES de llegar a
esa acción.** Trayectoria real auditada
(`%LOCALAPPDATA%\poolside\trajectories\trajectory-standalone_*.ndjson`):
27m30s de corrida total, de los cuales ~27 minutos fueron tres bloques de
`thought` consecutivos sin ninguna tool call, y el rechazo de aprobación en sí
tardó 24ms. Conclusión: lanzá SIEMPRE con `--unsafe-auto-allow` desde el
arranque en un directorio desechable — no hay forma de "probar primero sin el
flag" barato, porque el costo no está en el rechazo sino en el razonamiento
previo, que podés terminar pagando igual.

## Logs y trayectorias reales (para auditar sin re-lanzar)
`pool config` imprime las rutas reales de esta instalación:
- `log directory`: `%LOCALAPPDATA%\poolside\logs\pool-<run_id>.log` — texto
  plano con timestamps por evento (`pool CLI started`, `trajectory summary`
  con `duration` y `trajectory_error`, `pool CLI execution complete`). Es lo
  primero que hay que mirar para saber cuánto tardó y por qué terminó.
- `trajectory directory`:
  `%LOCALAPPDATA%\poolside\trajectories\trajectory-standalone_<run_id>.ndjson`
  — un evento por línea (`session.start`, `thought.start/end`,
  `tool_call.*`, `tool_call.approval.request`, `session.error`,
  `session.exit`) con timestamp de alta precisión. Restar `thought.end -
  thought.start` da la duración real de cada bloque de razonamiento sin tener
  que re-lanzar nada.
- Estas rutas existen SIEMPRE, aunque no hayas pedido `-o json` — sirven para
  reconstruir corridas pasadas (propias o del usuario) sin depender de que te
  las pasen.

## Verificación independiente (nunca confiar en el reporte de `pool`)
Igual doctrina que `delegar-glm-ccdd`:
1. Hashear el archivo de tests congelado ANTES de delegar; comparar después
   — debe ser idéntico.
2. Correr el `test_command` del contrato YO MISMO, no leer el resumen de
   `pool`.
3. Si el repo usa el gate CCDD (`ccdd-complexity`), correr `measure_complexity`
   y `check_signature` sobre el código final — soporta Python (AST nativo) y
   Rust/otros lenguajes vía tree-sitter si la gramática está instalada
   (`language: rust` en el contrato o extensión del archivo).
4. Confirmar que no tocó nada fuera de `touch_only`/`target` (diff o listado
   del directorio).

## Colisión de archivos en tareas paralelas
Si dos contratos apuntan al MISMO archivo target (p.ej. dos funciones en el
mismo `src/lib.rs`), lanzá los `pool exec` en SECUENCIA, no en paralelo —
verificado necesario, sin locking propio entre invocaciones.

## MCP (no dárselo al implementador)
`pool mcp add/list/get/remove` existe — `pool` puede conectarse a servidores
MCP igual que cualquier cliente ACP. Por la misma doctrina de
`delegar-glm-ccdd`: NO le des las tools del gate CCDD al dev efímero. El
veredicto lo corre el orquestador de forma independiente, no el
autoevaluador del implementador.

## Fricción menor de Windows (no bloqueante)
El tool `shell` interno de `pool` a veces intenta heredocs estilo POSIX
(`python << 'EOF'`) que fallan en el shell de Windows; reintenta solo con
otra sintaxis (`python -c "..."`). Ruido en el trace, no afecta el resultado
ni requiere intervención.
