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
   ([caso real](./casos-reales.md#entorno-afirmado)).
   La misma regla aplica a la EXISTENCIA de recursos nombrados: un pedido de «crear X»
   (repo, worker, base de datos) es en realidad «asegurar que X exista con este
   contenido». Verificar primero con un check barato (`gh repo view`, listado del
   proveedor, `ls`); si X ya existe, inspeccionar su contenido y reconciliar con lo
   pedido — nunca crear ni forzar por encima
   ([caso real](./casos-reales.md#crear-sobre-existente)).
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
   paso previene están en [casos reales](./casos-reales.md#hecho-sin-intencion).
   Complemento verificado: exigir sección de **trade-offs** en el reporte del agente es
   el detector más barato de estas clases — se cazan leyendo esa sección + el diff
   puntual de la zona, nunca el diff entero.
3. **DELEGAR** — un agente efímero por tarea. Tareas que compartan archivos → secuenciales.
   Las tareas en **paralelo** deben declarar en su spec el conjunto de archivos que tocan,
   y ese conjunto debe ser **disjunto** respecto a otras tareas corriendo al mismo tiempo.
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
   ([caso real](./casos-reales.md#verificar-antes-de-limpiar)).
5. **COMMIT por tarea verificada** — baseline limpio para la siguiente tarea.
6. **CIERRE** — suite completa 2× (dos corridas idénticas ≈ sin flaky; un flaky detectado
   es una tarea futura, no se ignora), reporte del contrato en `docs/reports/`, estado en
   el README.

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
