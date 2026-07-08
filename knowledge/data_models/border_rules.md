---
type: 'Data Model'
title: 'Reglas de control de fronteras'
description: 'Segundo dominio de la vertiente rule contract: reglas de admision de solicitantes (vocabulario papers-please) expresadas como datos declarativos, con su mapeo a familias y fronteras documentadas.'
tags: ['data-model', 'rule-contract', 'border', 'example']
---

# Data Model: reglas de control de fronteras

Segundo dominio de la vertiente [rule contract](../rule-contract-spec.md), para medir la
generalidad de las familias declarativas. Vocabulario tomado del perfil `papers-please` de
`MauricioPerera/game-protocol` (reglas `require-document`, `ban-country`,
`require-field-match`, `not-expired`; decisiones `approve/deny/detain`). El rule-set vive
en `examples/rules/border-control.rules.json` (referencia por ruta; los `.json` no son
nodos OKF).

## El record: una solicitud de entrada

| Campo             | Tipo    | Regla                                                        |
|-------------------|---------|--------------------------------------------------------------|
| `country`         | string  | Debe estar en la tabla `countries` (paises admitidos).       |
| `decision`        | string  | Una de `approve` / `deny` / `detain`.                        |
| `stay_days`       | number  | `> 0` y `<=` el tope `max_stay_days` del pais.               |
| `doc`             | dict    | Documento presentado.                                        |
| `doc.type`        | string  | Permitido segun `allowed_docs` del pais.                     |
| `doc.owner`       | string  | Obligatorio; debe COINCIDIR con `applicant_name` (frontera). |
| `doc.expiry_year` | number  | `>=` el año de politica (documento no vencido).              |
| `applicant_name`  | string  | Obligatorio.                                                 |

## Mapeo vocabulario papers-please -> familias declarativas

| Regla papers-please   | Familia          | Como                                                    |
|-----------------------|------------------|----------------------------------------------------------|
| `ban-country`         | `refs`           | `countries` contiene SOLO admitidos; vetado = fuera.     |
| `require-document`    | `required` + `keyed_enums` | doc obligatorio; `doc.type` permitido POR pais. |
| `not-expired`         | `bounds`         | `doc.expiry_year >= 2027` (año de politica FIJO).       |
| decision valida       | `enums`          | `approve` / `deny` / `detain`.                           |
| tope de estadia       | `keyed_bounds`   | `stay_days <=` `max_stay_days` del pais.                 |
| `require-field-match` | **`code_only`**  | Ver fronteras.                                           |

## Fronteras documentadas (dato/logica)

1. **`require-field-match`** (`doc.owner` debe coincidir con `applicant_name`): es igualdad
   ENTRE dos campos del record. Ninguna familia lo expresa — comparan un campo contra
   constantes (`enums`/`bounds`) o contra tablas (`refs`/`keyed_*`), no campos entre si.
   Coincide con game-protocol, que implementa esa regla como logica del motor. Queda
   `code_only` en el rule-set.
2. **`not-expired` relativo a "hoy"**: exigiria reloj y romperia el determinismo del gate.
   El rule-set congela el año de politica (2027) como dato; renovarlo es editar el
   rule-set y re-sellar (el diff lo hace visible en review).
