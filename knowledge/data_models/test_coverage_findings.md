---
type: 'Data Model'
title: 'Hallazgos de cobertura de tests (Capa 3 de KDD)'
description: 'Modelo de datos de un noveno dominio de KDD, junto a OKF (conocimiento), CCDD (codigo), hallazgos de seguridad, compliance/licencias, privacidad/PII, accesibilidad, vigencia de dependencias y observabilidad: hallazgos de gaps de cobertura de tests en test-coverage/scan/findings.json, gobernados por examples/rules/test-coverage-findings.rules.json via el mismo rule_engine.py declarativo de los demas dominios.'
tags: ['testing', 'cobertura', 'coverage', 'rules', 'ccdd']
---

# Hallazgos de cobertura de tests (Capa 3 de KDD)

Dominio de KDD que gobierna hallazgos de gaps de cobertura de tests --- rutas
criticas sin test, casos de error sin cubrir, ausencia de test de regresion
tras un bug real --- con el mismo motor declarativo (`rule_engine.py`) que ya
gobierna registros MCP, pagos, fronteras, seguridad, compliance de licencias,
privacidad, accesibilidad, vigencia de dependencias y observabilidad -- no se
escribio codigo de motor nuevo para esta capa, solo un dominio de datos y una
policy.

## Frontera critica con CCDD: NO es lo mismo que el oraculo congelado

**Este es el dominio con mayor riesgo de solaparse con la disciplina nativa
de KDD, asi que la frontera hay que leerla con cuidado antes de usarlo.**

CCDD (el segundo pilar de KDD) YA exige que todo `task contract` tenga un
oraculo de tests CONGELADO (`tests_sha256`) y que `test_command` pase en
verde -- eso lo gatea `validate_contracts.py` y `validate_test_commands.py`,
ambos Nivel 1 obligatorios, sin ningun dominio nuevo. Si tu pregunta es
"¿esta funcion que se implemento via un task contract tiene tests?", la
respuesta ya la da CCDD: no necesitas este dominio para eso.

Este dominio de Capa 3 cubre lo que CCDD deliberadamente NO cubre:

- **Codigo que nunca paso por un task contract** -- la mayoria de un
  proyecto real, sobre todo instanciado desde un codebase preexistente que
  adopta KDD despues (ver [por-que-kdd.md](../por-que-kdd.md)). CCDD exige
  oraculo SOLO para lo que se delega via contrato; el resto del codigo no
  tiene ninguna garantia de cobertura salvo la que declares aca.
- **Gaps de TIPO de cobertura, no de presencia** -- un `task contract` puede
  tener su `test_command` en verde y aun asi no cubrir el caso de error, la
  condicion de carrera, o el camino que un incidente real revelo como
  faltante. El oraculo congelado certifica que ESOS tests especificos pasan,
  no que sean SUFICIENTES.
- **Test de regresion faltante tras un incidente real** -- un bug que
  aparecio en produccion y se corrigio sin agregar el test que lo hubiera
  atrapado antes.

Si dudas si algo va en CCDD o en este dominio: si la pregunta es "¿este
`task contract` tiene su oraculo?", es CCDD (ya gobernado, gratis). Si la
pregunta es "¿esta ruta critica del sistema, dentro o fuera de un contrato,
tiene el tipo de test que hace falta?", es este dominio.

## Sin vendoring (mismo criterio que los demas dominios nativos)

Como los demas dominios nativos de KDD, este NO vendoriza ningun sellador
externo: la identidad de un gap de cobertura (ubicacion + tipo de gap) la
decide quien revisa el codigo o los reportes de cobertura -- una revision
manual, un reporte de `coverage.py`/`nyc`/`cargo-tarpaulin` cruzado con
juicio de criticidad, o el post-mortem de un incidente real. KDD normaliza
esa informacion al schema de este dominio y gatea, no reimplementa
generacion de reportes de cobertura por ecosistema.

## El artefacto sellado

`test-coverage/scan/findings.json`: `documentType:
"kdd-test-coverage.findings"` y `findings[]`. Cada finding trae `findingId`,
`gapType`
(`untested-critical-path`/`no-error-case-coverage`/`no-regression-test`/`flaky-test-untracked`/`other`),
`location` (archivo:funcion/metodo, modulo, u operacion con el gap),
`criticalPath` (bool, si la ubicacion esta en una ruta critica -- pago,
auth, riesgo de integridad de datos -- si se conoce), `severity`,
`remediation`, `source` (revision manual, reporte de cobertura, post-mortem
de incidente). Schema completo:
`knowledge/data_models/test-coverage/findings.schema.json`.

## Record aplanado que consume la policy

`examples/rules/test-coverage-findings.rules.json` opera sobre un record
aplanado que `scripts/validate_test_coverage_findings.py` deriva de
`findings.json`:

```json
{
  "findings": [
    {
      "findingId": "cov_refund-flow-001",
      "gapType": "untested-critical-path",
      "severityLevel": "high",
      "remediationLength": 0
    }
  ]
}
```

`remediationLength` es un campo CALCULADO (no existe con ese nombre en el
`findings.json` sellado), mismo patron que los demas dominios -- permite usar
la familia `bounds` del rule engine sobre la calidad del texto de
remediacion.

## Politica activa (examples/rules/test-coverage-findings.rules.json)

- Todo finding necesita `findingId`, `gapType`, `severity` validos.
- `severity` en `critical`/`high` exige `remediation` >=20 caracteres
  (rechaza placeholders) -- un gap de cobertura de impacto alto no se
  documenta con un "agregar tests despues": significa que, hoy, esa ruta
  puede romperse sin que ningun test lo detecte.

## Frontera honesta (`code_only`)

Verificar que un test de regresion REALMENTE hubiera atrapado el bug
original (no solo que existe y pasa) exige revertir la correccion y
confirmar que el test falla antes de re-aplicarla -- un chequeo manual
puntual, fuera del alcance de un gate nivel 1 determinista y sin ejecutar
mutaciones sobre el codigo real. Documentado como entrada `code_only` en el
rule-set, no fingido como cubierto.

## Como se produce un finding (la parte no gateada)

Ver la skill
[`kdd-test-coverage-scan`](../../.agents/skills/kdd-test-coverage-scan/SKILL.md):
gobierna el flujo (identificar rutas criticas, cruzarlas con reportes de
cobertura y con el historial de incidentes, normalizar al schema de este
dominio) que termina escribiendo estos artefactos.
