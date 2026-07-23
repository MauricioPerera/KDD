---
type: 'Concept'
title: 'Metodología de ejecución por contratos'
description: 'Proceso operativo de nivel proyecto: contratos de ejecución en specs/, delegación a agentes efímeros, verificación por artefacto y reportes en docs/reports/.'
tags: ['metodologia', 'ccdd', 'proceso', 'ejecucion']
---

# Metodología de ejecución por contratos

Capa de nivel **proyecto** que complementa los task contracts de
[Contratos de Desarrollo](./contracts/): agrupa tareas en **contratos de ejecución**
numerados, cada uno con criterios de aceptación verificables por máquina. Probada en
producción antes de formalizarse en esta plantilla (28 contratos consecutivos en el
proyecto donde nació la metodología — cifra de ese momento, no un conteo vivo de este repo).

## Capas

| Capa | Dónde | Alcance | Evidencia |
|---|---|---|---|
| Contrato de ejecución | `specs/CONTRACT-NN-<slug>.md` | un objetivo del proyecto (1-N tareas) | `docs/reports/CONTRACT-NN-REPORT.md` (en-repo) |
| Task contract (CCDD) | `knowledge/contracts/<task>.md` | una tarea de código delegada | `.agents/logs/<task>-REPORT.md` (local, gitignorado) |

Plantillas: `specs/TEMPLATE-CONTRACT.md` y `docs/reports/TEMPLATE-REPORT.md`. El
«Checklist antes de delegar» de la plantilla es la forma **operativa** de las reglas
RECON / red-team / perímetro / aborto de este nodo; este nodo es la fuente normativa —
ante divergencia manda la metodología y el checklist se re-alinea.

## DEFINIR (opcional, antes de PLAN)

`PLAN` (abajo) asume que ya existe un «pedido» convertible en tareas atómicas. Cuando el
proyecto todavía no está elegido, o está elegido pero su forma (arquitectura, alcance,
stack) no cerró, ese pedido no existe todavía — **DEFINIR** es el paso que lo produce.
Se hace UNA vez por proyecto (no por tarea), en conversación con un humano, y termina en
un único artefacto: `DEFINITION.md` en la raíz (plantilla: `TEMPLATE-DEFINITION.md`).
`DEFINITION.md` no es un nodo OKF ni lo valida ningún gate — es documentación previa a
que exista el primer contrato. Proceso completo, reglas y estilo:
[skill `kdd-definir`](../.agents/skills/kdd-definir/SKILL.md) — o, sin agente propio,
el GPT [Arquitecto de Definición KDD](https://chatgpt.com/g/g-6a566a4ad3248191821751cd14800573-arquitecto-de-definicion-kdd)
configurado con el mismo system prompt. Con `DEFINITION.md` cerrado, recién ahí arranca
`PLAN`.

## Proceso

1. **PLAN** — convertir el pedido en contrato de ejecución con tareas atómicas; mostrarlo
   antes de disparar trabajo pesado.
   **RECON NEEDED:** toda suposición del plan que no esté verificada (comando real de la
   suite, workflows del CI — incluidos los condicionales por diff que quizá nunca
   corrieron —, dependencias instaladas, lenguajes soportados por el gate) se lista con
   el check exacto que la resuelve, y esos checks se corren ANTES de redactar specs.
   Una suposición sin check es una re-delegación futura.
   **Las afirmaciones de estado del entorno DENTRO de la spec son suposiciones del plan**
   y siguen la misma regla: si el check no se corrió, la spec no afirma — condiciona
   («si falta X, instalarlo con Y»). Un fallo ambiental se parece a una «causa
   preexistente» y dispara un ABORTAR SI legítimo, quemando la delegación
   ([caso real](./casos-reales.md#entorno-afirmado-plan--recon)).
   La misma regla aplica a la EXISTENCIA de recursos nombrados: un pedido de «crear X»
   (repo, worker, base de datos) es en realidad «asegurar que X exista con este
   contenido». Verificar primero con un check barato (`gh repo view`, listado del
   proveedor, `ls`); si X ya existe, inspeccionar su contenido y reconciliar con lo
   pedido — nunca crear ni forzar por encima
   ([caso real](./casos-reales.md#crear-sobre-existente-plan--recon)).
   **Cuando el espacio de "qué falta hacer" es grande y abstracto, un artefacto real
   representativo corrido por el pipeline real prioriza más rápido que seguir
   clasificando en la cabeza** — un único esquema/caso de uso escrito a mano encontró en
   un pase gaps concretos que sesiones previas de categorización no habían señalado
   ([caso real](./casos-reales.md#artefacto-real-encuentra-gaps-que-la-clasificacion-abstracta-no-plan)).
2. **SPEC por tarea** — autocontenida y por OBJETIVO (estado final + definición de hecho
   con comando y resultado esperado), no por pasos. El agente efímero no tiene memoria:
   todo el contexto va en la spec (o se ensambla con el ensamblador de contexto).
   Los **tests congelados** del task contract los autora el orquestador ANTES de delegar,
   como oráculo independiente; el agente efímero que implementa no los toca ni los reescribe.
   **Red-team de la definición de hecho antes de delegar:** preguntar «¿cómo podría
   cumplirse este comando sin cumplir la intención?» y parchear la definición con lo que
   aparezca. Y la pregunta inversa: «¿algún check contradice otra orden de la spec?» —
   un check que choca con una orden propia obliga al agente a un judgment call que la
   spec prometía no dejarle. Para specs de **exponer/subir un método a una fachada o API
   pública**, dos preguntas más: «¿qué camino PÚBLICO consume esto?» — si la respuesta es
   «ninguno», la tarea real incluye cablear el consumidor o la feature es decorativa
   (contrato cumplido, tests verdes, valor cero) — y «¿cuál es el tipo/contenedor EXACTO
   de retorno en CADA modo?» — fijarlo en la definición de hecho (p. ej.
   `Array.isArray(...) === true` en todos los modos), no solo la shape del elemento.
   Las cinco clases verificadas de «comando cumplido sin cumplir la intención» que este
   paso previene están en [casos reales](./casos-reales.md#hecho-sin-intencion-spec--red-team-de-la-definición-de-hecho).
   Complemento verificado: exigir sección de **trade-offs** en el reporte del agente es
   el detector más barato de estas clases — se cazan leyendo esa sección + el diff
   puntual de la zona, nunca el diff entero.
   **Los nombres de entregables se verifican como libres antes de asignarlos** (`ls` del
   directorio destino al redactar la spec) y toda spec lleva la cláusula «si el archivo ya
   existe, no lo sobrescribas» ([caso real](./casos-reales.md#colision-de-entregables-spec)).
   **Si el orquestador conoce una tensión de diseño fundamental de la tarea, va EN la
   spec** — con dirección candidata, requisitos innegociables verificables y cláusula de
   honestidad, dejando el CÓMO libre; ocultarla condena al agente a iterar a ciegas
   ([caso real](./casos-reales.md#tension-de-diseno-en-la-spec-spec)).
   **Cambio de formato en un artefacto persistente** (journal, wire format, schema): la
   spec pregunta «¿qué pasa con los datos in-flight de la versión vieja?» — el fix y su
   contrato de upgrade son la misma tarea
   ([caso real](./casos-reales.md#formato-persistente-sin-contrato-de-upgrade-spec--cierre)).
   Y si el fix incluye una **nota de upgrade**, la spec exige EJECUTAR el escenario
   legado que la nota describe — construir el artefacto viejo cuesta minutos; una nota
   con outcomes narrados y no ejecutados es un claim sin evidencia
   ([caso real](./casos-reales.md#nota-de-upgrade-no-ejecutada-spec--verificar)).
   **Una clase de fallo cazada dos veces se convierte en cláusula estándar** de toda spec
   que toque esa zona — prevenir en la spec es más barato que re-cazar en cada
   verificación ([caso real](./casos-reales.md#clase-cazada-a-clausula-de-spec-spec)).
   **Si el comportamiento a cambiar está descrito en un contrato documentado, docs, código
   y asserts se actualizan en la MISMA tarea** — cero claims que el artefacto no cumpla
   ([caso real](./casos-reales.md#contrato-documentado-cambia-junto-spec--verificar)).
   **En cambios que prometen preservar comportamiento** (refactor, unificación,
   migración), las divergencias deliberadas se enumeran explícitas y cerradas: «idéntico
   salvo exactamente esto» es verificable, «básicamente igual» no
   ([caso real](./casos-reales.md#excepcion-unica-declarada-spec)).
   **Al agregar a un compilador/gramática compartida un nodo con una propiedad atípica**
   (no determinismo, efectos secundarios, coste variable), la spec pregunta «¿en qué
   OTROS contextos alcanzables por el compilador aparece esto, más allá de los que
   documenté como intención?» — un compilador genérico no distingue intención de alcance
   ([caso real](./casos-reales.md#propiedad-atipica-en-compilador-generico-spec)).
3. **DELEGAR** — un agente efímero por tarea. Tareas que compartan archivos → secuenciales.
   Las tareas en **paralelo** deben declarar en su spec el conjunto de archivos que tocan,
   y ese conjunto debe ser **disjunto** respecto a otras tareas corriendo al mismo tiempo.
   **Una credencial efímera puede viajar al agente delegado** solo si muere con la infra,
   la spec ordena el enmascarado explícito, y el orquestador verifica con grep cero
   ocurrencias literales en los entregables
   ([caso real](./casos-reales.md#credencial-efimera-a-delegados-delegar)).
   **Ante una muerte del agente a mitad de tarea** (cuota, crash): triar el disco — lo
   verde sobrevive verificado y CERCADO; solo lo faltante se re-delega, idealmente por un
   mecanismo alternativo que no comparta la causa de la muerte
   ([caso real](./casos-reales.md#rescate-hibrido-por-cuota-delegar--recuperación)).
   **Si se delega investigar la viabilidad de algo riesgoso aceptando BLOQUEADO como
   resultado válido, y el propio EXPERIMENTO puede reproducir ese riesgo** (una prueba de
   terminación que puede no terminar), la spec le da a la investigación su propio arnés
   de seguridad (timeout, límite del lado servidor, cleanup garantizado) — distinto del
   arnés de la feature que se investiga
   ([caso real](./casos-reales.md#investigacion-bloqueada-necesita-arnes-delegar)).
4. **VERIFICAR por artefacto** — la palabra del agente no cuenta: solo salidas reales de
   comandos (validador, tests). El orquestador re-corre los comandos antes de integrar.
   Todo trade-off declarado por el agente se inspecciona puntualmente.
   Si el orquestador tiene el gate CCDD disponible en su propia sesión, es más barato y
   estable que el orquestador corra el gate/validador sobre el artefacto entregado, en vez
   de exigirle al agente efímero que lo corra (menos superficie de entorno en el agente
   efímero, mismo veredicto determinista). No aplica cuando la tarea requiere que el propio
   agente itere contra el gate (funciones nuevas complejas que necesitan varias vueltas).
   **El orden es verificar → limpiar, nunca limpiar → verificar:** el artefacto de prueba
   (credencial canario, fixture, archivo temporal) se conserva hasta CONFIRMAR el estado
   final esperado; borrarlo antes destruye la única evidencia re-testeable. Y en sistemas
   de propagación eventual (secrets, DNS, caches), un resultado inmediato contrario al
   esperado no es fallo: se re-verifica con reintentos espaciados antes de concluir
   ([caso real](./casos-reales.md#verificar-antes-de-limpiar-verificar)).
   **Un fix a una función que un lado de un contrato bilateral produce y otro consume
   (firmar/verificar, escribir/leer, serializar/deserializar) no está verificado con solo
   probar el lado que tocaste:** grep del nombre de la función en todo el repo antes de dar
   el fix por completo — "mis tests pasan" no es lo mismo que "soy consistente con quien
   consume mi output" ([caso real](./casos-reales.md#contrato-bilateral-mitad-arreglado-verificar)).
   **El «PERSISTE» o «imposible» de un agente auditor se re-verifica con reproducción
   barata del orquestador antes de re-delegar o aceptar el veredicto** — es una afirmación
   como cualquier otra ([caso real](./casos-reales.md#persiste-de-auditor-refutado-verificar)).
   **Una verificación de ausencia solo vale si la herramienta corrió de verdad:**
   distinguir «corrió y no encontró» de «no corrió» — un fallback (`|| echo OK`) sobre un
   comando inexistente fabrica falsos negativos limpios
   ([caso real](./casos-reales.md#check-que-fallo-no-es-check-verificar)).
   **Los «NO VERIFICADO» que se repiten entre rondas son deuda de auditoría:** si la misma
   zona queda sin verificar dos rondas seguidas, la siguiente incluye provisionar la
   dependencia (infra efímera) en vez de re-anotar el hueco
   ([caso real](./casos-reales.md#no-verificado-acumulado-verificar)).
   **La re-demostración del orquestador usa la invocación DOCUMENTADA**, no la que el
   agente eligió para su propia verificación — si ambos caminos difieren, el bug vive en
   esa diferencia ([caso real](./casos-reales.md#demo-por-el-camino-documentado-verificar)).
   **Cuando un fix documenta un límite/alcance explícito, la ronda de confirmación
   siguiente rinde más atacando ESE límite con evidencia real que repitiendo el caso ya
   cerrado** — y una hipótesis de "esto podría divergir" formulada por el propio auditor
   es un claim más a verificar contra el sistema real, no una conclusión válida por
   razonamiento desde el estándar en abstracto
   ([caso real](./casos-reales.md#limite-declarado-es-el-siguiente-objetivo-de-auditoria-verificar)).
5. **COMMIT por tarea verificada** — baseline limpio para la siguiente tarea.
6. **CIERRE** — suite completa 2× (dos corridas idénticas ≈ sin flaky; un flaky detectado
   es una tarea futura, no se ignora), reporte del contrato en `docs/reports/`, estado en
   el README.
   **Un ciclo auditoría→fixes se cierra con una ronda de CONFIRMACIÓN de mandato
   invertido:** re-ejecutar la repro de cada hallazgo previo (tabla CERRADO/PERSISTE con
   salida real) + ataque adversarial al código nuevo de los fixes
   ([caso real](./casos-reales.md#ronda-de-confirmacion-cierre)).
   **Tras una interrupción, la infraestructura huérfana es evidencia antes que basura:**
   inspeccionarla y extraer lo que documenta (credenciales efímeras, estado) antes de
   desmontarla ([caso real](./casos-reales.md#infra-huerfana-es-evidencia-cierre)).

## Política de reintentos (tope de gasto)

Máx **2 re-delegaciones** por tarea, cada una con el error exacto como feedback. A la 3ª:
**subdividir** la tarea. Si la versión subdividida también falla: **bloqueado, escalar** al
humano con diagnóstico. Nunca bucle infinito.

## Reglas duras

- El veredicto es del **gate determinista** (validador + tests + CI), nunca del modelo.
- Un contrato de ejecución no se cierra con criterios sin salida de máquina.
- Los agentes nunca commitean ni tocan archivos fuera del perímetro declarado en su spec.
- Toda spec lleva **condiciones de aborto** explícitas (ver `specs/TEMPLATE-CONTRACT.md`):
  ante un criterio inalcanzable por razón legítima, el agente PARA y documenta con
  evidencia en vez de improvisar o forzar.
- El ensamblador de contexto (si está instalado: `scripts/assemble_context.py` +
  `ccdd/context.json`) provee contexto presupuestado y auditable para cada delegación.
