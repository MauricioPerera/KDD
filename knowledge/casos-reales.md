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

## contrato-bilateral-mitad-arreglado (VERIFICAR)

Fuera de este repo (proyecto hermano `mcpwasm`, mismo dueño): un bug real en `canonicalOrigin()` — `new URL(s).origin` descarta el subpath de una URL, rompiendo la firma Ed25519 de skills publicadas en un GitHub Pages de *proyecto* (`user.github.io/REPO/`, no de dominio raíz) — se arregló en el lado que **firma** (`scripts/attest.mjs`). Verificación propia completa en ese lado: tests unitarios, verificación criptográfica de la firma contra la clave pública, corrida real contra el sitio en producción. Todo dio verde. Lo que no se verificó: la misma función `canonicalOrigin()` estaba duplicada, sin arreglar, en los dos lugares que **consumen** esa firma (`worker-gateway.mjs`, el gate que hace cumplir las atestaciones en el propio servidor; `scripts/validate-publisher.mjs`, el linter de onboarding). El fix hacía que las firmas se generaran bien y se **rechazaran** en todo lugar donde se verificaban — el bug no desaparecía, cambiaba de lado. Lo encontraron dos revisores de código automáticos independientes (Gemini Code Assist y Codex) comentando la misma PR, en paralelo, sin que ninguno supiera del otro. Regla derivada: cuando el fix toca una función que un lado de un contrato bilateral usa para producir algo (firmar, escribir, serializar) y otro lado usa para consumirlo/verificarlo (verificar, leer, deserializar), un grep del nombre de la función en todo el repo es parte de la verificación — "mis tests pasan" certifica el lado que tocaste, no que seas consistente con quien consume tu output. Complemento: una segunda opinión independiente (humana o de otro agente) sigue cazando cosas que la propia verificación exhaustiva de un lado no puede ver por construcción.
