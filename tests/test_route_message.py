"""Oraculo congelado del contrato route-message (Contrato 21, ejemplo didactico).

Autorado por el orquestador ANTES de la delegacion. El implementador de
src/route_message.py NO escribe ni modifica este archivo. Politica:
knowledge/data_models/message_routing.md.

Contrato:
    route_message(message: dict, routing: dict) -> str
routing = {"senders": {<email minusculas>: <ruta>}, "default": <ruta>}.
El emisor (message["sender"]) se normaliza a minusculas antes de buscar en
senders; ausente, no-string o no listado -> routing["default"]. Nunca lanza.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from route_message import route_message


ROUTING = {"senders": {"vip@acme.com": "A", "soporte@acme.com": "A"}, "default": "B"}


class TestEmisorListado(unittest.TestCase):
    def test_emisor_y_va_a_a(self):
        self.assertEqual(route_message({"sender": "vip@acme.com"}, ROUTING), "A")

    def test_normaliza_mayusculas(self):
        self.assertEqual(route_message({"sender": "VIP@ACME.COM"}, ROUTING), "A")
        self.assertEqual(route_message({"sender": "Soporte@Acme.Com"}, ROUTING), "A")


class TestRamaElse(unittest.TestCase):
    def test_emisor_no_listado_va_a_default(self):
        self.assertEqual(route_message({"sender": "otro@x.com"}, ROUTING), "B")

    def test_emisor_ausente_va_a_default(self):
        self.assertEqual(route_message({}, ROUTING), "B")
        self.assertEqual(route_message({"sender": None}, ROUTING), "B")

    def test_emisor_no_string_va_a_default(self):
        for raro in (42, ["vip@acme.com"], {"x": 1}, True):
            self.assertEqual(route_message({"sender": raro}, ROUTING), "B", raro)

    def test_tabla_de_senders_vacia_todo_a_default(self):
        r = {"senders": {}, "default": "B"}
        self.assertEqual(route_message({"sender": "vip@acme.com"}, r), "B")


class TestPurezaYRobustez(unittest.TestCase):
    def test_la_tabla_entra_por_argumento(self):
        # Dos tablas distintas, mismo mensaje: la decision depende SOLO de los argumentos.
        r2 = {"senders": {"vip@acme.com": "Z"}, "default": "Q"}
        self.assertEqual(route_message({"sender": "vip@acme.com"}, ROUTING), "A")
        self.assertEqual(route_message({"sender": "vip@acme.com"}, r2), "Z")
        self.assertEqual(route_message({"sender": "nadie@x.com"}, r2), "Q")

    def test_determinista(self):
        m = {"sender": "vip@acme.com"}
        self.assertEqual(route_message(m, ROUTING), route_message(m, ROUTING))

    def test_nunca_lanza_con_mensajes_raros(self):
        for m in ({}, {"sender": object()}, {"otro": "campo"}):
            out = route_message(m, ROUTING)  # no debe lanzar
            self.assertIsInstance(out, str)


if __name__ == "__main__":
    unittest.main()
