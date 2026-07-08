---
type: 'Data Model'
title: 'Politica de ruteo de mensajes'
description: 'Ejemplo didactico del patron evento-decision en dos formas contratables: la decision como codigo (route_message) y la auditoria de decisiones como datos (keyed_enums), con la frontera del else abierto documentada.'
tags: ['data-model', 'routing', 'rule-contract', 'example']
---

# Data Model: politica de ruteo de mensajes

Ejemplo minimo del patron "si llega un mensaje y el emisor es Y, ejecuta A; si no, B" en
sus DOS formas contratables. La politica: emisores listados van a su ruta; cualquier otro
va a la ruta `default`.

| Emisor (minusculas)  | Ruta |
|----------------------|------|
| `vip@acme.com`       | A    |
| `soporte@acme.com`   | A    |
| cualquier otro       | B (default) |

Reglas de dominio: el emisor se normaliza a minusculas (los emails no distinguen
mayusculas); emisor ausente o malformado cae al default (rama else EXPLICITA, decidida por
contrato y fijada por tests, no por accidente de implementacion).

## Forma 1 — la decision como CODIGO (task contract)

[route-message](../contracts/route-message.md): funcion pura
`route_message(message, routing) -> str` con oraculo congelado. Es quien DECIDE. La rama
`else` abierta es trivial en codigo.

## Forma 2 — la auditoria como DATOS (rule contract)

`examples/rules/routing-audit.rules.json`: valida decisiones YA tomadas
(records `{sender, decision}`) contra la politica via `keyed_enums` (la decision permitida
depende del emisor). Sirve para auditar un log de ruteos con el gate determinista.

## Frontera documentada: el else abierto

La forma datos SOLO cubre emisores ENUMERADOS en la tabla: las familias keyed se saltan
cuando la clave no resuelve (semantica congelada del motor desde C17). "Cualquier emisor
NO listado debe haber ido a B" es un condicional con default sobre mundo abierto —
inexpresable declarativamente; queda `code_only` (lo decide y lo audita el codigo de la
Forma 1). Cuarta aparicion de la clase "condicional/comparacion no uniforme" en el mapa de
fronteras de la vertiente.
