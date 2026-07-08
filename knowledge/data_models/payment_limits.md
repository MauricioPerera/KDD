---
type: 'Data Model'
title: 'Limites de pago por pais'
description: 'Modelo de las reglas de compliance por pais para pagos internacionales: tope por pais, divisas permitidas y verificacion de beneficiario.'
tags: ['data-model', 'payments', 'compliance', 'example']
---

# Data Model: `payment_limits`

Reglas de compliance por pais para pagos internacionales. La logica que las hace cumplir
vive en el contrato [validate-payment-limit](../contracts/validate-payment-limit.md); este
nodo es la unica fuente de las reglas de dominio (el contrato ENLAZA aqui, no las duplica).

## Estructura de `limits`

`limits` es un dict `codigo_pais -> config`, con `codigo_pais` en ISO 3166-1 alpha-2
mayusculas:

| Campo               | Tipo       | Restricciones / Notas                                    |
|---------------------|------------|----------------------------------------------------------|
| `max_amount`        | number     | Tope por transaccion en la unidad menor; entero > 0.     |
| `allowed_currencies`| string[]   | Codigos ISO 4217 permitidos para ese pais (no vacio).    |

## Estructura de `payment`

| Campo         | Tipo    | Restricciones / Notas                                        |
|---------------|---------|--------------------------------------------------------------|
| `amount`      | number  | Monto de la transaccion; number (no bool), > 0.              |
| `currency`    | string  | ISO 4217; debe estar en `allowed_currencies` del pais.       |
| `country`     | string  | ISO 3166-1 alpha-2; debe existir como clave en `limits`.     |
| `beneficiary` | dict    | Ver "Verificacion de beneficiario".                          |

## Restricciones de dominio

- `country` desconocido (ausente de `limits`) = pago rechazado; no se asume tope global.
- `amount` debe ser number positivo y `<= limits[country].max_amount`.
- `currency` debe pertenecer a `allowed_currencies` del pais.

## Verificacion de beneficiario

- `beneficiary.verified` debe ser exactamente `True` (KYC/AML aprobado aguas arriba).
- `beneficiary.account` debe ser un string no vacio (destino identificable).
- Un beneficiario sin verificar bloquea el pago aunque el monto y la divisa sean validos.
