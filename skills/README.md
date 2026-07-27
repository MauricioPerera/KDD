# Skills versionadas

Copias versionadas de las skills operativas que implementan la metodología KDD.

- `delegar-ollama/SKILL.md` — capa BASE: mecánica de lanzamiento headless vía `ollama launch claude`, agnóstica al modelo (probe de vida, `< /dev/null`, MCP mínimo, anti-cuelgue, sondas, cuota, recuperación). No sabe de CCDD ni decide tareas.
- `delegar-pool/SKILL.md` — capa BASE: mecánica de lanzamiento headless vía `pool exec` (poolside.ai), análoga a `delegar-ollama` pero para `pool` (`--unsafe-auto-allow` obligatorio, logs/trayectorias reales para auditar, el riesgo real es el razonamiento previo al rechazo de aprobación, no un cuelgue). No sabe de CCDD ni decide tareas.
- `delegar-pool-ccdd/SKILL.md` — delegación de UNA función/tarea a `pool` con gate CCDD; usa `delegar-pool` para la mecánica y `kdd-okf-ccdd-hybrid` para el contrato (análoga a `delegar-glm-ccdd` pero para `pool` en vez de GLM/Ollama).
- `delegar-glm-ccdd/SKILL.md` — delegación de UNA función/tarea a GLM con gate CCDD; usa `delegar-ollama` para la mecánica y `kdd-okf-ccdd-hybrid` para el contrato (la capa de detalle debajo de pm-glm-ccdd).
- `pm-glm-ccdd/SKILL.md` — Claude como PM/orquestador con devs GLM efímeros y gate CCDD (capa de PROYECTO: varias tareas, varios devs, integración; por encima de las dos anteriores).
- `pm-native-ccdd/SKILL.md` — variante NATIVA del PM: sub-agentes de la app de Claude (tool Agent, Haiku) en vez de GLM/Ollama; misma metodología, cambia solo el mecanismo de delegación.
- `pkb-agent-first/SKILL.md` — sistema PocketBase Agent-First (repo D:\Repo\pkb): dev-tasks delegadas a sub-agentes GLM disparadas por webhook y verificadas contra tests definidos de antemano; planes encadenados (depends_on), deploy y notificación.
- `pm-sonnet-opus-haiku/SKILL.md` — variante 100% nativa sin GLM/Ollama: PM=Sonnet 5, implementador=subagent Opus 4.8 (fijo, caro), QA=subagent Haiku 4.5 read-only (o el gate CCDD/KDD si el repo lo trae), verificador adversarial opcional (2-3 Haiku en paralelo, voto por mayoría). NO reemplaza a `pm-native-ccdd`: mismo gate como verificador, tiering de implementador distinto (acá Opus fijo; `pm-native-ccdd` usa Haiku barato con escalado).

Este directorio versiona SOLO la familia de delegación KDD/CCDD. El respaldo
completo de todas las skills operativas (incluidas las no-KDD, como `wasam`)
vive en [MauricioPerera/claude-skills](https://github.com/MauricioPerera/claude-skills).

## Relación con la copia operativa

La copia **operativa** (la que Claude carga en cada sesión) vive en
`~/.claude/skills/<skill>/SKILL.md`, fuera de git. Este directorio existe para
darle historial y respaldo, no para editarla acá.

Regla de sincronía (la misma doctrina que la skill declara): ante una mejora de
proceso, se actualiza PRIMERO la metodología en `knowledge/`, DESPUÉS se refleja
en la copia operativa local, y por último se copia acá **byte-idéntica**
(`cp` + `diff` vacío). Si esta copia y la local divergen, la local manda y esta
se re-copia.
