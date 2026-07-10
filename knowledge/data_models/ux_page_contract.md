---
type: 'Data Model'
title: 'Convención UX/accesibilidad para páginas HTML'
description: 'Las dos convenciones de datos que el gate de UX exige (i18n como JSON embebido, pares de contraste explícitos) y la tabla de severidad ERROR/WARNING, calibrada contra google-labs-code/design.md. La frontera mecánico/juicio aplicada a una página web.'
tags: ['ux', 'accesibilidad', 'gate', 'example']
---

# Convención UX/accesibilidad (dominio de ejemplo)

`scripts/validate_ux_page.py` mide lo MECÁNICO de una página HTML autocontenida —
nunca su estética. Misma frontera que el dominio editorial ([Contrato 23](../../docs/reports/CONTRACT-23-REPORT.md)):
las definiciones exactas se congelan, el juicio queda declarado fuera.

## Las dos convenciones de datos que el gate exige

Ninguna de las dos existía antes de este contrato — ambas nacieron de la misma lección:
un objeto JS literal o CSS libre no se puede leer con seguridad sin un motor real; JSON
embebido sí.

**i18n** — `<script type="application/json" id="i18n-data">{"en":{...},"es":{...}}</script>`.
Toda clave `data-i18n`/`data-i18n-html` usada en el HTML debe existir en TODOS los
idiomas declarados.

**Pares de contraste** (opt-in) — `<script type="application/json" id="ux-contrast-pairs">
[{"scope":"root","text":"#hex","bg":"#hex"}, ...]</script>`. El gate calcula el ratio WCAG
2.1 SOLO sobre estos pares explícitos — nunca parsea `:root{...}` ni ninguna otra regla
CSS libre. Sin el bloque, el chequeo de contraste no produce ningún finding.

## Severidad (calibrada contra un tercero real)

Diseño verificado contra [`google-labs-code/design.md`](https://github.com/google-labs-code/design.md)
(25k stars, el linter de facto para este problema): su fórmula de luminancia relativa WCAG
coincide exactamente con la nuestra (validación independiente), y su calibración de
severidad (`contrast-ratio` es `warning`, solo referencias rotas son `error`) fijó la
nuestra:

| Regla | Severidad | Por qué |
|---|---|---|
| `HTML_UNCLOSED` | ERROR | ruptura estructural del documento |
| `I18N_DATA_MISSING` / `I18N_DATA_INVALID` / `I18N_MISSING` | ERROR | equivalente exacto de `broken-ref`: una clave de i18n ausente es una referencia rota |
| `ID_UNRESOLVED` | ERROR | referencia rota real (el JS lanzaría en runtime) |
| `CONTRAST_DATA_INVALID` | ERROR | el bloque opt-in, si existe, debe ser válido |
| `CONTRAST_LOW` | WARNING | alerta de accesibilidad, no ruptura del documento |
| `MOTION_UNGUARDED` | WARNING | accesibilidad recomendada, no ruptura |

El exit code del CLI solo cuenta ERROR (mismo precedente que `FM_KEY_forbids` en
`validate_contracts.py` desde el Contrato 10): un WARNING nunca bloquea.

## Frontera declarada (fuera de este gate)

Comportamiento real de layout (overflow en anchos con nombre, si un `position:sticky`
quece pegado en todo el rango de scroll — bug real encontrado en esta misma sesión
construyendo el propio landing page de KDD), errores de consola, aspecto real de
`:focus-visible`: todo exige un navegador de verdad, fuera del nivel 1 por doctrina (mismo
argumento que el servidor MCP vivo en [Contrato 25](../../docs/reports/CONTRACT-25-REPORT.md)).
Si el diseño es lindo, si la paleta es la correcta: juicio humano, nunca de este gate.

Ejemplo mínimo: `examples/ux-page/demo.html`.
