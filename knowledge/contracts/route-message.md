---
type: 'Task Contract'
title: 'Router de mensajes por emisor'
description: 'Funcion pura que decide la ruta de un mensaje segun su emisor contra una tabla de ruteo: emisor listado va a su ruta, cualquier otro a la ruta default.'
tags: ['ccdd', 'routing', 'mensajes', 'example']

task: route-message
intent: "Decidir la ruta de un mensaje segun su emisor contra una tabla de ruteo pasada por argumento."
target: src/route_message.py
signature: "def route_message(message: dict, routing: dict) -> str:"
test_command: "python -m unittest tests/test_route_message.py"
budget:
  max_cyclomatic_complexity: 5
  max_nesting_depth: 2
tests: "tests/test_route_message.py"
tests_sha256: "58536df6ac19b41b15b6024a3a9af2d842fb4ec647a39091eb42da066439cba7"
touch_only: ['src/route_message.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: route-message

## Intent
Ejemplo didactico minimo del patron "evento -> decision": si llega un mensaje y el emisor
es Y, ruta A; si no, ruta B. La politica vive en
[message_routing](../data_models/message_routing.md) (este contrato la enlaza, no la
duplica); la forma auditoria-como-datos del MISMO dominio vive en
`examples/rules/routing-audit.rules.json`. Spec: `specs/CONTRACT-21-message-router.md`.

## Interface
```python
def route_message(message: dict, routing: dict) -> str:
    """Decide la ruta de `message` segun `routing`:
    {"senders": {<email en minusculas>: <ruta>}, "default": <ruta>}.
    Devuelve la ruta del emisor (normalizado a minusculas) si esta en senders;
    routing["default"] en cualquier otro caso. Pura, determinista, nunca lanza."""
```

## Invariants
- El emisor (`message["sender"]`) se normaliza a minusculas antes de buscar en `senders`.
- Emisor ausente, `None`, no-string o no listado -> `routing["default"]`.
- La tabla entra POR ARGUMENTO (pureza): nada de estado global, red ni IO.
- Nunca lanza ante `message` con valores de tipos arbitrarios.
- Determinista; stdlib puro; sin red; sin subprocess.

## Examples
- `route_message({"sender": "vip@acme.com"}, R)` -> `"A"` (listado).
- `route_message({"sender": "VIP@ACME.COM"}, R)` -> `"A"` (normalizacion).
- `route_message({"sender": "otro@x.com"}, R)` -> `"B"` (rama else / default).
- `route_message({}, R)` -> `"B"` (ausente = default, decidido por contrato).

## Do / Don't
- DO: default seguro para todo lo no reconocido (la rama else es explicita, no implicita).
- DON'T: red, IO, estado global, dependencias fuera de stdlib; tocar tests/ (oraculo
  congelado por tests_sha256), knowledge/ ni examples/.

## Tests
(Los tests estan en `tests/test_route_message.py`, autorados por el orquestador y
congelados: emisor listado, normalizacion, rama else en todas sus formas, tabla vacia,
pureza por argumento, determinismo, robustez.)

## Constraints
- PARAR y reportar si... el oraculo congelado fuera internamente contradictorio o exigiera
  algo imposible con stdlib puro.
