---
type: 'Concept'
title: 'Casos reales de la metodología'
description: 'Incidentes verificados en producción que motivaron reglas de la metodología de ejecución; evidencia separada del proceso normativo.'
tags: ['metodologia', 'casos', 'evidencia']
---

# Casos reales

Evidencia que motivó reglas de la [metodología de ejecución](./metodologia-ejecucion.md). El proceso normativo vive allá; aquí solo los incidentes, para que la narrativa no cargue el contexto de cada delegación. Cada caso lleva el ancla que la metodología enlaza.

Los relatos completos y su evidencia se conservan en el [archivo historico](../docs/reports/ARCHIVO-CASOS-REALES.md). Este indice conserva todas las anclas y una sintesis por caso para mantener acotado el snapshot de memoria.

## entorno-afirmado (PLAN / RECON)

Un agente arrancó con `ERR_MODULE_NOT_FOUND` porque la spec afirmaba un entorno («node_modules ya está instalado») que no existía.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#entorno-afirmado-plan--recon).

## crear-sobre-existente (PLAN / RECON)

Un pedido de «crea el repo» se ejecutó sobre un repo que ya existía con más contenido del que se iba a migrar; lo salvó el fallo del proveedor («name already exists»), no el proceso.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#crear-sobre-existente-plan--recon).

## hecho-sin-intencion (SPEC / red-team de la definición de hecho)

Formas verificadas en que un comando de verificación se cumplió sin cumplir la intención:

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#hecho-sin-intencion-spec--red-team-de-la-definición-de-hecho).

## verificar-antes-de-limpiar (VERIFICAR)

Un token de prueba se borró ANTES de observar el 401 de su revocación — el 200 inmediato era solo propagación del secret y ya no quedaba con qué re-testear.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#verificar-antes-de-limpiar-verificar).

## replace-silencioso-en-docs (CERRAR / documentación)

En el ciclo de v1.2.0, tres entradas del CHANGELOG (C20-C22) se perdieron: un `str.replace('## Unreleased...')` no matcheó (la sección ya no existía tras el release anterior) y el script imprimió éxito igual, tres veces.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#replace-silencioso-en-docs-cerrar--documentación).

## colision-de-entregables (SPEC)

Tres specs paralelas asignaron nombres de reporte (`FIX-M1..M3-REPORT.md`) sin mirar que esos archivos YA existían commiteados de una ronda anterior.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#colision-de-entregables-spec).

## tension-de-diseno-en-la-spec (SPEC)

Un fix de corrupción de datos tenía una tensión fundamental: dos casos legítimos (valor journaleado desde un float vs.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#tension-de-diseno-en-la-spec-spec).

## formato-persistente-sin-contrato-de-upgrade (SPEC / CIERRE)

Un fix correcto y verificado cambió el formato de un artefacto persistente (el journal de captura ganó un marcador).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#formato-persistente-sin-contrato-de-upgrade-spec--cierre).

## contrato-bilateral-mitad-arreglado (VERIFICAR)

Fuera de este repo (proyecto hermano `mcpwasm`, mismo dueño): un bug real en `canonicalOrigin()` — `new URL(s).origin` descarta el subpath de una URL, rompiendo la firma Ed25519 de skills publicadas en un GitHub Pages de *proyecto* (`user.github.io/REPO/`, no de dominio raíz) — se arregló en el lado que **firma** (`scripts/attest.mjs`).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#contrato-bilateral-mitad-arreglado-verificar).

## persiste-de-auditor-refutado (VERIFICAR)

En una ronda de confirmación de cierre, un auditor efímero reportó un hallazgo previo como PERSISTE citando una línea concreta del archivo — pero el fix real vivía en un helper extraído por un refactor posterior, con tests verdes que lo demostraban.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#persiste-de-auditor-refutado-verificar).

## check-que-fallo-no-es-check (VERIFICAR)

Un `grep ... || echo SIN_STALE` «confirmó» la ausencia de texto obsoleto en docs — pero el comando había fallado porque `grep` no existe en esa shell (PowerShell), no porque no hubiera matches: el fallback del `||` convirtió un error de herramienta en un falso negativo limpio.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#check-que-fallo-no-es-check-verificar).

## alcance-real-de-un-gate-no-es-el-prometido (VERIFICAR)

Un gate de CI que valida enlaces relativos en documentación resultó, al leer su código fuente, verificar solo que el ARCHIVO destino de un link exista — nunca que un fragmento de ancla (`#slug`) resuelva a un heading real dentro de ese archivo.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#alcance-real-de-un-gate-no-es-el-prometido-verificar).

## auditoria-de-artefacto-sin-motor-vivo (CIERRE)

Tras reestructurar la propia documentación de proceso (mover reglas de sitio, consolidar referencias dispersas en una sección nueva), no había código ni motores reales contra los que correr una ronda de auditoría convencional.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#auditoria-de-artefacto-sin-motor-vivo-cierre).

## ronda-de-confirmacion (CIERRE)

Tras un ciclo auditoría→fixes (3 rondas, 17 hallazgos ALTA/MEDIA cerrados), una cuarta ronda con mandato INVERTIDO convirtió «creemos que quedó limpio» en evidencia: cada auditor (1) re-ejecutó la reproducción original de CADA hallazgo previo de su scope sobre HEAD y entregó una tabla CERRADO/PERSISTE con salida real, y (2) atacó adversarialmente el código NUEVO de los fixes con inputs que las repros originales no cubrían.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#ronda-de-confirmacion-cierre).

## infra-huerfana-es-evidencia (CIERRE)

Una sesión murió a mitad de un cierre de batch dejando un contenedor de base de datos efímero vivo en el servidor.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#infra-huerfana-es-evidencia-cierre).

## no-verificado-acumulado (VERIFICAR)

Cuatro rondas de auditoría dejaron los mismos caminos marcados «NO VERIFICADO» por falta de una dependencia viva (base de datos real), y encima de esos caminos vivía un hallazgo grave real: una familia de tipos cuya migración SIEMPRE divergía con datos correctos — invisible para los tests unitarios y para la auditoría estática, porque solo se manifestaba contra la infraestructura real.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#no-verificado-acumulado-verificar).

## credencial-efimera-a-delegados (DELEGAR)

Para que auditores y devs efímeros ejercitaran caminos que exigen una base de datos real, se les pasó el DSN (con password) por variable de entorno y en la spec, con la orden explícita «enmascarralo SIEMPRE como *** en el reporte».

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#credencial-efimera-a-delegados-delegar).

## clase-cazada-a-clausula-de-spec (SPEC)

La misma clase de staleness («test agregado sin actualizar el conteo documentado») se cazó dos veces en la verificación del orquestador.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#clase-cazada-a-clausula-de-spec-spec).

## contrato-documentado-cambia-junto (SPEC / VERIFICAR)

Un fix cosmético (un mensaje de error duplicado en stderr) tocaba un patrón de salida que la documentación machine-facing describía LITERALMENTE y que los tests end-to-end asserteaban.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#contrato-documentado-cambia-junto-spec--verificar).

## investigacion-bloqueada-necesita-arnes (DELEGAR)

Se pidió a un agente investigar la viabilidad de una feature de riesgo semántico real (una recursión que podía no terminar entre dos motores), con instrucción explícita de que un BLOQUEADO con evidencia era un resultado tan válido como que la feature entrara.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#investigacion-bloqueada-necesita-arnes-delegar).

## limite-declarado-es-el-siguiente-objetivo-de-auditoria (VERIFICAR)

Una cadena de rondas de confirmación fue convergiendo: una ronda cerró un hallazgo, la siguiente ronda no se limitó a repetir la prueba original sino que atacó específicamente el LÍMITE que el fix había declarado por escrito (p.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#limite-declarado-es-el-siguiente-objetivo-de-auditoria-verificar).

## propiedad-atipica-en-compilador-generico (SPEC)

Se agregó a una gramática compartida un nodo con una propiedad atípica (no determinismo: genera un valor distinto en cada evaluación), pensado para dos contextos de uso concretos y documentados.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#propiedad-atipica-en-compilador-generico-spec).

## artefacto-real-encuentra-gaps-que-la-clasificacion-abstracta-no (PLAN)

En vez de seguir enumerando categorías de qué debería soportarse en abstracto, se escribió a mano UN artefacto representativo del caso de uso real (un esquema típico completo, con sus tablas/triggers/vistas reales) y se corrió por el pipeline real de la herramienta.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#artefacto-real-encuentra-gaps-que-la-clasificacion-abstracta-no-plan).

## rescate-hibrido-por-cuota (DELEGAR / recuperación)

Un agente delegado murió por cuota del proveedor A MITAD de una tarea de dos partes.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#rescate-hibrido-por-cuota-delegar--recuperación).

## demo-por-el-camino-documentado (VERIFICAR)

Un agente entregó un script «verificado real» — y su verificación era honesta: lo corrió con éxito pasando la credencial por flag.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#demo-por-el-camino-documentado-verificar).

## nota-de-upgrade-no-ejecutada (SPEC / VERIFICAR)

Un fix correcto y verificado incluyó su nota de upgrade, y la nota afirmaba un outcome concreto («el primer verify contra un destino legado reporta divergencia») que el agente NUNCA ejecutó: describió el escenario legado sin construirlo.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#nota-de-upgrade-no-ejecutada-spec--verificar).

## excepcion-unica-declarada (SPEC)

Al unificar tres binarios CLI en uno con subcomandos, la spec fijó: «comportamiento observable byte-idéntico, con UNA excepción deliberada: los prefijos de mensaje cambian de X a Y».

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#excepcion-unica-declarada-spec).

## contrato-exige-superficie-no-expuesta (SPEC)

Un contrato de prueba end-to-end exigía dos condiciones simultáneas: un dato debía crearse VÍA LA API PÚBLICA real (no inserts directos, para probar el camino que un usuario real ejercitaría) Y ese dato debía incluir un campo (metadata JSON no vacía) que el endpoint existente, de un contrato anterior, no aceptaba — hacía el requisito insatisfacible tal como estaba la superficie.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#contrato-exige-superficie-no-expuesta-spec).

## destino-no-idempotente-se-limpia-antes-de-cada-corrida (DELEGAR / VERIFICAR)

Una herramienta de copia/exportación cuyo lado de escritura hace `CREATE TABLE` (sin `IF NOT EXISTS`) fue corrida dos veces contra el mismo destino real durante una verificación: la primera corrida tuvo éxito: la segunda colisionó (`relation already exists`) porque el destino ya tenía las tablas de la corrida anterior.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#destino-no-idempotente-se-limpia-antes-de-cada-corrida-delegar--verificar).

## fixture-persistente-se-aisla-de-la-suite-default (SPEC / VERIFICAR)

Una prueba de extremo a extremo necesitaba, a propósito, dejar un artefacto en disco (una base de datos con datos reales) para que un paso POSTERIOR e independiente (una herramienta de línea de comandos externa) lo consumiera — el patrón contrario al de un test unitario normal, que debe ser hermético y no dejar rastro.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#fixture-persistente-se-aisla-de-la-suite-default-spec--verificar).

## powershell-no-soporta-redireccion-de-stdin (DELEGAR)

Un comando de lanzamiento headless que dependía de `< /dev/null` (obligatorio para que un CLI que espera stdin no cuelgue el lanzamiento) falló al primer intento con `ParserError: The '<' operator is reserved for future use` — no un fallo del modelo delegado ni de la tarea, sino de la shell: PowerShell no implementa el operador `<` de redirección de entrada que la mecánica de lanzamiento requiere.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#powershell-no-soporta-redireccion-de-stdin-delegar).

## claim-de-cobertura-se-verifica-leyendo-el-artefacto-entero-no-su-encabezado (VERIFICAR)

**Corrección de una lección previa de este mismo repo** (`capacidad-generica-con-solo-tests-unitarios-es-deuda-de-verificacion`, ahora retirada): esa entrada afirmaba que el soporte nativo de un tipo de dato especial en una librería (vectores) «solo tenía tests unitarios, sin infraestructura real» — basada en leer el ENCABEZADO de un reporte de experimento («el layer no tiene soporte para este tipo») sin bajar hasta el final del mismo archivo, donde una sección posterior («Post-VectorType validation») se declaraba EXPLÍCITAMENTE que reemplazaba a esa primera («this section supersedes the pre-VectorType summary above») y contenía evidencia real completa (aplicar el esquema, exportar/importar snapshot, verificar equivalencia) contra el motor real con la extensión instalada.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#claim-de-cobertura-se-verifica-leyendo-el-artefacto-entero-no-su-encabezado-verificar).

## fixture-existente-se-extiende-con-alias-de-entorno-no-se-bifurca (SPEC)

Un contrato nuevo necesitaba reproducir, con una variable adicional (un dato nuevo: un embedding vectorial), el mismo fixture de extremo a extremo que un contrato anterior ya había construido y verificado (usuario real, artículos reales vía API real, export contra un Postgres real) — solo que esta vez el destino Postgres era una instancia distinta (con una extensión que la anterior no tenía).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#fixture-existente-se-extiende-con-alias-de-entorno-no-se-bifurca-spec).

## middleware-de-permiso-no-se-reusa-entre-header-y-cookie (SPEC)

Un backend con una API JSON ya auditada (autenticación por header `Authorization`, un middleware de permiso que resuelve la identidad SOLO desde ahí) ganó una capa de UI web nueva con sesión de navegador por cookie.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#middleware-de-permiso-no-se-reusa-entre-header-y-cookie-spec).

## escritura-atada-al-secreto-rompe-la-gestion-por-id (SPEC)

Una función de revocación existente (auditada, correcta para su caso de uso original) buscaba la fila a revocar por el SECRETO en texto plano del recurso (lo hasheaba y comparaba contra el hash almacenado) — diseño razonable cuando el único llamador es el propio poseedor del secreto revocando su credencial.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#escritura-atada-al-secreto-rompe-la-gestion-por-id-spec).

## colision-de-campo-con-struct-embebido-en-vista-compartida (VERIFICAR)

Una página de formulario (creación de un recurso) tenía su propio campo `Email` en el view-model, para preservar el valor ingresado si la validación fallaba — y ese view-model embebía (anónimo) el struct de layout compartido por TODAS las páginas, que YA promueve un campo `Email` (el del usuario de la sesión, usado por la barra de navegación).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#colision-de-campo-con-struct-embebido-en-vista-compartida-verificar).

## go-run-en-windows-deja-binario-huerfano (VERIFICAR)

Al reiniciar manualmente un servidor de prueba en Windows tras aplicar un fix (`go run ./cmd/...` en background, matar el proceso con `taskkill //IM go.exe` antes de relanzar), una verificación posterior seguía mostrando el comportamiento VIEJO — pareciendo que el fix no había funcionado.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#go-run-en-windows-deja-binario-huerfano-verificar).

## infra-existente-se-inspecciona-antes-de-decidir-arquitectura-de-deploy (PLAN)

Al pedirle al orquestador que desplegara un servicio nuevo en un VPS ya en uso por otros servicios, la primera respuesta fue asumir la arquitectura del deploy (proxy reverso, TLS, exposición) y preguntarle al usuario a partir de esa suposición — el usuario respondió literalmente «revisa lo que tienes antes de preguntar».

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#infra-existente-se-inspecciona-antes-de-decidir-arquitectura-de-deploy-plan).

## cache-immutable-sin-version-sirve-stale-tras-redeploy (VERIFICAR)

Un asset estático (una hoja de estilos) se servía con `Cache-Control: public, max-age=31536000, immutable` — una decisión correcta DENTRO de un build (el contenido embebido en un binario compilado es, en efecto, inmutable durante la vida de ESE binario) pero que no consideraba el caso de un REDEPLOY: el binario se reemplazó por uno con contenido nuevo, pero la URL del asset (`/static/app.css`, sin ningún componente que cambiara) siguió siendo la misma, así que un CDN delante del origin (con `immutable` diciéndole exactamente que nunca hace falta revalidar) siguió sirviendo, indefinidamente, la respuesta cacheada del build ANTERIOR — el usuario reportó "no carga bien" horas después de un deploy que localmente y por los tests HTTP daba todo verde.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#cache-immutable-sin-version-sirve-stale-tras-redeploy-verificar).

## verificacion-de-ui-por-geometria-no-por-status-http (VERIFICAR)

Tras un deploy que rompió visualmente un layout (una barra lateral que debía ocupar una columna a la izquierda terminó apilada como una franja horizontal arriba, por el bug de caché stale descrito en `cache-immutable-sin-version-sirve-stale-tras-redeploy`), la verificación inicial post-deploy (códigos de estado HTTP 200 en todas las rutas, presencia de las clases CSS esperadas en el HTML servido) NO detectó el problema — todo eso era cierto y a la vez la UI se veía rota, porque el problema vivía en el CSS cacheado, no en el HTML ni en las rutas.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#verificacion-de-ui-por-geometria-no-por-status-http-verificar).

## aplicar-esquema-todo-o-nada-rompe-el-primer-cambio-incremental-tras-deploy (VERIFICAR)

Una función de bootstrap de esquema («aplicar el esquema canónico si no está ya aplicado») decidía su idempotencia con una sola pregunta binaria: ¿está CADA tabla del esquema canónico ya presente?

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#aplicar-esquema-todo-o-nada-rompe-el-primer-cambio-incremental-tras-deploy-verificar).

## metadata-de-esquema-cacheada-se-reescribe-completa-tras-un-apply-parcial (VERIFICAR)

Al corregir el bug de `aplicar-esquema-todo-o-nada-rompe-el-primer-cambio-incremental-tras-deploy` filtrando la aplicación a solo las tablas ausentes, el test de regresión que probaba exactamente ese escenario (crear la tabla faltante, luego confirmar que las preexistentes seguían presentes) siguió fallando — con las tablas preexistentes reportadas como "ausentes" DESPUÉS del fix.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#metadata-de-esquema-cacheada-se-reescribe-completa-tras-un-apply-parcial-verificar).

## verificar-migracion-de-esquema-contra-copia-real-antes-de-tocar-produccion (VERIFICAR / CIERRE)

Antes de desplegar un cambio que modifica cómo se aplica el esquema de una base de datos ya en producción con datos reales, se descargó por SFTP una copia REAL del archivo de base de datos de producción, y el binario nuevo se corrió contra esa copia local dos veces seguidas (un arranque que ejercita el camino incremental agregando la tabla nueva, y un reinicio inmediato que ejercita el camino "ya todo aplicado") — confirmando que los datos preexistentes seguían íntegros y que ninguna de las dos corridas fallaba, ANTES de subir nada al servidor real.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#verificar-migracion-de-esquema-contra-copia-real-antes-de-tocar-produccion-verificar--cierre).

## modelo-de-referencia-externo-no-se-traduce-a-ciegas-cuando-el-proyecto-ya-eligio-otro (SPEC)

Se pidió replicar una capacidad de un sistema de referencia conocido (relación entre contenido y términos de clasificación, con el modelo de datos exacto que ese sistema de referencia usa: una tabla de relación POLIMÓRFICA única, viable ahí porque TODOS sus tipos de contenido viven en una sola tabla física).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#modelo-de-referencia-externo-no-se-traduce-a-ciegas-cuando-el-proyecto-ya-eligio-otro-spec).

## agregar-permiso-nuevo-se-justifica-por-ausencia-semantica-no-por-conveniencia (SPEC)

Tras una cadena larga de contratos donde CADA vez que hacía falta gatear una ruta nueva por permiso, el permiso correcto YA EXISTÍA en el catálogo fijo (una acción de contenido encajaba en un permiso de contenido genérico, una acción de cuentas encajaba en el permiso de gestión de usuarios) — reforzando el hábito de "nunca agregar, siempre reusar" — apareció una capacidad genuinamente nueva (administrar un catálogo de clasificación) que NINGÚN permiso existente cubría semánticamente: los permisos de contenido gobiernan piezas de contenido individuales, no el vocabulario compartido bajo el que se archivan; los permisos de cuentas son un dominio distinto.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#agregar-permiso-nuevo-se-justifica-por-ausencia-semantica-no-por-conveniencia-spec).

## verificar-un-deploy-con-lecturas-no-prueba-que-el-sistema-funcione (VERIFICAR / CIERRE)

Un servicio estuvo desplegado en producción durante varias entregas sucesivas, cada una verificada tras su deploy con la misma batería: login real, y peticiones de LECTURA a todas las rutas (las de datos y las de interfaz), todas respondiendo correctamente.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#verificar-un-deploy-con-lecturas-no-prueba-que-el-sistema-funcione-verificar--cierre).

## capacidad-de-configuracion-sin-via-de-escritura-en-el-producto (SPEC)

Un sistema con control de acceso basado en roles definía dos catálogos fijos en código (los roles, y los permisos) y una tabla de unión que decide qué puede hacer realmente cada rol.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#capacidad-de-configuracion-sin-via-de-escritura-en-el-producto-spec).

## invariante-que-se-puede-olvidar-se-vuelve-imposible-o-ruidosa (SPEC)

Una capa de presentación necesitaba que CADA página autenticada mostrara un dato compartido (una lista que vive en la base y cambia en runtime).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#invariante-que-se-puede-olvidar-se-vuelve-imposible-o-ruidosa-spec).

## reproducir-lo-que-el-cliente-real-envia-no-lo-que-uno-cree-que-envia (VERIFICAR)

Al verificar el manejo de un control de formulario con semántica traicionera (una casilla de verificación sin marcar sencillamente NO se envía en el envío de un formulario, así que una capa que interpreta "campo ausente" como "sin valor" guardaría nulo en vez de falso), el orquestador armó la petición A MANO con los campos que le parecían pertinentes y obtuvo, en efecto, un valor nulo — a un paso de reportar un defecto inexistente.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#reproducir-lo-que-el-cliente-real-envia-no-lo-que-uno-cree-que-envia-verificar).

## capacidad-que-puede-revocarse-a-si-misma-necesita-guarda-sobre-el-estado-resultante (SPEC)

Se construyó la capacidad de administrar qué permisos tiene cada rol — una capacidad gateada, ella misma, por uno de esos permisos.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#capacidad-que-puede-revocarse-a-si-misma-necesita-guarda-sobre-el-estado-resultante-spec).

## una-bateria-de-casos-sobre-estado-compartido-se-contamina-a-si-misma (VERIFICAR)

Al verificar una guarda de autorización con una batería de casos ejecutados en secuencia contra el MISMO servidor y la MISMA base, el segundo caso devolvió un resultado inesperado —parecía un fallo de la implementación— hasta que se inspeccionó el estado real de la base: el caso ANTERIOR de la propia batería había mutado justamente el dato del que dependía el caso siguiente (había vaciado los permisos del rol que servía de respaldo).

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-bateria-de-casos-sobre-estado-compartido-se-contamina-a-si-misma-verificar).

## migracion-manual-debe-invalidar-la-cache-que-el-sistema-prefiere (VERIFICAR / CIERRE)

Un despliegue cambió el esquema de nombres de ciertas tablas, y la instancia en producción tenía una tabla con el nombre viejo.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#migracion-manual-debe-invalidar-la-cache-que-el-sistema-prefiere-verificar--cierre).

## orden-de-un-deploy-con-migracion-minimiza-la-ventana-de-caida (CIERRE)

En un despliegue que requería detener el servicio para migrar datos, el orden ejecutado fue: detener el servicio → migrar → compilar el binario → subirlo → arrancar.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#orden-de-un-deploy-con-migracion-minimiza-la-ventana-de-caida-cierre).

## una-leccion-que-reincide-pide-un-artefacto-operativo-no-mas-documentacion (CIERRE)

Una misma trampa técnica (una caché de esquema que el sistema prefiere por sobre el estado real, y que hay que invalidar a mano tras ciertos cambios) causó TRES incidentes en el mismo proyecto.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-leccion-que-reincide-pide-un-artefacto-operativo-no-mas-documentacion-cierre).

## una-limitacion-de-una-dependencia-propia-se-arregla-en-la-dependencia (DEFINIR / PLAN)

Una fase de producto declaró fuera de alcance una capacidad deseable (editar la forma de una estructura ya creada) por una limitación concreta y verificada de una biblioteca de la que el producto depende: esa biblioteca no expresaba la operación necesaria.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-limitacion-de-una-dependencia-propia-se-arregla-en-la-dependencia-definir--plan).

## una-trampa-reincidente-se-convierte-en-criterio-de-aceptacion (SPEC / VERIFICAR)

La misma caché de esquema que ya había causado tres incidentes en un proyecto —una metadata propia que la lógica de inspección prefiere por sobre el catálogo físico— volvió a aparecer al implementar una operación nueva que borra estructuras.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-trampa-reincidente-se-convierte-en-criterio-de-aceptacion-spec--verificar).

## una-capa-de-compatibilidad-documenta-la-divergencia-no-la-fuerza (SPEC)

Una biblioteca cuyo propósito declarado es que el mismo esquema se comporte igual en dos motores distintos incorporó una operación nueva.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capa-de-compatibilidad-documenta-la-divergencia-no-la-fuerza-spec).

## publicar-una-version-no-es-tagearla-sino-verificarla-como-consumidor (CIERRE)

Al publicar una versión nueva de una biblioteca para que otro proyecto la consumiera, todos los pasos del lado del productor salieron bien: el código commiteado, el historial publicado en el repositorio de destino, el tag creado y visible en la web con sus notas.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#publicar-una-version-no-es-tagearla-sino-verificarla-como-consumidor-cierre).

## una-capacidad-destructiva-se-verifica-en-produccion-con-una-operacion-que-es-su-propio-inverso (VERIFICAR / CIERRE)

Un despliegue incorporó una capacidad que reconstruye una estructura de datos entera: puede agregar, renombrar y ELIMINAR partes de ella, con pérdida irreversible en el último caso.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capacidad-destructiva-se-verifica-en-produccion-con-una-operacion-que-es-su-propio-inverso-verificar--cierre).

## una-verificacion-que-necesita-identidad-se-emite-una-efimera-no-se-pide-la-del-humano (CIERRE)

Al llegar al paso de verificación de un despliegue —el que exige una escritura real, autenticada, que atraviese la capa de autorización— faltaba lo más básico: la credencial.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-verificacion-que-necesita-identidad-se-emite-una-efimera-no-se-pide-la-del-humano-cierre).

## el-desvio-que-tuviste-que-improvisar-siguiendo-un-runbook-es-el-bug-del-runbook (CIERRE)

Un proyecto convirtió una lección reincidente en un runbook operativo — la respuesta correcta a "documentar la trampa una tercera vez no la evita".

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#el-desvio-que-tuviste-que-improvisar-siguiendo-un-runbook-es-el-bug-del-runbook-cierre).

## antes-de-escribir-un-artefacto-operativo-busca-si-ya-existe-y-envejecio (CIERRE)

Tras verificar de punta a punta una capacidad del sistema, se decidió capturar los pasos en un runbook — la conducta correcta según una lección previa de este mismo repositorio.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#antes-de-escribir-un-artefacto-operativo-busca-si-ya-existe-y-envejecio-cierre).

## una-promesa-heredada-de-un-componente-se-verifica-al-nivel-del-sistema (DEFINIR / VERIFICAR)

Un producto se construyó sobre una biblioteca cuyo propósito declarado era permitir arrancar con un motor de datos barato y migrar a uno grande "sin reescribir la aplicación".

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-promesa-heredada-de-un-componente-se-verifica-al-nivel-del-sistema-definir--verificar).

## un-test-de-comparacion-cuyos-datos-no-pueden-diferir-no-prueba-nada (VERIFICAR)

Para garantizar que un componente se comportara igual en dos motores distintos se construyó una batería que ejecuta el mismo guion contra los dos y compara los resultados línea por línea.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-test-de-comparacion-cuyos-datos-no-pueden-diferir-no-prueba-nada-verificar).

## el-acoplamiento-que-ningun-compilador-atrapa-es-el-que-hay-que-buscar-a-mano (VERIFICAR)

Al portar una aplicación de un motor de datos a otro, la mayor parte de los problemas se anuncian solos: la sintaxis de los marcadores de parámetro cambia y el driver falla, los tipos no coinciden y el compilador protesta.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#el-acoplamiento-que-ningun-compilador-atrapa-es-el-que-hay-que-buscar-a-mano-verificar).

## la-instruccion-del-orquestador-es-una-hipotesis-y-el-implementador-debe-medirla (DELEGAR)

Al revisar un trabajo, el orquestador detectó un defecto real —una configuración inválida producía un fallo ruidoso en un sistema y desaparecía en el otro— y le indicó al implementador cómo arreglarlo, con una solución concreta que había verificado a medias.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#la-instruccion-del-orquestador-es-una-hipotesis-y-el-implementador-debe-medirla-delegar).

## una-capacidad-opcional-puede-imponer-un-requisito-de-infraestructura-obligatorio (DEFINIR / CIERRE)

Un sistema incorporó una capacidad avanzada que solo algunos usuarios necesitarían, y la modeló con cuidado como opcional: el dato es **admite-ausencia**, así que una instalación que nunca la use no guarda nada en ese campo y no paga ningún costo.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capacidad-opcional-puede-imponer-un-requisito-de-infraestructura-obligatorio-definir--cierre).

## verificar-las-dos-mitades-por-separado-no-verifica-la-composicion (VERIFICAR)

Un sistema prometía una operación compuesta: trasladarse de un motor de datos a otro **sin dejar de atender pedidos**.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#verificar-las-dos-mitades-por-separado-no-verifica-la-composicion-verificar).

## una-capacidad-que-nunca-operaste-solo-se-entiende-ensayandola (VERIFICAR / CIERRE)

Un sistema dependía de una herramienta que ofrecía una operación descrita como "migrar **sin ventana de corte**".

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capacidad-que-nunca-operaste-solo-se-entiende-ensayandola-verificar--cierre).

## el-titulo-con-que-anotaste-un-hueco-es-una-hipotesis-no-una-especificacion (DEFINIR)

Un proyecto llevaba una lista de huecos conocidos, cada uno anotado en el momento de descubrirlo con la evidencia de cómo había aparecido — buena práctica, y la lista funcionó: nadie los redescubrió desde cero.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#el-titulo-con-que-anotaste-un-hueco-es-una-hipotesis-no-una-especificacion-definir).

## el-valor-por-defecto-de-una-capacidad-nueva-debe-ser-el-statu-quo (SPEC)

Un sistema hizo opcional una capacidad que hasta entonces era obligatoria, con una bandera de configuración y —correctamente— una guarda que impide arrancar si la configuración contradice lo que la instalación tiene realmente aplicado, porque la elección no es reversible.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#el-valor-por-defecto-de-una-capacidad-nueva-debe-ser-el-statu-quo-spec).

## una-medicion-hecha-en-otra-topologia-mide-la-topologia-no-el-sistema (VERIFICAR)

Verificando un arreglo, se midió cuánto tardaba el sistema en fallar cuando su base de datos no estaba disponible.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-medicion-hecha-en-otra-topologia-mide-la-topologia-no-el-sistema-verificar).

## la-misma-clasificacion-de-errores-necesita-polaridad-opuesta-segun-la-capa (SPEC)

Un sistema arregló que un fallo de infraestructura se disfrazara de error del usuario: cuando la base de datos no respondía, la autenticación contestaba "credenciales inválidas".

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#la-misma-clasificacion-de-errores-necesita-polaridad-opuesta-segun-la-capa-spec).

## una-confirmacion-util-exige-un-dato-que-solo-se-obtiene-preguntando (SPEC)

Un sistema incorporó su operación más destructiva: borrar una estructura de datos completa junto con todo su contenido.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-confirmacion-util-exige-un-dato-que-solo-se-obtiene-preguntando-spec).

## invertir-una-decision-de-alcance-exige-registrar-que-la-estas-invirtiendo (DEFINIR)

Un proyecto llevaba, en su documento de definición, una lista de capacidades declaradas fuera de alcance.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#invertir-una-decision-de-alcance-exige-registrar-que-la-estas-invirtiendo-definir).

## una-capacidad-nueva-puede-tener-un-precio-y-conviene-cotizarlo-antes-de-construir (DEFINIR)

Se pidió construir una capacidad que estaba declarada fuera de alcance: relacionar entre sí las estructuras que los usuarios definen en tiempo de ejecución.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capacidad-nueva-puede-tener-un-precio-y-conviene-cotizarlo-antes-de-construir-definir).

## un-orden-implicito-que-nadie-valida-es-una-bomba-de-tiempo-en-el-export (SPEC / VERIFICAR)

Un sistema compone la definición de su almacenamiento a partir de partes fijas y partes que los usuarios crean en tiempo de ejecución, y publica esa definición para poder recrearla en otro motor.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-orden-implicito-que-nadie-valida-es-una-bomba-de-tiempo-en-el-export-spec--verificar).

## un-hueco-conocido-se-deja-asertado-para-que-una-prueba-obligue-a-cerrarlo (VERIFICAR / CIERRE)

Un trabajo cerró cinco de seis casos de un problema; el sexto dependía de un defecto en una biblioteca de la que el proyecto depende, y no se podía arreglar desde el consumidor sin violar sus propias reglas.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-hueco-conocido-se-deja-asertado-para-que-una-prueba-obligue-a-cerrarlo-verificar--cierre).

## las-sondas-de-verificacion-tambien-dejan-estado (VERIFICAR)

Al verificar el trabajo de otro, quien orquestaba escribió varias sondas desechables: programas pequeños que se conectan al sistema real, provocan una condición y miden el resultado.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#las-sondas-de-verificacion-tambien-dejan-estado-verificar).

## un-aislamiento-que-depende-de-la-higiene-compartida-no-es-aislamiento (SPEC / VERIFICAR)

Una batería de pruebas contra un almacén compartido se aislaba creando su propio espacio de nombres y resolviendo ahí primero, con el espacio común como respaldo.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-aislamiento-que-depende-de-la-higiene-compartida-no-es-aislamiento-spec--verificar).

## una-prueba-que-depende-de-una-variable-no-documentada-nunca-corre (VERIFICAR / CIERRE)

Un sistema hizo opcional una capacidad que antes era obligatoria, y la única forma honesta de probar la opción es contra un entorno que **no ofrezca** esa capacidad — un entorno que no se puede simular, porque la capacidad está o no está.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-prueba-que-depende-de-una-variable-no-documentada-nunca-corre-verificar--cierre).

## una-punta-anotada-como-comodidad-se-mide-antes-de-dimensionarla (DEFINIR / SPEC)

Un trabajo anterior había cerrado con una punta abierta, anotada con honestidad y en una línea: *el formulario del panel no ofrece un control para elegir el destino de la relación; el valor se manda por la interfaz programática*.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-punta-anotada-como-comodidad-se-mide-antes-de-dimensionarla-definir--spec).

## una-verificacion-que-pasa-con-el-artefacto-viejo-no-verifica-el-despliegue (VERIFICAR)

Quien orquestaba desplegó una versión nueva a un servidor: subió el artefacto compilado, lo movió a su lugar, reinició el servicio y comprobó los dos endpoints de salud.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-verificacion-que-pasa-con-el-artefacto-viejo-no-verifica-el-despliegue-verificar).

## seguir-un-runbook-de-memoria-es-no-seguirlo (VERIFICAR / CIERRE)

El procedimiento operativo del despliegue estaba escrito, era bueno, y lo había escrito la misma persona que ahora desplegaba — precisamente porque una lección anterior había demostrado que ese conocimiento sirve donde se ejecuta y no donde se archiva.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#seguir-un-runbook-de-memoria-es-no-seguirlo-verificar--cierre).

## declarar-un-residuo-no-lo-registra (CIERRE)

Al entregar un trabajo, quien lo implementó declaró con precisión tres cosas que no había cubierto.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#declarar-un-residuo-no-lo-registra-cierre).

## instalar-en-limpio-siguiendo-solo-el-manual-encuentra-lo-que-el-autor-ya-no-ve (VERIFICAR / CIERRE)

Un sistema llevaba semanas de trabajo verificado paso a paso, con su promesa central cumplida y medida.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#instalar-en-limpio-siguiendo-solo-el-manual-encuentra-lo-que-el-autor-ya-no-ve-verificar--cierre).

## un-gate-con-un-limite-que-el-sistema-supero-no-puede-dar-verde (VERIFICAR)

Un proyecto tenía un guion de cierre que ejecutaba su batería más cara y decidía si el resultado era aceptable: la batería tiene un fallo intencional y documentado, así que el guion daba éxito solo si ese fallo —y ningún otro— aparecía.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-gate-con-un-limite-que-el-sistema-supero-no-puede-dar-verde-verificar).

## corregir-una-promesa-exige-barrer-todas-las-superficies-donde-se-la-dijo (CIERRE)

Un ensayo operativo midió que una capacidad no cumplía lo que su nombre prometía: no era "sin interrupción", era "con una interrupción mucho más corta".

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#corregir-una-promesa-exige-barrer-todas-las-superficies-donde-se-la-dijo-cierre).

## leer-por-fuera-de-la-capa-de-portabilidad-reintroduce-la-divergencia-que-la-capa-elimina (SPEC)

Un sistema se apoya en una capa cuyo trabajo declarado es que dos motores de almacenamiento distintos se comporten igual: declara el esquema una vez, lo compila a los dos, y al leer devuelve los valores ya canonizados a la forma declarada.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#leer-por-fuera-de-la-capa-de-portabilidad-reintroduce-la-divergencia-que-la-capa-elimina-spec).

## una-novedad-puede-reabrir-un-defecto-cerrado-por-un-camino-nuevo (VERIFICAR / CIERRE)

Un panel permitía que una fila apuntara a otra mediante un control que elegía el destino; como ese control solo ofrecía las cien filas más recientes, una fila vieja resultaba inalcanzable y se le sumó un buscador que recargaba las opciones consultando la base.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-novedad-puede-reabrir-un-defecto-cerrado-por-un-camino-nuevo-verificar--cierre).

## una-capa-de-portabilidad-que-delega-la-semantica-al-motor-no-porta (SPEC / DEFINIR)

Una capa cuyo propósito declarado es que dos motores de almacenamiento se comporten igual ofrecía un operador de coincidencia de texto, y lo implementaba **traduciéndolo al operador equivalente de cada motor**.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-capa-de-portabilidad-que-delega-la-semantica-al-motor-no-porta-spec--definir).

## bajo-un-regimen-sin-alter-una-tabla-nueva-llega-sola-y-una-columna-nueva-no (SPEC)

Un sistema cuya capa de almacenamiento **no puede alterar tablas existentes** —crea las que faltan al arrancar y nunca toca las que ya están, y esa restricción es justamente lo que hace seguro cada reinicio— necesitó registrar un dato nuevo sobre entidades que ya existían.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#bajo-un-regimen-sin-alter-una-tabla-nueva-llega-sola-y-una-columna-nueva-no-spec).

## una-medicion-correcta-no-autoriza-la-generalizacion-que-la-acompana (VERIFICAR / DELEGAR)

Al entregar un trabajo, quien lo implementó explicó por qué había dejado afuera una parte, y lo hizo bien: con una medición real y reproducible, no con una opinión.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-medicion-correcta-no-autoriza-la-generalizacion-que-la-acompana-verificar--delegar).

## donde-pones-el-rechazo-decide-si-rompes-la-escritura-o-tambien-la-lectura (SPEC)

Una capa decidió endurecer una regla: cierta construcción que antes aceptaba pasaba a rechazarse, porque se había medido que producía comportamientos distintos según el motor de almacenamiento.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#donde-pones-el-rechazo-decide-si-rompes-la-escritura-o-tambien-la-lectura-spec).

## una-regla-que-se-evalua-al-escribir-es-mas-grave-que-una-que-se-evalua-al-leer (DEFINIR / SPEC)

El mismo defecto —una construcción que se comporta distinto en cada motor de almacenamiento— apareció en dos lugares de la misma capa, y el equipo lo trató primero en el que dolía más obviamente: el de las consultas.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-regla-que-se-evalua-al-escribir-es-mas-grave-que-una-que-se-evalua-al-leer-definir--spec).

## la-verificacion-la-elige-lo-que-el-cambio-gobierna-no-el-tamano-del-diff (VERIFICAR)

Un proyecto subió la versión de una biblioteca de la que depende.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#la-verificacion-la-elige-lo-que-el-cambio-gobierna-no-el-tamano-del-diff-verificar).

## una-comparacion-entre-sistemas-debe-comparar-solo-la-propiedad-bajo-prueba (VERIFICAR)

Al verificar que un operador nuevo devolviera exactamente lo mismo en dos sistemas de almacenamiento distintos, quien orquestaba escribió una sonda propia —bien: no confiar en la del implementador— que consultaba ambos y comparaba los resultados como texto.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#una-comparacion-entre-sistemas-debe-comparar-solo-la-propiedad-bajo-prueba-verificar).

## cobertura-parcial-honesta-vale-mas-que-completa-falsa (VERIFICAR / CIERRE)

El dominio de Seguridad de esta plantilla (findings sellados por un motor vendorizado, gobernados por el mismo motor de reglas declarativo que los demás dominios) se corrió por primera vez contra un blanco real y grande, no contra los fixtures sintéticos con los que se había diseñado y probado.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#cobertura-parcial-honesta-vale-mas-que-completa-falsa-verificar--cierre).

## dos-dominios-de-capa-3-que-nunca-se-hablan-convergen-en-el-mismo-riesgo (VERIFICAR)

Primera corrida de los 7 dominios de Capa 3 (security, compliance, privacy, accessibility, dependency-eol, observability, test-coverage) juntos contra un target real y no sintético — una app de notificaciones push (Cloudflare Workers + D1 + Web Push/VAPID) construida para ese fin.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#dos-dominios-de-capa-3-que-nunca-se-hablan-convergen-en-el-mismo-riesgo-verificar).

## un-hallazgo-arreglado-en-el-codigo-sigue-abierto-si-el-artefacto-no-se-resella (CIERRE / VERIFICAR)

Sobre el mismo target real de Capa 3: dos de sus hallazgos críticos (registro de admin sin autenticación, dependencia con licencia `UNLICENSED` bundleada en el Worker desplegado) se corrigieron en el código, verificados con evidencia ejecutada — curl real devolviendo 403/403/201 contra los tres casos de la regla nueva; `wrangler deploy --dry-run` confirmando que la dependencia problemática ya no aparece ni una vez en el bundle real.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#un-hallazgo-arreglado-en-el-codigo-sigue-abierto-si-el-artefacto-no-se-resella-cierre--verificar).

## el-fix-obvio-de-un-hallazgo-de-capa-3-puede-romper-en-silencio-lo-que-arregla (VERIFICAR)

Al remediar el hallazgo crítico de compliance (una dependencia transitiva de producción con licencia `UNLICENSED` bundleada en el Worker), la corrección que parecía evidente era subir esa dependencia a una versión más nueva con licencia MIT — el propio finding lo sugería como remediación recomendada.

[Relato y evidencia completos](../docs/reports/ARCHIVO-CASOS-REALES.md#el-fix-obvio-de-un-hallazgo-de-capa-3-puede-romper-en-silencio-lo-que-arregla-verificar).
