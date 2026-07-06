---
name: delegar-glm-ccdd
description: Cómo delegar la IMPLEMENTACIÓN de código a glm-5.2:cloud (vía `ollama launch claude`) mientras yo orquesto con el CCDD gate. Úsala cuando el usuario pida implementar, arreglar, extender o refactorizar código y quiera que el trabajo lo haga glm — o cuando pida explícitamente "delega a glm" / "usa el ccdd gate con glm". Aplica a CUALQUIER repo de trabajo (el del cwd actual o el que el usuario indique). Mi rol es interpretar y verificar; glm escribe el código de producción. Incluye el comando exacto y las lecciones aprendidas para que no se cuelgue ni devuelva vacío.
---

# Delegar a glm-5.2:cloud con CCDD gate

Patrón de trabajo genérico, **independiente del repo**. El repo de trabajo es el **directorio actual** (cwd) salvo que el usuario indique otro: sustituye `<REPO>` por esa ruta en los prompts.

## Rol (inviolable)
- **Yo (instancia anfitriona) NO implemento.** Interpreto el pedido del usuario, lo traduzco a una instrucción clara, lo **delego a glm-5.2:cloud**, y **verifico el resultado yo mismo**.
- **glm-5.2:cloud es el implementador.** Escribe TODO el código de producción usando el CCDD gate. Si yo escribo el código, invalido el experimento (el gate mide al modelo pequeño).
- No cuestionar de más ni re-validar enfoque salvo que el usuario lo pida. Recibir → traducir → un solo comando de delegación → reportar → pedir la siguiente decisión.

## Comando de delegación (memorízalo)
```bash
ollama launch claude --model glm-5.2:cloud -y -- --strict-mcp-config --mcp-config '{"mcpServers":{}}' -p "INSTRUCCION..." --dangerously-skip-permissions < /dev/null
```
- **`< /dev/null` es OBLIGATORIO.** Sin él, claude espera stdin y la tarea sale **vacía** (exit 0, sin trabajo hecho).
- **`--strict-mcp-config --mcp-config ...` es OBLIGATORIO** (verificado 2026-07-03/04): sin él, cada
  delegación hereda y levanta TODA la flota MCP global (n8n, github, chrome...) — decenas de procesos
  que ya colgaron la app anfitriona dos veces. Si la tarea NO usa el gate → `'{"mcpServers":{}}'`;
  si lo usa → un JSON con SOLO la entrada `ccdd-complexity` copiada de `~/.claude.json`.
- `--dangerously-skip-permissions` para que glm pueda editar/correr sin prompts. Alternativa más
  contenida (verificada 2026-07-04, repos reales): `--permission-mode acceptEdits --allowedTools
  "Bash,mcp__ccdd-complexity__*"` — habilita exactamente editar + correr comandos/gate sin bypass total.
- glm hereda el **cwd** desde el que lanzas el comando (haz `cd <REPO>` antes, o pásalo en la instrucción). Trabaja sobre el repo del usuario, sea cual sea.
- Para tareas largas: corre el comando con `run_in_background: true` y lee el `output-file` al recibir la notificación de fin.
- Probe de vida si hace rato no se usa: `ollama launch claude --model glm-5.2:cloud -- -p "Responde: VIVO" --permission-mode plan < /dev/null` → debe imprimir `VIVO`. `glm-5.2:cloud` requiere `ollama signin` (modelo cloud). Si no está, dilo tajante y ofrece alternativa.

## Lecciones (NO repetir errores)
1. **Prompts pequeños y enfocados.** Un prompt monolítico hace que glm devuelva **vacío** (exit 0, sin cambios). Si la tarea es grande, **pártela en chunks** (A/B/C), cada uno terminando con una respuesta CORTA tipo `'CHUNK A LISTO' + lista`. Verifica entre chunks con `git status`.
2. **Reporte a archivo.** Pide a glm que escriba el reporte final en un `.md` del repo ADEMÁS de imprimirlo. Si el stdout vuelve vacío, lees el archivo. Confirma con `git status` / archivos recientes que sí trabajó.
3. **Anti-cuelgue.** Prohíbe servidores en foreground: arrancar un server bloqueante (p.ej. `npm start`/`node server.js` a secas) **bloquea para siempre** y quema el wall-clock sin terminar. Regla a incluir: "ningún proceso en foreground; si necesitas un server, arráncalo en BACKGROUND y mátalo al final; usa flags/targets que se autocierren; todo proceso debe terminar solo".
4. **CCDD gate** (si el repo lo usa / hay MCP `ccdd-complexity`). Para cada función de lógica core: task-contract con las **7 secciones** (`## Intent`, `## Interface`, `## Invariants`, `## Examples`, `## Do / Don't`, `## Tests`, `## Constraints`) + cláusula `PARAR y reportar si...` dentro de `## Constraints`, property-tests congelados (oráculo independiente), validar con `lint_task_contract` y correr `run_integration_gate` hasta PASS, dentro de budget (cyclomatic/nesting/params/lines). Descomponer funciones grandes en sub-funciones gateadas. Si el repo no usa CCDD, pide tests + criterio de verde equivalentes.
5. **`run_integration_gate`, no `run_ephemeral_agent`.** El ephemeral corre en un sandbox tempdir que **vacía el directorio** → puede destruir archivos en disco. Usar el gate de integración sobre archivos reales.
6. **Verificar yo mismo SIEMPRE.** No me fío del reporte de glm. Tras cada delegación corro la verificación real del repo (su suite de tests, linters, build, o pruebas en vivo). Ojo: los tests unitarios pueden pasar y el flujo end-to-end estar roto; las pruebas e2e suelen necesitar un server corriendo.
7. **El gate lo puedo correr YO al verificar** (verificado 2026-07-04): si tengo el MCP `ccdd-complexity`
   en MI sesión, es más barato dar a glm MCP vacío + hecho verificable por suite/comandos, y correr yo
   `lint_task_contract` sobre el entregable final. Gate-en-glm solo cuando glm deba ITERAR contra el
   gate (funciones nuevas complejas), no para validar un artefacto terminado.
8. **Tareas de docs/texto → hecho por greps de presencia Y ausencia** (verificado 2026-07-04):
   `grep -n "<clave>" <files>` (hit obligatorio) + `grep -rn "<prohibido>" <files> || echo SIN_MENCIONES`
   + suite verde. glm pega la salida real; yo re-corro los mismos greps. Sin esto no hay veredicto.
9. **glm copia el REGISTRO del prompt, no el del repo** (verificado 2026-07-04): prompt en voseo → docs
   en voseo aunque el repo use tuteo y el prompt pida "tono consistente". Si el registro importa,
   ejemplo explícito ("tuteo: 'explora', no 'explorá'") o asumir el retoque al integrar.
10. **Log vacío ≠ colgado** (verificado 2026-07-04): en headless `-p` el log se escribe AL FINAL. Para
    saber si avanza: mtimes de los entregables esperados y de `__pycache__/` (mtime reciente = está
    corriendo tests). Recién si nada cambia en disco por minutos, tratarlo como colgado.
11. **Error transitorio `Could not verify your plan`** = el lanzamiento muere al instante (exit 1, log
    de 1 línea). No es culpa del prompt: relanzar con delay (~100 s). Detalle y mitigación por batch en
    la skill `pm-glm-ccdd`.

## Plantilla de prompt para glm
```
[CONTEXTO: qué hay hecho y dónde]
TAREA: [una rebanada acotada, no todo]
1. [pasos concretos]
2. [Si aplica] CCDD GATE: toda función core no trivial -> task-contract (7 secciones + 'PARAR y reportar si...') + property-tests, lint_task_contract + run_integration_gate hasta PASS, dentro de budget. Descompón en sub-funciones gateadas.
3. Verificación: [suite de tests verde / build / prueba en vivo con server en background].
REGLAS: ningún proceso foreground; procesos que terminen solos; no loguear secretos.
ENTREGA: escribe reporte en X-REPORT.md. Al terminar responde SOLO: 'LISTO' + [resumen corto verificable].
Trabaja en <REPO>. No rompas lo existente.
```

## Flujo por turno
1. Interpretar el pedido → instrucción clara y acotada. Determinar `<REPO>` (cwd o el que diga el usuario).
2. (Opcional) probe de vida de glm.
3. Delegar con el comando + `< /dev/null` (+ background si es largo); `cd <REPO>` primero.
4. Al terminar: leer output/`.md`, **confirmar con `git status`** que sí hubo cambios.
5. **Verificar yo mismo** (tests/build/pruebas en vivo del repo).
6. Reportar al usuario tajante (qué se hizo, verde/rojo, notas honestas) y pedir la siguiente decisión.
