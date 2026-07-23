---
type: 'Concept'
title: 'Casos reales de la metodología'
description: 'Incidentes verificados en producción que motivaron reglas de la metodología de ejecución; evidencia separada del proceso normativo.'
tags: ['metodologia', 'casos', 'evidencia']
---

# Casos reales

Evidencia que motivó reglas de la [metodología de ejecución](./metodologia-ejecucion.md). El proceso normativo vive allá; aquí solo los incidentes, para que la narrativa no cargue el contexto de cada delegación. Cada caso lleva el ancla que la metodología enlaza.

## entorno-afirmado (PLAN / RECON)

Un agente arrancó con `ERR_MODULE_NOT_FOUND` porque la spec afirmaba un entorno («node_modules ya está instalado») que no existía. Un fallo ambiental se parece a una «causa preexistente» y dispara un ABORTAR SI legítimo, quemando la delegación. Se salvó por iniciativa del agente, no por diseño. Regla derivada: si el check no se corrió, la spec no afirma — condiciona («si falta X, instalarlo con Y»).

## crear-sobre-existente (PLAN / RECON)

Un pedido de «crea el repo» se ejecutó sobre un repo que ya existía con más contenido del que se iba a migrar; lo salvó el fallo del proveedor («name already exists»), no el proceso. Regla derivada: «crear X» = «asegurar que X exista con este contenido» — verificar existencia con un check barato primero; si existe, inspeccionar y reconciliar, nunca crear ni forzar por encima.

## hecho-sin-intencion (SPEC / red-team de la definición de hecho)

Formas verificadas en que un comando de verificación se cumplió sin cumplir la intención:

- Búsqueda degradada a escaneo completo con tests verdes.
- Conteo de parámetros que evadía el budget del gate (`f(a, b int)` contado como 1 → `f(a,b,c,d,e,f int)` = 1).
- Un grep de verificación que matcheaba el valor exigido por otra orden del mismo plan (un check que contradice una orden propia fuerza al agente a un judgment call que la spec prometía no dejarle).
- Un índice expuesto que ningún camino público consumía (`count` seguía escaneando): contrato cumplido, tests verdes, valor cero — feature decorativa.
- Un `find` delegado literal que devolvía un cursor lazy en un modo y un array en otro: la spec fijaba la shape del elemento pero no el tipo/contenedor exacto de retorno por modo.

Complemento verificado: exigir sección de **trade-offs** en el reporte del agente es el detector más barato de estas clases — los dos últimos casos se declararon ahí y se cazaron leyendo esa sección + el diff puntual de la zona, nunca el diff entero.

## verificar-antes-de-limpiar (VERIFICAR)

Un token de prueba se borró ANTES de observar el 401 de su revocación — el 200 inmediato era solo propagación del secret y ya no quedaba con qué re-testear. Se resolvió con un canario nuevo (alta → verificar → revocar → verificar 401 → recién entonces borrar). Regla derivada: el artefacto de prueba se conserva hasta CONFIRMAR el estado final; y en sistemas de propagación eventual, un resultado inmediato contrario al esperado se re-verifica con reintentos espaciados antes de concluir.

## replace-silencioso-en-docs (CERRAR / documentación)

En el ciclo de v1.2.0, tres entradas del CHANGELOG (C20-C22) se perdieron: un `str.replace('## Unreleased...')` no matcheó (la sección ya no existía tras el release anterior) y el script imprimió éxito igual, tres veces. Se descubrió recién al cortar v1.2.0 ("nothing to commit"). Regla derivada: toda edición programática de documentación se verifica con grep de PRESENCIA antes de commitear, o se hace con una herramienta de edición que falle ruidoso si el ancla no existe. La regla humana quedó automatizada en el gate `scripts/validate_changelog.py` (Contrato 27): todo reporte de contrato exige su entrada en el CHANGELOG, y viceversa — la clase entera de este incidente ahora rompe el CI en vez de perderse en silencio.

## colision-de-entregables (SPEC)

Tres specs paralelas asignaron nombres de reporte (`FIX-M1..M3-REPORT.md`) sin mirar que esos archivos YA existían commiteados de una ronda anterior. Los tres agentes efímeros detectaron la colisión por su cuenta y renombraron su entregable sin sobrescribir — buen instinto, pero fue suerte, no diseño: un agente menos cuidadoso habría pisado historial trackeado. Regla derivada: al redactar la spec, listar el directorio de entregables (`ls`) y asignar nombres verificados como libres; añadir la cláusula «si el archivo ya existe, NO lo sobrescribas: elegí otro nombre y decláralo».

## tension-de-diseno-en-la-spec (SPEC)

Un fix de corrupción de datos tenía una tensión fundamental: dos casos legítimos (valor journaleado desde un float vs. texto arbitrario que parece float) eran indistinguibles por el texto solo, y el arreglo ingenuo de uno rompía el otro. La spec explicó la tensión («por texto no se puede distinguir X de Y; la desambiguación probablemente venga de <fase anterior> que sí conoce Z»), fijó tres requisitos innegociables verificables por máquina, dejó el CÓMO libre y añadió cláusula de honestidad («si concluís con evidencia que no se puede, PARÁ y entregá el análisis»). El agente aterrizó un diseño correcto (marcador reservado emitido en la fase que conoce el dato faltante) en un solo intento, que después sobrevivió una ronda de auditoría adversarial dedicada. Regla derivada: cuando el orquestador conoce la tensión de diseño, va EN la spec con una dirección candidata — ocultarla no «deja libertad», condena al agente a iterar a ciegas contra un muro que el orquestador ya había mapeado.

## formato-persistente-sin-contrato-de-upgrade (SPEC / CIERRE)

Un fix correcto y verificado cambió el formato de un artefacto persistente (el journal de captura ganó un marcador). Recién una ronda de auditoría posterior notó que los datos in-flight de la versión anterior (journals capturados con triggers viejos) divergían al aplicarse con el código nuevo — detectado por la verificación, no silencioso, pero el requisito operativo (reinstalar triggers, drenar o re-snapshotear al actualizar) no estaba documentado en ningún lado. Regla derivada: todo cambio de formato en un artefacto persistente (journal, wire format, schema, archivo de estado) obliga a preguntar en la spec «¿qué pasa con los datos in-flight de la versión vieja?» — el fix técnico y su contrato de upgrade son la MISMA tarea; si la spec no lo pide, nadie lo escribe.

## contrato-bilateral-mitad-arreglado (VERIFICAR)

Fuera de este repo (proyecto hermano `mcpwasm`, mismo dueño): un bug real en `canonicalOrigin()` — `new URL(s).origin` descarta el subpath de una URL, rompiendo la firma Ed25519 de skills publicadas en un GitHub Pages de *proyecto* (`user.github.io/REPO/`, no de dominio raíz) — se arregló en el lado que **firma** (`scripts/attest.mjs`). Verificación propia completa en ese lado: tests unitarios, verificación criptográfica de la firma contra la clave pública, corrida real contra el sitio en producción. Todo dio verde. Lo que no se verificó: la misma función `canonicalOrigin()` estaba duplicada, sin arreglar, en los dos lugares que **consumen** esa firma (`worker-gateway.mjs`, el gate que hace cumplir las atestaciones en el propio servidor; `scripts/validate-publisher.mjs`, el linter de onboarding). El fix hacía que las firmas se generaran bien y se **rechazaran** en todo lugar donde se verificaban — el bug no desaparecía, cambiaba de lado. Lo encontraron dos revisores de código automáticos independientes (Gemini Code Assist y Codex) comentando la misma PR, en paralelo, sin que ninguno supiera del otro. Regla derivada: cuando el fix toca una función que un lado de un contrato bilateral usa para producir algo (firmar, escribir, serializar) y otro lado usa para consumirlo/verificarlo (verificar, leer, deserializar), un grep del nombre de la función en todo el repo es parte de la verificación — "mis tests pasan" certifica el lado que tocaste, no que seas consistente con quien consume tu output. Complemento: una segunda opinión independiente (humana o de otro agente) sigue cazando cosas que la propia verificación exhaustiva de un lado no puede ver por construcción.

## persiste-de-auditor-refutado (VERIFICAR)

En una ronda de confirmación de cierre, un auditor efímero reportó un hallazgo previo como PERSISTE citando una línea concreta del archivo — pero el fix real vivía en un helper extraído por un refactor posterior, con tests verdes que lo demostraban. Un grep + un `go test -run` del orquestador (un minuto) refutaron el reporte. Regla derivada: el «PERSISTE» de un auditor es una afirmación como cualquier otra y se re-verifica con reproducción barata del orquestador ANTES de re-delegar o de aceptar el veredicto — simétrico al «imposible» de un dev, que ya exigía reproducción antes de descartar. La refutación se documenta donde quede el veredicto final (commit de reportes), para que el falso PERSISTE no renazca en la ronda siguiente.

## check-que-fallo-no-es-check (VERIFICAR)

Un `grep ... || echo SIN_STALE` «confirmó» la ausencia de texto obsoleto en docs — pero el comando había fallado porque `grep` no existe en esa shell (PowerShell), no porque no hubiera matches: el fallback del `||` convirtió un error de herramienta en un falso negativo limpio. Regla derivada: una verificación de AUSENCIA solo vale si la herramienta corrió de verdad — distinguí «corrió y no encontró» de «no corrió»; usá una herramienta confirmada en esa shell y, ante un check cuyo resultado depende del exit code, verificá primero que el comando exista. Un check que falla por otra razón no es un check.

## ronda-de-confirmacion (CIERRE)

Tras un ciclo auditoría→fixes (3 rondas, 17 hallazgos ALTA/MEDIA cerrados), una cuarta ronda con mandato INVERTIDO convirtió «creemos que quedó limpio» en evidencia: cada auditor (1) re-ejecutó la reproducción original de CADA hallazgo previo de su scope sobre HEAD y entregó una tabla CERRADO/PERSISTE con salida real, y (2) atacó adversarialmente el código NUEVO de los fixes con inputs que las repros originales no cubrían. Resultado: 21/21 cierres confirmados, cero regresiones ALTA/MEDIA nuevas, y de yapa afloraron huecos de documentación que ninguna ronda de búsqueda había visto (el contrato de upgrade del caso formato-persistente-sin-contrato-de-upgrade salió de acá). Regla derivada: un ciclo de auditoría no se cierra con el último fix — se cierra con una ronda de confirmación cuyo veredicto firma el orquestador tras refutar o confirmar cada PERSISTE (ver persiste-de-auditor-refutado).

## infra-huerfana-es-evidencia (CIERRE)

Una sesión murió a mitad de un cierre de batch dejando un contenedor de base de datos efímero vivo en el servidor. La sesión siguiente, en vez de borrarlo y re-provisionar a ciegas, lo inspeccionó primero (`docker inspect ... Config.Env`) y recuperó el DSN exacto con el que se había verificado el batch — pudiendo reanudar el cierre (suite e2e, commit, push, desmonte) sin rehacer nada. Regla derivada: tras una interrupción, la infraestructura huérfana es EVIDENCIA del estado del trabajo antes que basura — inspeccionar y extraer lo que documenta (credenciales efímeras, versiones, estado) ANTES de desmontarla. Complemento del patrón general: infra efímera se provisiona por batch y se desmonta en el cierre; si el cierre no llegó, la infra colgada es la señal de que el cierre está pendiente.

## no-verificado-acumulado (VERIFICAR)

Cuatro rondas de auditoría dejaron los mismos caminos marcados «NO VERIFICADO» por falta de una dependencia viva (base de datos real), y encima de esos caminos vivía un hallazgo grave real: una familia de tipos cuya migración SIEMPRE divergía con datos correctos — invisible para los tests unitarios y para la auditoría estática, porque solo se manifestaba contra la infraestructura real. La quinta ronda recibió la dependencia provisionada (contenedor efímero + DSN) y cazó el bug en un solo pase, además de convertir en evidencia ejecutada todos los caminos ex-pendientes. Regla derivada: los «NO VERIFICADO» que se repiten entre rondas son DEUDA de auditoría, no una anotación neutral — si la misma zona queda sin verificar dos rondas seguidas, la ronda siguiente incluye provisionar la dependencia (infra efímera) en vez de re-anotar el hueco.

## credencial-efimera-a-delegados (DELEGAR)

Para que auditores y devs efímeros ejercitaran caminos que exigen una base de datos real, se les pasó el DSN (con password) por variable de entorno y en la spec, con la orden explícita «enmascarralo SIEMPRE como *** en el reporte». El orquestador verificó después con grep que el literal no apareciera en ningún entregable: cero fugas en tres corridas, y la credencial murió con el contenedor al desmontarlo. Regla derivada: una credencial efímera puede viajar a un agente delegado si (1) es de vida corta y muere con la infra, (2) la spec ordena el enmascarado explícito con el formato exacto, y (3) el orquestador verifica cero ocurrencias literales en los entregables — la orden sin la verificación es confianza, no control.

## clase-cazada-a-clausula-de-spec (SPEC)

La misma clase de staleness («test agregado sin actualizar el conteo documentado») se cazó dos veces en la verificación del orquestador. A partir de la segunda, la cláusula «si agregás tests top-level, actualizá el conteo en <docs>» pasó a viajar en toda spec que tocara esa zona — y la tercera vez el agente lo hizo solo, sin retoque del orquestador. Regla derivada: una clase de fallo cazada dos veces deja de ser un ítem de verificación y se convierte en cláusula estándar de las specs de esa zona; prevenir en la spec es más barato que re-cazar en cada verificación, y además le enseña el patrón al agente en vez de corregirlo por detrás.

## contrato-documentado-cambia-junto (SPEC / VERIFICAR)

Un fix cosmético (un mensaje de error duplicado en stderr) tocaba un patrón de salida que la documentación machine-facing describía LITERALMENTE y que los tests end-to-end asserteaban. La spec ordenó «docs, código y tests se mueven JUNTOS — cero claims que el binario no cumpla», y el entregable llegó coherente en el mismo cambio. Regla derivada: cuando el comportamiento a cambiar está descrito en un contrato documentado (aunque el cambio sea trivial), la spec exige actualizar documentación, código y asserts en la MISMA tarea — un fix que deja la doc mintiendo reabre exactamente la clase de hallazgo doc↔código que las auditorías cierran.

## rescate-hibrido-por-cuota (DELEGAR / recuperación)

Un agente delegado murió por cuota del proveedor A MITAD de una tarea de dos partes. El disco reveló que la primera parte estaba COMPLETA y verde (un fix de parser con sus tests, +126 líneas, gate en verde); la segunda ni empezada. En vez de re-delegar la tarea entera o darla por FAIL, el orquestador: (1) verificó la mitad sobreviviente por artefacto (gate + tests, no el log del muerto); (2) delegó SOLO el resto a un mecanismo alternativo que no dependía de esa cuota (subagente nativo de la propia app), sobre el mismo árbol sucio, con la mitad verde CERCADA en la spec («YA COMPLETO, verificado por el orquestador, NO lo toques salvo que <condición> lo exija») y los cambios huérfanos declarados «SON TUYOS para completar». Cero trabajo rehecho, cero conflicto entre mecanismos. Regla derivada: ante una muerte a mitad de tarea, el disco se tría en dos — lo verde sobrevive cercado, lo faltante se delega solo; y tener un mecanismo de delegación alternativo (otro proveedor/otra vía) convierte la cuota agotada en un desvío, no en un bloqueo.

## demo-por-el-camino-documentado (VERIFICAR)

Un agente entregó un script «verificado real» — y su verificación era honesta: lo corrió con éxito pasando la credencial por flag. Lo que su verificación no podía ver: el script PISABA la variable de entorno que la documentación del proyecto manda usar, porque el agente solo ejercitó SU forma de invocarlo. La demo del orquestador usó la invocación exacta que la doc prescribe (env var seteada, sin flag) y cazó el clobber en un comando. Regla derivada: el agente puede demostrar con los parámetros que elija; el orquestador re-demuestra con la invocación que los docs/usuarios reales van a usar — si el camino del agente y el camino documentado difieren, el bug vive exactamente en esa diferencia. Es la variante de interfaz del principio «demo en vivo con inputs PROPIOS del orquestador, no los del agente».

## nota-de-upgrade-no-ejecutada (SPEC / VERIFICAR)

Un fix correcto y verificado incluyó su nota de upgrade, y la nota afirmaba un outcome concreto («el primer verify contra un destino legado reporta divergencia») que el agente NUNCA ejecutó: describió el escenario legado sin construirlo. La ronda de confirmación posterior creó el artefacto legado A MANO (una tabla con el tipo nativo viejo) y el comportamiento real era otro: la rama defensiva del fix hacía CONVERGER la re-verificación, y el flujo CLI ni siquiera llegaba a verify (colisionaba antes con otro error). El principio de seguridad («nunca silencioso») se cumplía; el outcome narrado, no — un agente que siguiera la nota esperaría un error que jamás iba a ver. Regla derivada, doble: (a) la spec de un fix que incluya nota de upgrade exige que el agente EJECUTE el escenario legado que describe — construir el artefacto de la versión vieja cuesta minutos y convierte la prosa en evidencia; (b) la ronda de confirmación audita también las NOTAS que los fixes escribieron, no solo su código: una afirmación de comportamiento en una nota de upgrade es un claim verificable más, con el mismo estatus que cualquier claim del contrato.

## excepcion-unica-declarada (SPEC)

Al unificar tres binarios CLI en uno con subcomandos, la spec fijó: «comportamiento observable byte-idéntico, con UNA excepción deliberada: los prefijos de mensaje cambian de X a Y». Con la excepción delimitada de forma exhaustiva, todo lo demás se verificó mecánicamente contra el comportamiento previo (envelopes, exit codes, streams, orden de líneas), y la ronda de auditoría posterior confirmó el contrato completo. Regla derivada: en un cambio que promete preservar comportamiento («refactor», «unificación», «migración»), las divergencias deliberadas se enumeran EXPLÍCITAS y cerradas en la spec — «básicamente igual» no es verificable; «idéntico salvo exactamente esto» sí.
