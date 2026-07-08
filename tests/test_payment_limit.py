"""Oraculo congelado del contrato validate-payment-limit (ejemplo de dominio).

Autorado por el orquestador ANTES de la delegacion. El implementador de
src/payment_limit.py NO escribe ni modifica este archivo: es el oraculo
independiente (CCDD canonico). Reglas de dominio: knowledge/data_models/payment_limits.md.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from payment_limit import validate_payment_limit


# Config de limites de ejemplo (una tabla real vendria de la fuente de compliance).
LIMITS = {
    "AR": {"max_amount": 500000, "allowed_currencies": ["USD", "ARS"]},
    "BR": {"max_amount": 300000, "allowed_currencies": ["USD", "BRL"]},
    "US": {"max_amount": 1000000, "allowed_currencies": ["USD"]},
}


def _valid_payment(**overrides):
    p = {
        "amount": 1000,
        "currency": "USD",
        "country": "AR",
        "beneficiary": {"verified": True, "account": "AR-000-123"},
    }
    p.update(overrides)
    return p


class TestPagosValidos(unittest.TestCase):
    def test_pago_completo_valido(self):
        self.assertEqual(validate_payment_limit(_valid_payment(), LIMITS), [])

    def test_monto_en_el_tope_exacto_es_valido(self):
        p = _valid_payment(amount=500000)  # == max_amount de AR
        self.assertEqual(validate_payment_limit(p, LIMITS), [])

    def test_divisa_local_permitida(self):
        self.assertEqual(validate_payment_limit(_valid_payment(currency="ARS"), LIMITS), [])


class TestLimitePorPais(unittest.TestCase):
    def test_pais_desconocido_es_violacion(self):
        v = validate_payment_limit(_valid_payment(country="XX"), LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("country", v[0])

    def test_monto_sobre_el_tope_del_pais(self):
        v = validate_payment_limit(_valid_payment(amount=500001), LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("amount", v[0])

    def test_tope_es_por_pais_no_global(self):
        # 400000 pasa en AR pero excede el tope de BR (300000): el tope es por pais.
        self.assertEqual(validate_payment_limit(_valid_payment(amount=400000), LIMITS), [])
        v = validate_payment_limit(_valid_payment(country="BR", currency="BRL", amount=400000), LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("amount", v[0])


class TestDivisa(unittest.TestCase):
    def test_divisa_no_permitida_para_el_pais(self):
        v = validate_payment_limit(_valid_payment(currency="EUR"), LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("currency", v[0])


class TestVerificacionBeneficiario(unittest.TestCase):
    def test_beneficiario_no_verificado_bloquea(self):
        p = _valid_payment(beneficiary={"verified": False, "account": "AR-000-123"})
        v = validate_payment_limit(p, LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("beneficiary", v[0])

    def test_beneficiario_sin_cuenta_bloquea(self):
        p = _valid_payment(beneficiary={"verified": True, "account": ""})
        v = validate_payment_limit(p, LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("beneficiary", v[0])

    def test_verified_truthy_no_alcanza_debe_ser_true(self):
        # 1 es truthy pero no es True: KYC no aprobado explicitamente -> bloquea.
        p = _valid_payment(beneficiary={"verified": 1, "account": "AR-000-123"})
        v = validate_payment_limit(p, LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("beneficiary", v[0])


class TestMontoInvalido(unittest.TestCase):
    def test_monto_cero_o_negativo(self):
        for bad in (0, -1):
            v = validate_payment_limit(_valid_payment(amount=bad), LIMITS)
            self.assertEqual(len(v), 1, f"amount={bad}: {v}")
            self.assertIn("amount", v[0])

    def test_monto_booleano_no_es_number(self):
        # True es int en Python pero no es un monto valido: se rechaza.
        v = validate_payment_limit(_valid_payment(amount=True), LIMITS)
        self.assertEqual(len(v), 1)
        self.assertIn("amount", v[0])


class TestAcumulacionYRobustez(unittest.TestCase):
    def test_acumula_todas_las_violaciones(self):
        # pais desconocido + beneficiario sin verificar + monto negativo = 3.
        p = _valid_payment(country="XX", amount=-5,
                           beneficiary={"verified": False, "account": ""})
        v = validate_payment_limit(p, LIMITS)
        self.assertEqual(len(v), 3)

    def test_nunca_lanza_con_tipos_raros(self):
        raros = [
            {"amount": "mil", "currency": 7, "country": None, "beneficiary": "x"},
            {},
            {"amount": [1], "currency": {}, "country": ["AR"], "beneficiary": None},
        ]
        for p in raros:
            r = validate_payment_limit(p, LIMITS)  # no debe lanzar
            self.assertIsInstance(r, list)
            self.assertGreaterEqual(len(r), 1)


if __name__ == "__main__":
    unittest.main()
