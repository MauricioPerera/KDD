"""Implementacion de validate-payment-limit (Contrato 16, ejemplo de dominio).

Funcion pura que valida pagos internacionales contra limites por pais y
verificacion de beneficiario. Las reglas de dominio viven en
knowledge/data_models/payment_limits.md; el contrato en
knowledge/contracts/validate-payment-limit.md; el oraculo (congelado) en
tests/test_payment_limit.py.
"""


def validate_payment_limit(payment: dict, limits: dict) -> list:
    """Valida `payment` contra las reglas de dominio de `limits` (por pais).

    Devuelve una lista de strings legibles, una por violacion (vacia si es
    valido). Cada mensaje nombra el campo afectado. Funcion pura: sin IO,
    sin red, determinista.

    Args:
        payment: dict con keys 'amount', 'currency', 'country', 'beneficiary'.
        limits: dict mapeando codigo_pais -> {'max_amount': int, 'allowed_currencies': [...]}.

    Returns:
        list de strings de violaciones acumuladas ([] si valido).
    """
    violations = []

    # Validar country: debe ser string y existir en limits
    country = payment.get("country")
    country_valid = isinstance(country, str) and country in limits
    if not country_valid:
        violations.append(f"country: invalid or not found in limits")

    # Validar amount: debe ser number (no bool), > 0, y <= limits[country].max_amount
    amount = payment.get("amount")
    # Rechazar booleans explicitamente ANTES de int/float (bool es subclase de int en Python)
    if isinstance(amount, bool):
        violations.append(f"amount: boolean is not a valid payment amount")
    elif not isinstance(amount, (int, float)):
        violations.append(f"amount: must be numeric")
    elif amount <= 0:
        violations.append(f"amount: must be positive")
    elif country_valid and amount > limits[country]["max_amount"]:
        violations.append(f"amount: exceeds country limit")

    # Validar currency: debe estar en limits[country].allowed_currencies (solo si country valido)
    if country_valid:
        currency = payment.get("currency")
        allowed_currencies = limits[country].get("allowed_currencies", [])
        if currency not in allowed_currencies:
            violations.append(f"currency: not allowed for this country")

    # Validar beneficiary: dict con verified==True (exactamente True) y account no vacio
    beneficiary = payment.get("beneficiary")
    if not isinstance(beneficiary, dict):
        violations.append(f"beneficiary: must be a dictionary")
    elif beneficiary.get("verified") is not True or not beneficiary.get("account"):
        violations.append(f"beneficiary: must have verified=True and non-empty account")

    return violations
