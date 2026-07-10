---
type: 'Task Contract'
title: 'Validacion de limite de pago por pais'
description: 'Funcion pura que valida un pago internacional contra los limites por pais y la verificacion de beneficiario, antes de cualquier merge.'
tags: ['ccdd', 'payments', 'compliance', 'validacion', 'example']

task: validate-payment-limit
intent: "Validar un pago internacional contra los limites por pais y la verificacion de beneficiario."
target: src/payment_limit.py
signature: "def validate_payment_limit(payment: dict, limits: dict) -> list:"
test_command: "python -m unittest tests/test_payment_limit.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 3
tests: "tests/test_payment_limit.py"
tests_sha256: "e484831ce7394394bf0e437b85570593847c687b6faf2f764852d5d5a8c8a311"
touch_only: ['src/payment_limit.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: validate-payment-limit

## Intent
Funcion pura de validacion de pagos internacionales para el gate pre-merge, anclada al
modelo [Limites de pago por pais](../data_models/payment_limits.md) -- las reglas de
compliance viven ALLI, este contrato no las duplica (regla 3 de la skill KDD). El veredicto
lo da el gate determinista corriendo los tests, nunca un modelo: una regla de limite por
pais o de beneficiario se verifica, no se opina.

## Interface
```python
def validate_payment_limit(payment: dict, limits: dict) -> list:
    """Valida `payment` contra las reglas de dominio de `limits` (por pais).
    Devuelve una lista de strings legibles, una por violacion (vacia si es valido).
    Cada mensaje nombra el campo afectado. Funcion pura: sin IO, sin red, determinista."""
```

## Invariants
- `country`: debe ser string y existir como clave en `limits`; desconocido -> violacion
  que nombra `country`. No se asume un tope global para paises no habilitados.
- `amount`: number (no bool) y `> 0`; ademas `<= limits[country].max_amount` cuando el
  pais es valido. El tope es POR PAIS, no global.
- `currency`: string dentro de `limits[country].allowed_currencies` (solo evaluable con
  pais valido).
- `beneficiary`: dict con `verified is True` (exactamente True, no truthy) y `account`
  string no vacio; en otro caso -> violacion que nombra `beneficiary`.
- La funcion NO consulta fuentes externas ni la red: `limits` se le pasa como argumento
  (la carga de la tabla de compliance es responsabilidad del llamador, fuera del oraculo).
- Acumula TODAS las violaciones (no corta en la primera); determinista, pura, stdlib;
  nunca lanza ante `payment` con valores de tipos arbitrarios.

## Examples
- Pago valido completo (`AR`, `USD`, monto bajo, beneficiario verificado) -> `[]`.
- `country="XX"` (fuera de `limits`) -> 1 violacion; el mensaje contiene `country`.
- `amount` por encima de `max_amount` del pais -> 1 violacion que contiene `amount`.
- `beneficiary.verified is False` -> 1 violacion que contiene `beneficiary`.
- Pais desconocido + monto negativo + beneficiario sin verificar -> 3 violaciones.

## Do / Don't
- DO: mensajes que nombren el campo y la regla violada.
- DO: acumular TODAS las violaciones (una corrida = todos los motivos de rechazo).
- DON'T: red, subprocess, IO de archivos, consultar la tabla de limites por fuera del
  argumento `limits` -- el oraculo esta congelado.
- DON'T: tocar tests/, knowledge/, el modelo de datos -- el implementador no reescribe su
  propio oraculo.

## Tests
(Los tests estan en `tests/test_payment_limit.py`, autorados por el orquestador ANTES de
la delegacion y congelados por `tests_sha256`: el implementador no los escribe ni los
modifica -- si edita el archivo, el hash rompe el gate.)

## Constraints
- PARAR y reportar si... los tests congelados contradijeran el modelo de datos enlazado, o
  exigieran consultar una fuente externa de limites (eso viola la pureza: la tabla entra
  por argumento), o algo imposible con stdlib puro.
