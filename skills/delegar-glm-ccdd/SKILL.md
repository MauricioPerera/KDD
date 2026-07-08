---
name: delegar-glm-ccdd
description: Delega la IMPLEMENTACIÓN de UNA función/tarea puntual a glm-5.2:cloud, verificada por el CCDD gate. Úsala cuando el usuario pida implementar/arreglar/extender algo puntual y quiera que lo haga GLM — "delega a glm" / "usa el ccdd gate con glm". Para proyectos con VARIAS tareas y devs en paralelo, usá `pm-glm-ccdd` en su lugar (esta es la capa de UNA tarea suelta, no la de orquestación de proyecto).
---

# Delegar UNA tarea a glm-5.2:cloud con CCDD gate

Capa mínima sobre [`delegar-ollama`](../delegar-ollama/SKILL.md) (mecánica de lanzamiento/probe/anti-cuelgue, agnóstica al modelo) + el contrato CCDD definido en [`kdd-okf-ccdd-hybrid`](https://github.com/MauricioPerera/KDD/blob/main/.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md) (7 secciones + frontmatter, si el repo usa KDD). Esta skill NO reescribe esos dos — solo fija `model=glm-5.2:cloud` y agrega lo específico de delegar UNA tarea suelta.

## Rol (inviolable)
- **Yo NO implemento.** Interpreto el pedido, lo traduzco a una instrucción clara, delego a `glm-5.2:cloud` vía `delegar-ollama`, y **verifico el resultado yo mismo** (nunca me fío del reporte de glm).
- Recibir → traducir → un solo comando de delegación → reportar → pedir la siguiente decisión. No cuestionar de más ni re-validar enfoque salvo que el usuario lo pida.

## Cómo delegar
Usá el comando base y el probe de [`delegar-ollama`](../delegar-ollama/SKILL.md) con `<MODEL>=glm-5.2:cloud`. Si la tarea usa CCDD: contrato con las 7 secciones (ver [`kdd-okf-ccdd-hybrid`](https://github.com/MauricioPerera/KDD/blob/main/.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md)) + property-tests congelados, validar con `lint_task_contract` y correr `run_integration_gate` hasta PASS **sobre los archivos REALES del repo**. **Nunca `run_ephemeral_agent` apuntando al repo real:** corre en un sandbox tempdir que VACÍA el directorio y puede destruir archivos.

## Lecciones específicas de GLM (no de la mecánica de Ollama, ver `delegar-ollama` para esa)
- **GLM copia el REGISTRO del prompt, no el del repo** (verificado 2026-07-04): un prompt en voseo produjo docs en voseo dentro de un repo en tuteo, aunque el prompt pedía "tono consistente con el README". Si el registro importa, decilo EXPLÍCITO con ejemplo ("tuteo: 'explora', no 'explorá'") o asumí el retoque al integrar.
- **El gate lo puedo correr YO al verificar** (verificado 2026-07-04): si tengo el MCP `ccdd-complexity` en MI sesión, es más barato dar a GLM MCP vacío + hecho verificable por suite/comandos, y correr yo `lint_task_contract` sobre el entregable final. Gate-en-GLM solo cuando GLM deba ITERAR contra el gate (funciones nuevas complejas), no para validar un artefacto terminado.
- **Tareas de docs/texto → hecho por greps de presencia Y ausencia** (verificado 2026-07-04): `grep -n "<clave>" <files>` (hit obligatorio) + `grep -rn "<prohibido>" <files> || echo SIN_MENCIONES` + suite verde. GLM pega la salida real; yo re-corro los mismos greps.

## Plantilla de prompt (una tarea)
```
[CONTEXTO: qué hay hecho y dónde]
TAREA: [una rebanada acotada, no todo]
1. [pasos concretos]
2. [Si aplica] CCDD GATE: ver kdd-okf-ccdd-hybrid — contrato (7 secciones + 'PARAR y reportar si...') + property-tests, lint_task_contract + run_integration_gate hasta PASS, dentro de budget.
3. Verificación: [suite de tests verde / build / prueba en vivo con server en background].
REGLAS: ningún proceso foreground; procesos que terminen solos; no loguear secretos.
ENTREGA: escribe reporte en X-REPORT.md. Al terminar responde SOLO: 'LISTO' + [resumen corto verificable].
Trabaja en <REPO>. No rompas lo existente.
```

## Flujo por turno
1. Interpretar el pedido → instrucción clara y acotada. Determinar `<REPO>` (cwd o el que diga el usuario).
2. (Opcional) probe de vida — ver [`delegar-ollama`](../delegar-ollama/SKILL.md).
3. Delegar con el comando de `delegar-ollama` (+ background si es largo); `cd <REPO>` primero.
4. Al terminar: leer output/`.md`, **confirmar con `git status`** que sí hubo cambios.
5. **Verificar yo mismo** (tests/build/pruebas en vivo del repo).
6. Reportar al usuario tajante (qué se hizo, verde/rojo, notas honestas) y pedir la siguiente decisión.
