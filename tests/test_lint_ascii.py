"""Stub del oraculo de lint-ascii (Contrato 13).

Sellado por el orquestador para que el task contract valide pre-delegacion;
el dev lo REEMPLAZA con la suite real y re-sella tests_sha256 en
knowledge/contracts/lint-ascii.md (contrato de tooling: el dev autora sus
tests; el sello congela el drift futuro, no la autoria presente).
"""

import unittest


class TestStub(unittest.TestCase):
    def test_stub_pending_implementation(self):
        self.skipTest("stub: el dev de C13 reemplaza este archivo")


if __name__ == "__main__":
    unittest.main()
