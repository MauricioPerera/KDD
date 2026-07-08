"""Oraculo congelado del contrato check-graph (Contrato 22).

Autorado por el orquestador ANTES de la delegacion. El implementador de
src/check_workflow_graph.py NO escribe ni modifica este archivo.

Contrato:
    find_graph_cycles(connections: dict) -> list
connections = {nodo: [destinos]}. Devuelve una lista de violaciones legibles
(vacia = sin ciclos), cada una con prefijo "connections:" y el camino del
ciclo en FORMA CANONICA: rotado para empezar en su nodo lexicograficamente
menor, con el nodo inicial repetido al final ("connections: ciclo A -> B -> A").
Cada ciclo se reporta UNA vez; violaciones ordenadas; entradas malformadas
(no-dict, destinos no-lista, destinos no-string) se saltan sin lanzar.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from check_workflow_graph import find_graph_cycles


class TestSinCiclos(unittest.TestCase):
    def test_vacio_y_lineal(self):
        self.assertEqual(find_graph_cycles({}), [])
        self.assertEqual(find_graph_cycles({"A": ["B"], "B": ["C"], "C": []}), [])

    def test_diamante_no_es_ciclo(self):
        # A->B, A->C, B->D, C->D: convergencia en D, cero ciclos (el falso
        # positivo clasico de un DFS mal hecho).
        g = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        self.assertEqual(find_graph_cycles(g), [])

    def test_destino_inexistente_no_es_ciclo(self):
        # Apuntar a un nodo sin entrada propia no es ciclo (la forma la valida
        # el rule contract del dominio, no este checker).
        self.assertEqual(find_graph_cycles({"A": ["Z"]}), [])


class TestCiclos(unittest.TestCase):
    def test_self_loop(self):
        v = find_graph_cycles({"A": ["A"]})
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0].startswith("connections:"), v[0])
        self.assertIn("A -> A", v[0])

    def test_ciclo_de_dos_forma_canonica(self):
        # El caso FRONTERA del golden de C20.
        v = find_graph_cycles({"A": ["B"], "B": ["A"]})
        self.assertEqual(len(v), 1, v)
        self.assertIn("A -> B -> A", v[0])

    def test_canonica_empieza_en_el_menor(self):
        # Mismo ciclo declarado "al reves": la forma canonica no cambia.
        v = find_graph_cycles({"B": ["A"], "A": ["B"]})
        self.assertEqual(len(v), 1, v)
        self.assertIn("A -> B -> A", v[0])

    def test_ciclo_largo(self):
        v = find_graph_cycles({"C": ["A"], "A": ["B"], "B": ["C"]})
        self.assertEqual(len(v), 1, v)
        self.assertIn("A -> B -> C -> A", v[0])

    def test_ciclo_en_componente_desconectado(self):
        g = {"A": ["B"], "B": [], "X": ["Y"], "Y": ["X"]}
        v = find_graph_cycles(g)
        self.assertEqual(len(v), 1, v)
        self.assertIn("X -> Y -> X", v[0])

    def test_multiples_ciclos_una_vez_cada_uno_y_ordenados(self):
        g = {"A": ["A"], "X": ["Y"], "Y": ["X"]}
        v = find_graph_cycles(g)
        self.assertEqual(len(v), 2, v)
        self.assertEqual(v, sorted(v))
        self.assertIn("A -> A", v[0])
        self.assertIn("X -> Y -> X", v[1])


class TestRobustezYDeterminismo(unittest.TestCase):
    def test_malformados_sin_lanzar(self):
        for g in ("no-dict", 42, None, {"A": "no-lista"}, {"A": [1, None]}, {5: ["A"]}):
            out = find_graph_cycles(g)  # no debe lanzar
            self.assertIsInstance(out, list)

    def test_mixto_malformado_mas_ciclo_real(self):
        # Lo malformado se salta; el ciclo real se reporta igual.
        g = {"A": "no-lista", "X": ["Y"], "Y": ["X"]}
        v = find_graph_cycles(g)
        self.assertEqual(len(v), 1, v)
        self.assertIn("X -> Y -> X", v[0])

    def test_determinista(self):
        g = {"B": ["A"], "A": ["B"], "C": ["C"]}
        self.assertEqual(find_graph_cycles(g), find_graph_cycles(g))


if __name__ == "__main__":
    unittest.main()
