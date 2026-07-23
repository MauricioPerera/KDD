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
