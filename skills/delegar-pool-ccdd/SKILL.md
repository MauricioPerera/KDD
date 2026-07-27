---
name: delegar-pool-ccdd
description: Delega la IMPLEMENTACIÓN de UNA función/tarea puntual a un dev efímero vía `pool exec` (poolside.ai), verificada por el CCDD gate. Úsala cuando el usuario pida implementar/arreglar/extender algo puntual y quiera que lo haga `pool` — "delega a pool" / "usa el ccdd gate con pool". Para proyectos con VARIAS tareas y devs en paralelo, adaptá `pm-glm-ccdd` con `pool` como mecanismo en vez de esta (esta es la capa de UNA tarea suelta).
---

# Delegar UNA tarea a `pool exec` con CCDD gate

Capa mínima sobre [`delegar-pool`](../delegar-pool/SKILL.md) (mecánica de
lanzamiento/logs/anti-riesgo, agnóstica a la tarea) + el contrato CCDD
definido en
[`kdd-okf-ccdd-hybrid`](https://github.com/MauricioPerera/KDD/blob/main/.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md)
(7 secciones + frontmatter, si el repo usa KDD). Esta skill NO reescribe esos
dos — solo fija el flujo de delegar UNA tarea suelta a `pool` y agrega lo
verificado en vivo (2026-07-26, Python y Rust) que es específico de `pool`
como implementador.

## Rol (inviolable)
- **Yo NO implemento.** Interpreto el pedido, lo traduzco a un TASK-CONTRACT
  con tests congelados, delego a `pool exec --unsafe-auto-allow` vía
  [`delegar-pool`](../delegar-pool/SKILL.md), y **verifico el resultado yo
  mismo** (nunca me fío del exit code ni del resumen final de `pool`).
- Recibir → contrato + tests → un solo comando de delegación → verificar →
  reportar → pedir la siguiente decisión.

## Cómo delegar
1. Redactar el TASK-CONTRACT (formato `kdd-okf-ccdd-hybrid`: front-matter +
   7 secciones) y los property-tests congelados en el mismo turno, ANTES de
   invocar `pool`.
2. Validar el contrato con `lint_task_contract(contract_text, test_code)`
   hasta `{"ok": true}` — corregir yo el contrato, no delegarle eso a `pool`.
3. Hashear (`sha256`) el archivo de tests congelado y guardarlo. Crear en
   disco el target (stub vacío o implementación previa con bug, según el
   caso) y el archivo de tests ANTES de invocar `pool`.
4. Delegar con el comando base de [`delegar-pool`](../delegar-pool/SKILL.md)
   (`--unsafe-auto-allow` SIEMPRE, `-d <dir>` apuntando exactamente al
   directorio de la tarea — doble-chequear esa ruta, un `-d` mal apuntado
   escribe en el lugar equivocado sin aviso). El prompt le pide correr el
   `test_command` primero (no asumir que pasa) y iterar SOLO sobre el target
   si falla.
5. Verificar yo mismo: re-hashear los tests (deben ser idénticos), correr el
   `test_command` de forma independiente, y si el repo tiene gate CCDD real
   correr `measure_complexity` + `check_signature` sobre el código final
   (Python vía AST nativo, Rust/otros vía tree-sitter con `language: <lang>`
   en la llamada).

## Verificado en vivo con `pool` (no con GLM — no asumas que aplica igual)
- **Caso de éxito al primer intento y caso de iteración tras fallo, ambos
  confirmados en Python Y Rust** con el mismo contrato KDD (budget, forbids,
  firma, tests congelados). En los 4 casos: no tocó los tests, no tocó
  código fuera del target, no agregó dependencias, respetó `forbids`
  (`unsafe` en Rust incluido).
- **NO le des las tools del gate CCDD a `pool`** (aunque `pool mcp add`
  lo permita) — la verificación es del orquestador, no autoevaluación del
  implementador. Ver doctrina completa en
  [`delegar-pool`](../delegar-pool/SKILL.md#mcp-no-dárselo-al-implementador).
- **El riesgo de costo es tiempo de razonamiento, no cuelgue** — ver
  [`delegar-pool`](../delegar-pool/SKILL.md#el-riesgo-real-no-es-que-se-cuelgue-esperando-aprobación).
  Con `--unsafe-auto-allow` puesto desde el arranque este riesgo no aplicó en
  ninguna de las 4 corridas verificadas (todas terminaron en el primer o
  segundo ciclo de tool calls).
- **Tareas que comparten el mismo archivo target → lanzar en SECUENCIA**, no
  en paralelo (verificado necesario con dos funciones en el mismo
  `src/lib.rs`).
- **No verificado todavía** (no asumir sin probarlo): copia de registro
  (tuteo/voseo) del prompt como con GLM, comportamiento con tareas
  multi-archivo, ni compatibilidad con el modo standalone `--api-url`
  apuntando a un modelo propio/local en vez del backend cloud de Poolside.

## Plantilla de prompt (una tarea)
```
Estás en un directorio de trabajo con un TASK-CONTRACT en <task.md> (formato
front-matter YAML + Markdown), [un stub vacío | una implementación previa que
puede tener bugs] en <target> y un archivo de tests congelado <tests>.

1. Leé <task.md> completo antes de tocar nada.
2. Corré primero: <test_command> (no asumas que pasa).
3. Si falla, iterá SOLO sobre <target> (nunca sobre los tests) hasta que
   pasen, respetando firma y budget del contrato.
4. NO modifiques <tests> ni <task.md> bajo ninguna circunstancia.
5. NO agregues dependencias fuera de deps_allowed.
6. Si no podés cumplir el contrato sin violar la interfaz, PARÁ y explicá
   por qué en vez de forzar un workaround.
7. No hagas nada fuera de este directorio.
```

## Flujo por turno
1. Interpretar el pedido → contrato + tests congelados (pasos 1-3 arriba).
2. Delegar con `pool exec --unsafe-auto-allow -d <dir> -f <prompt.txt> -o
   json` (+ `run_in_background: true` si puede tardar).
3. Al terminar: leer el log NLJSON, **confirmar con hash/diff** que tests y
   contrato quedaron intactos.
4. **Verificar yo mismo** (test_command independiente + gate CCDD si aplica).
5. Reportar al usuario tajante (qué se hizo, verde/rojo, notas honestas) y
   pedir la siguiente decisión.
