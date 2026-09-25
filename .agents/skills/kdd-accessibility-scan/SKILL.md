---
name: kdd-accessibility-scan
description: Guia a cualquier agente (no depende de ningun modelo puntual) para producir un scan de accesibilidad (WCAG) de un producto en el formato de contrato de Capa 3 de KDD -- findings.json -- que despues gatea scripts/validate_accessibility_findings.py. Usala cuando se pida auditar accesibilidad de una app/pagina, correr axe-core/Lighthouse/pa11y, o se mencione "accessibility scan", "WCAG", "a11y" o "Capa 3" en el contexto de este template. NO confundir con validate_ux_page.py (linter estatico de HTML propio del repo, otro gate).
---

# Accessibility Scan (Capa 3 de KDD -- WCAG)

Produce hallazgos de auditoria de accesibilidad en el formato de contrato que
audita la Capa 3 de KDD. Esta skill NO es el gate -- es la parte creativa/no
determinista (correr un scanner automatizado, complementar con revision manual,
mapear cada violacion a un criterio WCAG) que el gate despues valida. Distincion
central: **el scanner/agente decide QUE es un hallazgo de accesibilidad; el gate
solo audita que el artefacto sellado cumpla forma y politica de calidad de datos.**

Como [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md) y
[`kdd-privacy-scan`](../kdd-privacy-scan/SKILL.md), este dominio NO vendoriza
ningun sellador externo -- vos mismo escribis `findings.json` ya en forma final.

## No es lo mismo que `validate_ux_page.py`

KDD ya tiene un gate mecanico, `scripts/validate_ux_page.py` (ver
[validacion.md](../../../knowledge/validacion.md)): un linter estatico que corre
SIN ejecutar nada, sobre paginas HTML AUTOCONTENIDAS del propio repo
(`examples/ux-page/` por defecto) -- contraste sobre pares explicitos, i18n,
`prefers-reduced-motion`. Esta skill es OTRA cosa: gobierna una auditoria real
(automatizada y/o manual) sobre el PRODUCTO en ejecucion, con cobertura mucho mas
amplia (formularios, navegacion por teclado, lectores de pantalla, SPAs). Los dos
gates coexisten sin conflicto -- ver la seccion correspondiente en
[`knowledge/data_models/accessibility_findings.md`](../../../knowledge/data_models/accessibility_findings.md).

## Cuando usarla

El usuario pide auditar la accesibilidad de un producto/pagina en ejecucion y
quiere el resultado gobernado por KDD (versionable, gateado en CI, con politica
declarativa), no un reporte suelto en prosa.

## Insumos que necesitas antes de empezar

- `target`: URL o build local del producto a auditar.
- `scan_dir`: donde vas a escribir `findings.json`. Por defecto
  `accessibility/scan` dentro del repo KDD (coincide con el default de
  `validate_accessibility_findings.py`); si estas gobernando un producto EXTERNO,
  cualquier directorio disponible sirve, con tal de pasarselo explicito al gate.
- El schema completo vive en
  `knowledge/data_models/accessibility/findings.schema.json` -- consultalo si
  dudas de un campo, no adivines la forma.

## Flujo

### 1. Corre un scanner automatizado

No reimplementes deteccion de violaciones WCAG: usa una herramienta estandar.

| Herramienta | Cobertura tipica | Comando/uso tipico |
|---|---|---|
| axe-core | La mas amplia, integrable en tests E2E (Playwright/Cypress) | `@axe-core/playwright` o CLI `axe <url>` |
| Lighthouse | Auditoria de pagina completa (incluye accesibilidad + performance) | `lighthouse <url> --only-categories=accessibility` |
| pa11y | CLI simple, buena para CI | `pa11y <url>` |

Un scanner automatizado detecta tipicamente 30-50% de las violaciones reales
(contraste, labels faltantes, orden de headings, atributos ARIA mal usados) --
NO detecta problemas de flujo (orden de tab logico, anuncios de lector de
pantalla en contenido dinamico, gestos). Documenta cual usaste en `source`.

### 2. Complementa con revision manual donde el scanner no llega

Al menos: navegacion completa solo-teclado (Tab/Shift+Tab/Enter/Escape) y
verificacion de que el foco es visible y sigue un orden logico. Si podes,
sumale un recorrido rapido con un lector de pantalla (NVDA/VoiceOver/JAWS) sobre
los flujos criticos (login, checkout, formularios). Documentalo como
`source: "manual review"` en los findings que produzca.

No inventes un finding para llenar un cupo: una auditoria que concluye "sin
violaciones de impacto critico/serious" es un resultado valido.

### 3. Mapea cada violacion a WCAG y clasifica el impacto

Por cada violacion real, junta ANTES de escribir el JSON:
- `wcagCriterion` (numero de criterio de exito, p.ej. `1.4.3` contraste,
  `2.1.1` teclado, `4.1.2` nombre/rol/valor -- si el scanner ya lo mapea,
  reusalo; si no, mapealo vos con la [Quick Reference de W3C](https://www.w3.org/WAI/WCAG21/quickref/));
- `wcagLevel` (`A`/`AA`/`AAA`, o `n/a` si no es mapeable a un criterio formal);
- `impact` -- mismo vocabulario que axe-core: `critical` (bloquea el uso total
  para un grupo de usuarios), `serious` (bloquea una tarea especifica),
  `moderate` (dificulta pero no bloquea), `minor` (friccion menor);
- `location` exacta (pagina/ruta + selector CSS o descripcion del componente);
- una remediacion CONCRETA y accionable para cualquier `critical`/`serious` (no
  "mejorar la accesibilidad" -- eso no pasa el gate de politica, que exige
  remediaciones sustantivas de >=20 caracteres para esos dos niveles).

### 4. Escribir el artefacto

En `<scan_dir>/findings.json`:

```json
{
  "documentType": "kdd-accessibility.findings",
  "schemaVersion": "1.0",
  "scanId": "<identificador estable, p.ej. hash corto del commit + '_kdd-accessibility-scan'>",
  "findings": [
    {
      "findingId": "a11y_<pagina-slug>-<secuencial>",
      "wcagCriterion": "1.4.3",
      "wcagLevel": "AA",
      "impact": "serious",
      "location": "...",
      "ruleId": "color-contrast",
      "remediation": "...",
      "source": "axe-core | lighthouse | pa11y | manual review"
    }
  ]
}
```

`findingId` es responsabilidad tuya (no hay finalizer que lo derive): usa la
pagina/componente + un secuencial para que sea estable entre corridas del mismo
scan.

### 5. Gatear

```
python scripts/validate_accessibility_findings.py <scan_dir>
```

`FAIL` con violaciones reales (impacto fuera de enum, remediacion tipo
placeholder en un `critical`/`serious`) significa que el HALLAZGO esta mal
capturado, no que el gate este mal -- volve al paso 3 para ese finding
especifico, no debilites la regla en
`examples/rules/accessibility-findings.rules.json` para que pase.

### 6. Reportar

Devolve al usuario la ruta de `findings.json` y un resumen: que herramienta(s)
se usaron, cuantas paginas/flujos se cubrieron, cuantos findings de impacto
`critical`/`serious` se sellaron.

## Que NO hace esta skill

- No reemplaza pruebas con usuarios reales de tecnologia asistiva -- produce el
  artefacto gobernable que puede alimentar una auditoria mas profunda; verificar
  que una correccion funciona para un usuario real vive fuera del artefacto
  sellado (ver el `code_only` de `accessibility-findings.rules.json`).
- No reemplaza el gate `validate_ux_page.py` -- son dominios complementarios, no
  sustitutos (ver seccion arriba).
- No escanea seguridad, licencias ni privacidad -- esos son
  [`kdd-security-scan`](../kdd-security-scan/SKILL.md),
  [`kdd-compliance-scan`](../kdd-compliance-scan/SKILL.md) y
  [`kdd-privacy-scan`](../kdd-privacy-scan/SKILL.md), dominios de politica
  distintos.
