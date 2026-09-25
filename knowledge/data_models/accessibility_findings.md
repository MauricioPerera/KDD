---
type: 'Data Model'
title: 'Hallazgos de accesibilidad (Capa 3 de KDD)'
description: 'Modelo de datos de un sexto dominio de KDD, junto a OKF (conocimiento), CCDD (codigo), hallazgos de seguridad, compliance/licencias y privacidad/PII: hallazgos de auditoria de accesibilidad (WCAG) en accessibility/scan/findings.json, gobernados por examples/rules/accessibility-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['accesibilidad', 'accessibility', 'wcag', 'rules', 'ccdd']
---

# Hallazgos de accesibilidad (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos de auditoria de accesibilidad (WCAG) de un
producto, con el mismo motor declarativo (`rule_engine.py`) que ya gobierna
registros MCP, pagos, fronteras, seguridad, compliance de licencias y privacidad --
no se escribio codigo de motor nuevo para esta capa, solo un dominio de datos y una
policy.

## No reemplaza al gate `validate_ux_page.py` -- es otra cosa

KDD ya tiene un gate mecanico de accesibilidad, `scripts/validate_ux_page.py`
(documentado en [validacion.md](../validacion.md)): un linter propio en Python puro
que verifica contraste WCAG sobre pares explicitos, completitud de i18n y la guarda
`prefers-reduced-motion` en las paginas HTML AUTOCONTENIDAS del propio repo KDD (por
ejemplo `examples/ux-page/`). Ese gate se solapa en TEMA con este dominio pero no en
mecanica ni en alcance:

- `validate_ux_page.py` es un **linter estatico** sobre HTML que vive en el repo,
  sin ejecutar nada -- cubre 4 chequeos puntuales, no una auditoria completa.
- Este dominio (`accessibility/scan/findings.json`) sella **hallazgos de una
  auditoria externa real** (axe-core, Lighthouse, pa11y, o revision manual con
  lector de pantalla) sobre el PRODUCTO en ejecucion -- paginas renderizadas, apps
  SPA, cualquier superficie que el linter estatico no puede alcanzar.

Un proyecto puede usar los dos gates a la vez sin conflicto: el linter estatico para
las paginas HTML del propio repo, este dominio para hallazgos de una auditoria mas
amplia del producto.

## Sin vendoring (mismo criterio que compliance/privacidad)

Como [compliance/licencias](./compliance_findings.md) y
[privacidad/PII](./privacy_findings.md), este dominio NO vendoriza ningun sellador
externo: la identidad de un hallazgo de accesibilidad (pagina + criterio WCAG +
selector) la resuelve el scanner que se use (axe-core, Lighthouse, pa11y) o quien
haga la revision manual -- no un finalizer determinista propio de KDD. KDD
normaliza la salida de esas herramientas al schema de este dominio y gatea, no
reimplementa deteccion de violaciones WCAG.

## El artefacto sellado

`accessibility/scan/findings.json`: `documentType: "kdd-accessibility.findings"` y
`findings[]`. Cada finding trae `findingId`, `wcagCriterion` (numero de criterio de
exito WCAG, p.ej. `1.4.3`, `2.1.1`, o `n/a` si no es mapeable a un criterio),
`wcagLevel` (`A`/`AA`/`AAA`/`n/a`), `impact`
(`critical`/`serious`/`moderate`/`minor` -- mismo vocabulario que el campo `impact`
de axe-core), `location` (pagina/ruta + selector o componente), `ruleId` (id de
regla especifico del scanner, si se conoce), `remediation`, `source` (que
herramienta lo produjo). Schema completo:
`knowledge/data_models/accessibility/findings.schema.json`.

## Record aplanado que consume la policy

`examples/rules/accessibility-findings.rules.json` opera sobre un record aplanado
que `scripts/validate_accessibility_findings.py` deriva de `findings.json`:

```json
{
  "findings": [
    {
      "findingId": "a11y_checkout-btn-contrast-001",
      "wcagCriterion": "1.4.3",
      "wcagLevel": "AA",
      "impactLevel": "serious",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), mismo patron que los demas dominios -- permite usar la
familia `bounds` del rule engine sobre la calidad del texto de remediacion.

## Politica activa (examples/rules/accessibility-findings.rules.json)

- Todo finding necesita `findingId`, `wcagCriterion`, `impact` validos.
- `impact` en `critical`/`serious` exige `remediation` >=20 caracteres (rechaza
  placeholders) -- una violacion de impacto alto no se documenta con un "revisar
  despues".

## Frontera honesta (`code_only`)

Las pruebas con tecnologia asistiva real (recorridos con lector de pantalla,
navegacion solo-teclado con usuarios reales, testing con switch access) viven fuera
del `findings.json` sellado -- verificar que una correccion realmente funciona para
un usuario real de tecnologia asistiva exige esas pruebas, fuera del alcance de un
gate nivel 1 determinista y sin red. Documentado como entrada `code_only` en el
rule-set, no fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill [`kdd-accessibility-scan`](../../.agents/skills/kdd-accessibility-scan/SKILL.md):
gobierna el flujo (correr un scanner automatizado del ecosistema, complementar con
revision manual de lo que el scanner no puede detectar, normalizar al schema de
este dominio) que termina escribiendo estos artefactos.
