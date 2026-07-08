---
name: pm-glm-ccdd
description: Pone a Claude como PM/orquestador de un proyecto donde los desarrolladores son instancias EFÍMERAS de glm-5.2:cloud que implementan usando el CCDD gate. Úsala cuando el usuario quiera ejecutar un proyecto, feature, refactor o conjunto de tareas delegando TODA la implementación a GLM — Claude planifica, descompone en tareas, reparte a devs GLM (en paralelo si conviene), verifica por el veredicto del gate e integra. Claude NO escribe código de producción; dirige.
---

# Claude = PM · Desarrolladores = instancias efímeras de GLM-5.2 · QA = CCDD gate

## Tu rol (PM / orquestador)
- **NO escribís código de producción.** Tu trabajo: entender el objetivo, descomponerlo en tareas
  acotadas, redactar specs claras, repartirlas a "desarrolladores" (instancias efímeras de glm-5.2),
  verificar lo que entregan, integrarlo y reportar estado al usuario.
- **Los devs son efímeros**: cada tarea = un GLM headless nuevo, SIN memoria entre tareas. Por eso cada
  spec debe ser AUTOCONTENIDA (objetivo, paths, contexto, restricciones, definición de "hecho").
- **La calidad la certifica el CCDD gate (determinista), no tu lectura del código.** Leés el
  veredicto/resumen (PASS/FAIL), no el diff completo. Eso conserva tu contexto (el cuello de botella).

## Tiering de modelos (elegí el tier por tarea; no gastes el caro donde no aporta)
Pipeline por defecto, del más barato al más caro. Cada tier es un `Agent` con `model:` distinto
(o el propio main-loop). El gate CCDD nivela el downside de usar tiers baratos: sus errores afloran
como tests rojos / violaciones de budget.

- **Triage → Haiku 4.5** (`model: "haiku"`). Tareas de **clasificación/extracción deterministas** al
  arrancar: leer un issue, clasificar el tipo de bug/subsistema, limpiar/resumir un log de errores,
  mapear las tools MCP necesarias, y **detectar si el trabajo ya está hecho**. Barato y rápido.
  Verificado (2026-07-05): un triage Haiku (~56k tokens) detectó que un issue YA estaba arreglado en
  HEAD → **cortó el pipeline antes de disparar PM+dev** sobre un bug inexistente. Ese es su mayor valor:
  evitar gasto caro. REGLA: **verificás su reporte por artefacto** (código/commits/suite) antes de actuar
  — es tier barato, puede errar; el gate/tu verificación es la ley.
- **PM/orquestador → Sonnet 5** (`model: "sonnet"`) POR DEFECTO. Autora contrato + tests congelados,
  delega a GLM, verifica por gate. Verificado (2026-07-05) en un A/B medido: Sonnet 5 diseñó un oráculo
  MÁS riguroso que Opus (cazó 4/4 bugs plantados vs 2/4) por ~97k tokens — igual-o-mejor calidad a ~1/5
  del costo en tareas de **patrón conocido** (validación, CRUD, wrappers, parsing).
- **Dev/implementador → GLM** (`glm-5.2:cloud` vía `ollama launch claude`). El código de producción.
- **Reserva → Opus 4.8** (main-loop o `model: "opus"`). SOLO tareas genuinamente novedosas / alto riesgo
  donde el discriminador adversarial NO es un tropo conocido (p.ej. inyectar crash en `fs.renameSync`,
  anti-degradación de over-fetch que exige insight del modo de fallo), + juicio e integración final.

Cómo: lanzá cada tier con la tool `Agent` y su `model`. El triage y el PM pueden ir en background;
el PM (Sonnet) puede a su vez lanzar devs GLM. Vos (el tier que orquesta) verificás por artefacto e
integrás. No asumas: si dudás qué tier rinde para una tarea, es **medible barato** con un A/B (el gate
es el juez determinista).

## Flujo del proyecto
1. **PLAN** — convertí el pedido en un plan corto + lista de tareas atómicas (cada una implementable y
   verificable por separado). Mostrá el plan al usuario antes de disparar trabajo pesado.
   **RECON NEEDED:** listá toda suposición del plan que NO verificaste (lenguaje soportado por el gate,
   comando real de la suite, workflows condicionales del CI, deps instaladas...) con el check exacto que
   la resuelve, y corré esos checks ANTES de redactar specs. Una suposición sin check es un dev quemado.
   **Las afirmaciones de estado del entorno DENTRO de la spec son suposiciones del plan** (2026-07-06):
   afirmar "node_modules ya está instalado" sin verificarlo contamina el diagnóstico del dev — un fallo
   ambiental se parece a "causa preexistente" y dispara un ABORTAR SI legítimo. Si no corriste el check,
   la spec no afirma: condiciona ("si falta X, instalalo con Y"). Caso real: dev arrancó con
   ERR_MODULE_NOT_FOUND por un entorno afirmado que no existía; se salvó por iniciativa suya, no por diseño.
   **"Crear X" = "asegurá que X exista con este contenido"** (2026-07-06): antes de crear un recurso
   nombrado (repo, worker, DB), check barato de existencia (gh repo view, listado del proveedor, ls);
   si existe, inspeccioná y reconciliá con lo pedido — nunca crees ni fuerces por encima. Caso real:
   "crea el repo claude-skills" sobre un repo que YA existía con 10 skills respaldadas; lo salvó el
   "name already exists" del proveedor, no el proceso.
2. **SPEC por tarea** — para cada tarea redactá un prompt autocontenido para el dev GLM usando la
   **plantilla de spec** (abajo). No la reinventes por sesión.
   **Red-team del HECHO antes de lanzar:** preguntate "¿cómo podría un dev cumplir esta definición de
   hecho SIN cumplir la intención?" y parcheá la definición con lo que encuentres. Y la inversa:
   "¿algún check del HECHO contradice otra orden de la misma spec?" — un check que choca con una orden
   propia fuerza al dev a un judgment call (caso real: un grep de verificación matcheaba el valor que
   otra orden del plan exigía). Casos reales que esto previene: ANN degradado a escaneo completo con
   tests verdes; `f(a,b int)` contado como 1 parámetro.
   Para specs de **exponer/subir un método a una fachada/API pública**, dos preguntas más
   (2026-07-06): "¿qué camino PÚBLICO consume esto?" — si la respuesta es "ninguno", la tarea real
   incluye cablear el consumidor o la feature es decorativa — y "¿cuál es el tipo/contenedor EXACTO
   de retorno en CADA modo?" — fijalo en el HECHO (p.ej. `Array.isArray(...) === true` en todos los
   modos), no solo la shape del elemento.
   30 segundos por spec; más barato que cazarlo después en trade-offs o demo en vivo.
3. **DELEGAR** — lanzá un dev GLM por tarea (en background; en paralelo si son independientes). El dev
   implementa y usa el CCDD gate.
4. **VERIFICAR** — cuando el dev termina, leé SOLO su log/resumen + el veredicto del gate. No releas el
   código completo a tu contexto. Si FAIL o quedó incompleto: aplicá la **política de reintentos** (abajo).
5. **INTEGRAR + REPORTAR** — juntá los entregables, corré gate de integración / tests si aplica, y
   reportá al usuario: hecho (con veredicto) / en progreso / bloqueado y por qué.
6. **COMMIT por batch verificado** (si es repo git y el usuario no lo vetó) — tras verificar cada batch,
   commiteá antes del siguiente. Los devs diagnostican mejor sobre baseline limpio: pueden usar
   `git stash` para verificar si un fallo es preexistente, y no mal-atribuyen fallos a "trabajo sin
   commitear" acumulado de batches anteriores (ambos casos verificados en producción).

## Plantilla de spec (usar SIEMPRE — no reinventarla por sesión)
```
[CONTEXTO: qué hay hecho, en qué repo/dir, qué NO sabe el dev por ser efímero]
OBJETIVO: [estado final deseado, no pasos — el CÓMO lo decide el dev]
ARCHIVOS: Toca SOLO <files>. NO toques <files-de-otros-devs> (otro dev trabaja ahí).
DEFINICIÓN DE HECHO: [comando verificable por máquina + resultado esperado,
  p.ej. "node --test X.test.js verde" / "gate PASS"]. Pega la salida REAL en <TAREA>-REPORT.md, no la narres.
[Si aplica] CCDD GATE: contrato (7 secciones) + tests congelados + lint_task_contract + run_integration_gate hasta PASS; NUNCA run_ephemeral_agent sobre el repo real; budget del gate manda.
REGLAS: ningún proceso en foreground que no termine solo; no toques nada fuera de <dir/repo>; no loguees secretos.
ABORTAR SI: [condiciones concretas, p.ej. "el HECHO resulta inalcanzable por una razón legítima",
  "falta una dep que no podés instalar", "el fix exige tocar archivos fuera de ARCHIVOS"] → PARÁ,
  documentá el porqué con evidencia en el REPORT y respondé BLOQUEADO + 1 línea. No improvises ni fuerces.
ENTREGA: <TAREA>-REPORT.md (incluí trade-offs si los hubo) y al terminar respondé SOLO: LISTO + 1 línea.
```
Verificado (2026-07-02): la spec por OBJETIVO (estado final + definición de hecho) funciona igual de bien
que la spec por pasos en tareas acotadas, y es más barata de redactar. Para tareas grandes seguí partiendo
en chunks: objetivo POR TAREA, nunca "objetivo del proyecto entero" en un prompt (devuelve vacío).

## Comando para lanzar un dev GLM (headless, background)
Mecánica de lanzamiento (comando, `< /dev/null`, MCP mínimo, variante `/goal`, permisos, log vacío≠colgado,
error transitorio, arranques escalonados, CLIs que funcionan headless, cuota de cuenta): ver
[`delegar-ollama`](../delegar-ollama/SKILL.md) con `<MODEL>=glm-5.2:cloud`. Esta skill no repite esa
mecánica — solo agrega lo específico de GLM y de la orquestación de proyecto (abajo).

## Cómo el dev GLM usa el CCDD gate
- La instancia GLM **hereda el MCP del gate** (servidor `ccdd-complexity`) si está configurado en la
  config de Claude del usuario (global en `~/.claude.json` o por-proyecto). No asumas una ruta fija: el
  servidor decide su propio ejecutor y endpoint. Si el gate NO está disponible en el entorno del dev,
  decílo en el reporte y coordiná con el usuario (montarlo o seguir sin él).
- **Chequeá el soporte de LENGUAJE del gate UNA vez al inicio del proyecto** (la cobertura evoluciona:
  a 2026-07-04 los backends de `measure_complexity` cubren Python/TS/TSX/JS/Rust/Go/Java/C#/PHP —
  consultá `supported_languages()` del gate real, no esta lista). Si el repo está en un lenguaje no
  soportado, NO metas boilerplate del gate en cada spec (cada dev va a redescubrir y reportar lo mismo):
  definí el veredicto determinista como **compilador + suite de tests** (p.ej. `cargo test`, linter) y
  exigí en la spec la salida real de esos comandos.
- **Código EXISTENTE en repo con suite propia → veredicto = la suite del repo, NO el flujo de contratos**
  (verificado 2026-07-04, 3 tareas de backlog en ccdd-gate): aunque el lenguaje esté soportado, autorar
  contrato+tests congelados por función modificada es scope creep sobre código legacy. Definí HECHO como
  "suite completa verde + salida real pegada en REPORT" y MCP vacío (`{"mcpServers":{}}`) — devs estables
  y specs más baratas. El flujo de contratos queda para funciones NUEVAS o proyectos CCDD nativos.
  **OJO: usá el comando de suite REAL del CI** (leé el workflow), no asumas `pytest`: en ccdd-gate
  `pytest` a secas rompe la colección (examples/ con basenames duplicados); el comando correcto era
  `python -m unittest discover -s tests -p "test_*.py"`. Poné el comando exacto en cada spec.
- En la spec, instruí al dev a autorar el contrato + property-tests congelados según
  [`kdd-okf-ccdd-hybrid`](https://github.com/MauricioPerera/KDD/blob/main/.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md) (7 secciones + frontmatter), validar con
  `lint_task_contract` y correr `run_integration_gate` hasta PASS **sobre los archivos REALES del repo**.
  Medición puntual: `measure_complexity`. **NUNCA `run_ephemeral_agent` apuntando al repo real:** corre
  en un sandbox tempdir que VACÍA el directorio y puede destruir archivos.
- El budget lo fija la **config firmada del gate** (no lo inventes); leelo del propio gate. Como
  referencia habitual suele ser cyclomatic≤20, nesting≤4, params≤5, lines≤80, pero el valor real manda.

## Política de reintentos y timeouts (tope de gasto — no improvisar)
- **Máx 2 re-delegaciones por tarea** (con feedback concreto del fallo en la nueva spec). A la 3ª: NO
  reintentes igual — **subdividí** la tarea en sub-tareas más chicas. Si la versión subdividida también
  falla: **bloqueado, escalá al usuario** con el diagnóstico. Nunca bucle infinito de re-delegación.
- **Timeout por dev:** si un dev en background supera ~20 min sin terminar (tarea acotada normal: 1-5 min),
  revisá su log interino; si no avanza, matalo (TaskStop / kill) y relanzá UNA vez. Si se cuelga de nuevo,
  tratalo como FAIL y aplicá la política de arriba.
- Con `/goal`, el tope va DENTRO de la condición ("o parar tras N turnos"); el timeout de wall-clock del
  punto anterior aplica igual.

## Paralelismo y control
- Tareas independientes → varios devs GLM en paralelo (run_in_background). **Cap práctico: ~3 modelos
  cloud concurrentes en Ollama** — no dispares más a la vez.
- **Devs concurrentes = conjuntos de archivos DISJUNTOS, declarados en la spec.** Trabajan sobre el
  mismo working tree: dos devs editando el mismo archivo se pisan. En cada spec poné "Toca SOLO <files>"
  y, si otro dev toca archivos vecinos, "NO toques <file>, otro dev trabaja ahí" (verificado: los devs
  lo respetan si está explícito). Tareas que compartan un archivo → batches secuenciales.
- **Los conteos de tests que reporta un dev concurrente son solo informativos**: su suite corrió
  mientras otros editaban (compilación rota transitoria, totales cambiantes). El ÚNICO conteo válido es
  el que corrés VOS tras integrar el batch.
- Para "mayor control": 2 devs sobre la misma tarea con enfoques distintos y comparás, o un dev
  implementa y otro revisa.

## Subagentes y agent teams dentro de un dev (verificado 2026-07-02)
- **Subagentes (tool `Agent`): disponibles headless SIN flag, en GLM y Kimi.** Un dev puede delegar hacia
  abajo para proteger su propio contexto en tareas grandes. Rastro forense: el subagente deja su propio
  transcript en `<proyecto>\<session>\subagents\agent-*.jsonl`.
- **Agent teams (task list compartida + mensajería): SOLO con `kimi-k2.7-code:cloud` como lead** y
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` en el env del lanzamiento. Kimi ejecutó el protocolo completo
  headless (TeamCreate → TaskCreate → spawn con team_name → teammates reclaman de la task list →
  SendMessage/inbox → TeamDelete). Los teammates heredaron el modelo del lead. Cap de Ollama (~3 cloud
  concurrentes) cuenta lead + teammates.
- **GLM NO sirve de lead de team y además reporta éxito falso:** nunca llamó TeamCreate, spawneó un
  subagente común y reportó "el teammate funcionó". Si un dev afirma que armó un team, verificá en el
  transcript (TeamCreate/SendMessage con success, dir `~\.claude\teams\<team>`), no su palabra.
- **`/goal` + teams: NO combinarlos por ahora.** Caso real: la condición exigía "teammates apagados al
  final", el estado nunca llegó (limitación conocida de teams: shutdown lento / task status que no se
  actualiza) y el lead persiguió lo inalcanzable en bucle infinito de TeamDelete hasta que el PM lo mató.
  Si igual se combina: condición SIN exigencias sobre el ciclo de vida del team (solo sobre archivos y
  tests) y monitoreo activo del PM con kill.
- Si un run de teams muere a mitad: limpiá los huérfanos `~\.claude\teams\<team>` y `~\.claude\tasks\<team>`.

## Verificación: confiá en el gate, no en leer el código
- El gate es determinista: PASS = cumple contrato + tests congelados + budget. Leé el veredicto, no el diff.
- **PERO el veredicto certifica el CONTRATO, no el diseño.** Leé SIEMPRE la sección de trade-offs del
  resumen del dev; si menciona un trade-off, inspeccioná el diff de ESA zona puntual (no el diff entero).
  Verificado: un dev cumplió el contrato con tests verdes degradando la búsqueda ANN a escaneo completo
  — solo se cazó leyendo su nota de trade-off y ~50 líneas de diff del hot path.
- **"Verificado por lectura" del dev = NO verificado.** Toda afirmación sin salida de máquina detrás
  (compilación, test) la re-verificás VOS con un comando antes de integrar (un `cargo check`/`tsc` son
  segundos). Verificado: un dev afirmó "código correcto por lectura" sobre un archivo con 8 errores de
  compilación.
- **Auditoría forense sin re-leer código (verificado 2026-07-02):** cada dev deja su transcript completo
  en `~\.claude\projects\<cwd-del-dev-sanitizado>\<session>.jsonl` (cada mensaje, tool call y salida real
  de comandos). Si dudás de un reporte, grep ahí (p.ej. la salida de `node --test`, o el registro
  `goal_status` con `met`/`reason`/`iterations` si usaste /goal) en vez de meter el diff a tu contexto.
- Si el repo tiene tests/CI, corrélos VOS como verificación final del batch. **Corré la suite completa
  DOS veces**: dos corridas idénticas ≈ determinismo; una sola corrida verde no detecta tests flaky
  (verificado: 2 flaky encontrados así). Un test flaky NO se tolera — es una tarea más (arreglar la
  causa raíz, no reintentar hasta verde), porque invalida el veredicto de toda suite futura.
- **Verificá → limpiá, nunca al revés** (2026-07-06): el artefacto de prueba (token canario, fixture,
  temporal) se conserva hasta CONFIRMAR el estado esperado; borrarlo antes destruye la única evidencia
  re-testeable. En sistemas de propagación eventual (secrets de Cloudflare, DNS, caches), un resultado
  inmediato contrario al esperado NO es fallo: re-verificá con reintentos espaciados (~10-30 s) antes de
  concluir. Caso real: token de prueba borrado antes del 401 de su revocación — el 200 era propagación
  y no quedó con qué re-testear; se resolvió con canario nuevo (alta → verificar → revocar → 401 → borrar).

## Reporte al usuario
- Respondé cuando haya algo **verificado**, no antes. Formato: completado (con veredicto) / en progreso /
  bloqueado y por qué.
- Si el flujo es issue-primero, creá/actualizá issues por hallazgo.

## Lecciones (por tema; la fecha entre paréntesis es la jornada en que se verificó)

### Doctrina del PM
- NO hagas el trabajo vos "porque es rápido": el costo de tu contexto es el cuello de botella; **delegá**.
- No te pongas a vos de portón con "¿conviene delegar?": en esta skill, **siempre se delega**; vos dirigís.
- **Retoques triviales de integración los hace el PM, no un dev nuevo** (2026-07-04): typo de 2 palabras,
  alinear registro (voseo→tuteo). Re-delegar eso cuesta más que hacerlo; no viola "no escribís código de
  producción" (es pulido de integración, no implementación). El umbral: si necesita tests, se delega.
- **KDD es la metodología canónica; esta skill es la capa operativa** (2026-07-05). Ante cualquier mejora
  de proceso: actualizar PRIMERO el repo KDD (MauricioPerera/KDD) y reflejar después acá.
- Relación: [`delegar-ollama`](../delegar-ollama/SKILL.md) cubre la mecánica de lanzamiento agnóstica al
  modelo — comando, `/goal`, permisos, sondas, anti-cuelgue, monitoreo por mtimes, arranques escalonados,
  error transitorio, cuota de cuenta y recuperación tras muerte del host; NADA de eso se repite acá.
  [`delegar-glm-ccdd`](../delegar-glm-ccdd/SKILL.md) cubre delegar UNA función con GLM. **Esta es la capa
  de PROYECTO** (varias tareas, varios devs, integración) por encima de ambas.

### Specs
- **El dev copia el REGISTRO de la spec, no el del repo** (2026-07-04). Specs en voseo produjeron docs en
  voseo dentro de un repo en tuteo, aunque la spec pedía "tono consistente con el README". Si el registro
  importa, decilo EXPLÍCITO con ejemplo ("tuteo: 'explora', no 'explorá'") o asumí el retoque al integrar.
- **Cláusulas de honestidad cuando el hecho pueda ser inalcanzable por razones legítimas** (2026-07-05):
  "si <condición legítima>, documentalo con el análisis y PARÁ, no lo fuerces" + prohibir inventar tests.
  Caso que habilitaron: un dev demostró con fuzz (69k inputs) que un mutante de una auditoría de mutación
  era EQUIVALENTE y que los otros ya morían — el tool los reportaba vivos por un bug real de `__pycache__`
  stale. Un aparente FAIL se convirtió en dos fixes de producción.
- **Features de infraestructura sobre un núcleo vivo: siempre opt-in** (2026-07-05): wal/lock/autoflush
  como opciones nuevas con default = comportamiento previo intacto. Permitió aterrizar WAL + transacciones
  + lock + CRC en 6 tareas seguidas sin romper jamás los tests preexistentes.
- **Núcleo con copias vendored congeladas por test de sincronía** (2026-07-05): toda spec que toque el
  núcleo incluye como paso final "copiar el raíz byte-idéntico sobre <copias>" — si no, la suite rompe
  por diseño y el dev reporta un FAIL que no es suyo.
- **Baseline rota = tarea T0 antes de cualquier feature** (2026-07-05), con los tests rojos existentes
  como oráculo congelado si los hay (17 tests describían funciones jamás implementadas: spec gratis).
  Los devs de features en paralelo reciben el aviso "la suite completa puede estar roja por X ajeno;
  tu veredicto son TUS suites + no aportar errores nuevos a tsc".
- **Fallos de spec al "exponer/subir" a una fachada** (2026-07-06; ya integrados al red-team del HECHO,
  arriba): (1) **feature decorativa** — se expuso `ensureIndex` pero ningún camino público usaba el índice;
  contrato cumplido, tests verdes, valor cero; (2) **contenedor divergente** — `find` delegado literal
  devolvía Cursor lazy en un modo y array en otro; la spec fijaba la shape pero no el contenedor. Ambos
  fueron fallos del PM, no del dev: el dev entregó lo pedido y DECLARÓ el trade-off.
- **Pendiente colateral viaja gratis en la spec siguiente que ya toca ese archivo** (2026-07-06): recrear
  una sección del CHANGELOG se encargó en una línea al dev de la tarea siguiente, sin tarea propia.

### Delegación y batches
- **El gate lo puede correr el PM, no el dev** (2026-07-04). Con el MCP `ccdd-complexity` en TU sesión,
  es más barato dar a los devs MCP vacío + hecho verificable por suite/greps, y correr vos
  `lint_task_contract` sobre el entregable. Mismo veredicto determinista, cero riesgo de flota MCP en los
  devs. Gate-en-el-dev solo cuando deba ITERAR contra el gate (funciones nuevas complejas).
- **Verificación en dos momentos** (2026-07-04): los entregables de un dev que ya terminó se verifican
  (lint, lectura puntual) MIENTRAS los otros devs del batch siguen corriendo — archivos disjuntos, no hay
  carrera. La suite completa 2× sí espera al batch entero.
- **El fix de un batch sin commitear puede re-delegarse sobre el árbol sucio** (2026-07-06) indicándole
  al dev que los archivos del batch anterior "SON TUYOS para corregir". El commit llega cuando el batch
  completo pasa el veredicto del PM.
- **El shell del PM puede reiniciarse entre llamadas** (2026-07-05; cwd vuelve al default sin aviso):
  el comando que lanza un dev SIEMPRE lleva su `cd` explícito delante.
- **Matices GLM sobre la cuota** (2026-07-05; la mecánica general está en `delegar-ollama`): vacío
  repetido ≠ spec grande — antes de subdividir una spec que vuelve vacía, descartá ventana mala del
  proveedor con la sonda de tools. Y una muerte por cuota al FINAL de la tarea puede dejar trabajo
  COMPLETO y verde en disco (murieron escribiendo su REPORT): auditá disco y corré el gate ANTES de
  darlo por FAIL — el gate decide, no el log; un batch entero se integró así sin re-delegar nada.

### Verificación
- **Tareas de DOCS: hecho determinista por greps de presencia Y ausencia** (2026-07-04):
  `grep -n "<clave>" <files>` (hit obligatorio en cada archivo) + `grep -rn "<prohibido>" <files>
  || echo SIN_MENCIONES` + suite verde. El dev pega la salida real y el PM re-corre los mismos greps.
  Sin esto, una tarea de docs no tiene veredicto y cae a "confiar en la lectura".
- **La verificación local del PM = EXACTAMENTE los checks que el PR va a correr, incluidos los
  CONDICIONALES por diff** (2026-07-04/05). Caso 1: suite verde pero el check `gate` de dogfooding del
  repo falló en el PR por una función con nesting 5. Caso 2: un gate de CI que solo corre si el PR toca
  cierto tipo de archivo puede no haber corrido NUNCA hasta tu PR y fallar en cascada por capas. Antes
  del primer batch: leer TODOS los workflows (también los pasos condicionales) y replicarlos local.
- **Trade-off declarado ≠ trade-off aceptable: juzgalo contra el PROPÓSITO de la pieza** (2026-07-04).
  Un dev declaró honesto que en Go `func f(a, b int)` contaba 1 parámetro; contra el budget params≤5 eso
  es evasión del gate (`f(a,b,c,d,e,f int)` → 1). Complementos baratos: demo en vivo del PM con inputs
  PROPIOS (no los del dev), y **leer SIEMPRE la sección de trade-offs del REPORT** — re-confirmada
  (2026-07-06) como el detector más barato: los fallos de fachada se cazaron leyéndola + diff puntual.
- **Oráculos congelados (fixtures/manifest): exigí "cambio ADITIVO" y verificalo SEMÁNTICAMENTE**
  (2026-07-04) — cargar el JSON de HEAD y el nuevo y comparar por entrada, no por diff de líneas: un diff
  con 9 líneas borradas resultó reformateo inocuo, y un diff "limpio" podría esconder un cambio de valor.
- **Todo workflow de GitHub editado por un dev se parsea localmente antes de pushear** (2026-07-05):
  `python -c "import yaml; yaml.safe_load(open('.github/workflows/X.yml'))"`. Fallo real: `- name: KDD:
  validar...` (dos puntos sin comillas) → YAML inválido → el workflow requerido falla en 0s SIN
  check-runs y la protección de rama bloquea el merge. Diagnóstico: `gh run list` con failures de 0s.
- **Ante un "imposible" del dev: reproducción barata del PM ANTES de re-delegar o descartar**
  (2026-07-05): una reproducción de 1 comando confirmó el bug del tool y convirtió un FAIL aparente en
  fixes de producción (ver el caso del mutante equivalente en Specs).
- **Los fallos en cascada de gates apilados son el sistema FUNCIONANDO** (2026-07-05): cada re-corrida
  destapa la capa siguiente (cwd → budget → mutación → YAML). Presupuestá 1 re-delegación chica por capa
  y mantené "el gate es la ley" (nunca debilitarlo para que pase — salvo bug demostrado DEL gate).
- **Ojo con el pipe al verificar la suite** (2026-07-06): `node --test | tail` enmascara el exit code.
  O capturás el conteo con grep de `pass/fail`, o corrés sin pipe y validás exit 0.
- **Cierre de cadena de features: un harness adversarial de verdad** (2026-07-05) — crash-injection con
  SIGKILL real y chequeo de invariantes tras recuperación como ÚLTIMA tarea, con cláusula "si un
  invariante falla es hallazgo: documentá y dejá el FAIL, prohibido parchear el núcleo o debilitar el
  assert". Valida la cadena entera con evidencia de máquina, no con lecturas.
- **En repos KDD, el checklist pre-delegación es EJECUTABLE** (2026-07-05): `python scripts/validate_specs.py
  specs` valida los contratos de ejecución (abiertos exigen Tocar SOLO y ABORTAR SI; cerrados solo
  baseline). Corrélo como parte de la verificación de batch; no confíes en la disciplina del redactor.

### Entorno y RECON
- **El PM prepara el entorno ANTES de redactar specs** (2026-07-04): instalar deps que los devs van a
  necesitar (p.ej. gramáticas tree-sitter) + smoke de carga. Verifica viabilidad de una vez y evita que
  N devs redescubran la dependencia faltante por separado.
- **Bug de versión fantasma (chequeo RECON barato en proyectos npm)** (2026-07-05): código commiteado
  contra una versión de dependencia NUNCA publicada → baseline rota en tests Y build. Check: `npm view
  <dep> versions` vs package.json vs los imports que el código usa. Fix que preserva la intención:
  feature-detection en runtime, no borrar la lógica.
