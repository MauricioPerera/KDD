---
type: 'Task Contract'
title: 'Validación de registro de usuario'
description: 'Función pura que valida un registro de usuario contra las restricciones de dominio del modelo users.'
tags: ['ccdd', 'users', 'validacion', 'example']

task: validate-user-record
intent: "Validar un registro de usuario contra las restricciones de dominio del modelo users."
target: src/users.py
signature: "def validate_user_record(record: dict) -> list:"
test_command: "python -m unittest tests/test_users.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 3
tests: "tests/test_users.py"
tests_sha256: "725feb13af1b36b1d28aac4cd478045cbed7fabfbcba42dc618b7538191b84a9"
touch_only: ['src/users.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-user-record

## Intent
Función pura de validación de registros de usuario para la app de ejemplo, anclada al
modelo [Tabla users](../data_models/users_table.md) — las reglas de dominio viven ALLÍ,
este contrato no las duplica.

## Interface
```python
def validate_user_record(record: dict) -> list:
    """Valida `record` contra los campos y restricciones de dominio de la tabla users.
    Devuelve una lista de strings legibles, una por violación (vacía si es válido).
    Cada mensaje nombra el campo afectado. Función pura: sin IO, sin red, determinista."""
```

## Invariants
- Campos obligatorios (no nulos sin default en el modelo): `email`, `username`,
  `password_hash` — ausentes o no-string → violación que nombra el campo.
- `username`: exactamente el patrón `[a-z0-9_]{3,50}` del modelo.
- `email`: validación básica de formato (al estilo "RFC 5322 básica" del modelo: una `@`,
  parte local no vacía, dominio con al menos un punto y sin espacios). Tope 255 chars.
- `password_hash`: string de exactamente 60 caracteres (CHAR(60), bcrypt).
- `display_name`: opcional (ausente o None es válido); si está, string de ≤100 chars.
- La función NO valida unicidad ni timestamps (invariantes de tabla/DB, no de registro).
- Determinista, pura, stdlib (se permite `re`); nunca lanza ante input dict arbitrario.

## Examples
- Registro válido completo -> `[]`.
- `{"email": "a@b.co", "username": "ab", "password_hash": "x"*60}` -> 1 violación
  (username corto), el mensaje contiene `username`.
- `{}` -> 3 violaciones (email, username, password_hash ausentes).

## Do / Don't
- DO: mensajes que nombren el campo y la regla violada.
- DO: acumular TODAS las violaciones (no cortar en la primera).
- DON'T: red, subprocess, IO de archivos, dependencias fuera de stdlib.
- DON'T: tocar tests/, knowledge/, scripts/, ccdd/ — el oráculo está congelado.

## Tests
(Los tests están en `tests/test_users.py`, autorados por el orquestador ANTES de la
delegación y congelados: el implementador no los escribe ni los modifica.)

## Constraints
- PARAR y reportar si... los tests congelados contradijeran el modelo de datos enlazado o
  exigieran algo imposible con stdlib puro.
