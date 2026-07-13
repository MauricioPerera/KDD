"""Oraculo congelado del gate de diagramas Mermaid (Contrato: diagram-gate).

Fija el comportamiento de ``scripts/validate_diagrams.py``. Parsers propios en
Python puro (sin subprocess/red/LLM, por 'forbids' de este repo) para 4 tipos
de Mermaid: flowchart/graph, gantt, pie, journey — NO el parser real de
mermaid.

  API por tipo:
    ``parse_flowchart(text) -> {'nodes': [...], 'edges': [...]}``
    ``parse_gantt(text) -> {'tasks': [...], 'sections': [...]}``
    ``parse_pie(text) -> {'slices': [...]}``
    ``parse_journey(text) -> {'tasks': [...], 'sections': [...], 'actors': [...]}``
    ``get_diagram_type(text) -> str|None`` (primer token del texto).
    ``validate_diagram(mmd_path, contract_path) -> list`` — findings
    ``{'file','level','rule','msg'}`` ordenados por (rule, msg).

  Checks y severidad EXACTA, comunes a todos los tipos:
    FILE_ERROR (ERROR)               el .mmd no se pudo leer.
    CONTRACT_INVALID (ERROR)         el .diagram-contract.json no existe o
                                      no es JSON valido.
    DIAGRAM_TYPE_UNSUPPORTED (ERROR) el contrato (o el .mmd) pide/tiene un
                                      diagram_type fuera de
                                      {flowchart, gantt, pie, journey}.
    DIAGRAM_TYPE_MISMATCH (ERROR)    el diagram_type del contrato no
                                      coincide con el del .mmd ('graph' es
                                      alias valido de 'flowchart').

  Checks especificos de 'flowchart':
    MIN_NODES / MAX_NODES (ERROR)    cantidad de nodos fuera de rango.
    MISSING_NODE (ERROR)             un id de required_nodes no aparece.
    NODE_LABEL_MISMATCH (ERROR)      el nodo existe pero su label no
                                      coincide con el declarado.
    MISSING_EDGE (ERROR)             un edge de required_edges no aparece.

  Checks especificos de 'gantt':
    MIN_TASKS / MAX_TASKS (ERROR)    cantidad de tasks fuera de rango.
    MISSING_SECTION (ERROR)          una section de required_sections no
                                      aparece.
    MISSING_TASK (ERROR)             un id de required_tasks no aparece.
    TASK_SECTION_MISMATCH (ERROR)    la task existe pero su section no
                                      coincide.
    TASK_START_MISMATCH / TASK_END_MISMATCH (ERROR) la task existe pero su
                                      start/end (YYYY-MM-DD, derivado de
                                      fecha literal + duracion 'Nd', o de
                                      'after <id>' si <id> ya fue visto
                                      antes en el texto) no coincide con lo
                                      declarado.

  Checks especificos de 'pie':
    MIN_SLICES / MAX_SLICES (ERROR)  cantidad de slices fuera de rango.
    MISSING_SLICE (ERROR)            un label de required_slices no
                                      aparece.
    SLICE_VALUE_MISMATCH (ERROR)     la slice existe pero su value no
                                      coincide.

  Checks especificos de 'journey':
    MIN_TASKS / MAX_TASKS (ERROR)    cantidad de tasks fuera de rango.
    MISSING_SECTION (ERROR)          una section de required_sections no
                                      aparece.
    MISSING_ACTOR (ERROR)            un actor de required_actors no
                                      aparece en ninguna task.
    MISSING_TASK (ERROR)             un texto de required_tasks[].task no
                                      aparece.
    TASK_SECTION_MISMATCH (ERROR)    la task existe pero su section no
                                      coincide.
    TASK_SCORE_MISMATCH (ERROR)      la task existe pero su score no
                                      coincide.
    TASK_MISSING_PERSON (ERROR)      la task existe pero no incluye a una
                                      persona listada en required_tasks[].people
                                      (subset: no exige match exacto).

  CLI (``main(argv)``): uno o mas paths (archivo .mmd o directorio);
  default ``['examples/diagrams']``. Directorio se escanea recursivamente
  por ``*.mmd``; cada .mmd espera un ``<mismo-nombre>.diagram-contract.json``
  al lado. Path inexistente o sin .mmd -> INFO ``PATH_MISSING`` (no bloquea).
  .mmd sin contrato -> WARNING ``CONTRACT_MISSING`` (no bloquea: capa
  opt-in, un diagrama puede existir sin contrato). Exit 1 solo si hay >=1
  ERROR. Resumen: ``Resumen: N error(es), M warning(s), K diagrama(s)
  verificados`` (K = pares .mmd+contrato efectivamente validados).

Este archivo es un ORACULO CONGELADO (tests_sha256): el implementador no lo
modifica. Ver knowledge/contracts/diagram-gate.md.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_diagrams as vd  # noqa: E402


FLOWCHART_OK = (
    "flowchart TD\n"
    "    A[Inicio] --> B{Condicion}\n"
    "    B -->|Si| C[Accion 1]\n"
    "    B -->|No| D[Accion 2]\n"
)

GANTT_OK = (
    "gantt\n"
    "    title Proyecto\n"
    "    dateFormat YYYY-MM-DD\n"
    "    section Diseno\n"
    "    Wireframes :a1, 2026-01-01, 5d\n"
    "    Mockups    :a2, after a1, 3d\n"
    "    section Dev\n"
    "    Backend    :b1, 2026-01-06, 10d\n"
)

PIE_OK = (
    'pie title Distribucion\n'
    '    "A" : 40\n'
    '    "B" : 35\n'
    '    "C" : 25\n'
)

JOURNEY_OK = (
    "journey\n"
    "    title Compra online\n"
    "    section Buscar\n"
    "      Buscar producto: 5: Cliente\n"
    "      Comparar precios: 3: Cliente\n"
    "    section Pagar\n"
    "      Confirmar pago: 4: Cliente, Sistema\n"
)


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="diag_")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def _write(self, name, content):
        p = os.path.join(self.base, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        return p

    def _write_json(self, name, obj):
        return self._write(name, json.dumps(obj))

    def _pair(self, mmd_content, contract_obj, base_name="d"):
        mmd = self._write(base_name + ".mmd", mmd_content)
        self._write_json(base_name + ".diagram-contract.json", contract_obj)
        return mmd, mmd[:-4] + ".diagram-contract.json"

    def _rules(self, findings, level=None):
        if level is None:
            return sorted(f["rule"] for f in findings)
        return sorted(f["rule"] for f in findings if f["level"] == level)


class TestParseFlowchart(unittest.TestCase):
    def test_nodos_y_edges_basicos(self):
        parsed = vd.parse_flowchart(FLOWCHART_OK)
        nodes_by_id = {n["id"]: n["label"] for n in parsed["nodes"]}
        self.assertEqual(nodes_by_id, {
            "A": "Inicio", "B": "Condicion", "C": "Accion 1", "D": "Accion 2",
        })
        edges = [(e["from"], e["to"], e["label"]) for e in parsed["edges"]]
        self.assertEqual(edges, [
            ("A", "B", None), ("B", "C", "Si"), ("B", "D", "No"),
        ])

    def test_nodo_sin_shape_usa_id_como_label(self):
        parsed = vd.parse_flowchart("flowchart TD\n    X --> Y\n")
        nodes_by_id = {n["id"]: n["label"] for n in parsed["nodes"]}
        self.assertEqual(nodes_by_id, {"X": "X", "Y": "Y"})

    def test_diagram_type_flowchart_y_graph(self):
        self.assertEqual(vd.get_diagram_type("flowchart TD\nA-->B"), "flowchart")
        self.assertEqual(vd.get_diagram_type("graph LR\nA-->B"), "graph")

    def test_comentarios_y_lineas_vacias_se_ignoran(self):
        text = "flowchart TD\n\n    %% comentario\n    A --> B\n"
        parsed = vd.parse_flowchart(text)
        self.assertEqual(len(parsed["edges"]), 1)


class TestValidateDiagramEstructura(_Fixture):
    def test_diagrama_valido_sin_findings(self):
        mmd, contract = self._pair(FLOWCHART_OK, {
            "diagram_type": "flowchart",
            "min_nodes": 3, "max_nodes": 10,
            "required_nodes": [{"id": "A", "label": "Inicio"}, {"id": "B"}],
            "required_edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C", "label": "Si"}],
        })
        self.assertEqual(vd.validate_diagram(mmd, contract), [])

    def test_falta_nodo_requerido(self):
        mmd, contract = self._pair(FLOWCHART_OK, {
            "diagram_type": "flowchart",
            "required_nodes": [{"id": "Z"}],
        })
        findings = vd.validate_diagram(mmd, contract)
        self.assertIn("MISSING_NODE", self._rules(findings))
        self.assertTrue(any("'Z'" in f["msg"] for f in findings))

    def test_label_de_nodo_no_coincide(self):
        mmd, contract = self._pair(FLOWCHART_OK, {
            "diagram_type": "flowchart",
            "required_nodes": [{"id": "A", "label": "Otro"}],
        })
        findings = vd.validate_diagram(mmd, contract)
        self.assertIn("NODE_LABEL_MISMATCH", self._rules(findings))

    def test_falta_edge_requerido(self):
        mmd, contract = self._pair(FLOWCHART_OK, {
            "diagram_type": "flowchart",
            "required_edges": [{"from": "C", "to": "A"}],
        })
        findings = vd.validate_diagram(mmd, contract)
        self.assertIn("MISSING_EDGE", self._rules(findings))

    def test_min_nodes_y_max_nodes(self):
        mmd, contract = self._pair(FLOWCHART_OK, {"diagram_type": "flowchart", "min_nodes": 10})
        self.assertIn("MIN_NODES", self._rules(vd.validate_diagram(mmd, contract)))

        mmd2, contract2 = self._pair(FLOWCHART_OK, {"diagram_type": "flowchart", "max_nodes": 1}, "d2")
        self.assertIn("MAX_NODES", self._rules(vd.validate_diagram(mmd2, contract2)))

    def test_diagram_type_mismatch(self):
        mmd, contract = self._pair("graph TD\n    A --> B\n", {"diagram_type": "flowchart"}, "d3")
        # graph es alias valido de flowchart: no debe dar mismatch
        self.assertEqual(vd.validate_diagram(mmd, contract), [])

    def test_diagram_type_unsupported_en_contrato(self):
        mmd, contract = self._pair(FLOWCHART_OK, {"diagram_type": "sequenceDiagram"})
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["DIAGRAM_TYPE_UNSUPPORTED"])

    def test_diagram_type_mismatch_real(self):
        mmd, contract = self._pair(GANTT_OK, {"diagram_type": "flowchart"}, "d4")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["DIAGRAM_TYPE_MISMATCH"])

    def test_diagram_sin_diagram_type_soportado_es_unsupported(self):
        mmd = self._write("no-header.mmd", "sequenceDiagram\n    A->>B: hola\n")
        contract = self._write_json("no-header.diagram-contract.json", {})
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["DIAGRAM_TYPE_UNSUPPORTED"])

    def test_contrato_invalido(self):
        mmd = self._write("bad.mmd", FLOWCHART_OK)
        contract = self._write("bad.diagram-contract.json", "{no es json valido")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["CONTRACT_INVALID"])

    def test_archivo_mmd_inexistente(self):
        contract = self._write_json("x.diagram-contract.json", {"diagram_type": "flowchart"})
        findings = vd.validate_diagram(os.path.join(self.base, "no-existe.mmd"), contract)
        self.assertEqual(self._rules(findings), ["FILE_ERROR"])


class TestParseGantt(unittest.TestCase):
    def test_tasks_fechas_y_secciones(self):
        parsed = vd.parse_gantt(GANTT_OK)
        by_id = {t["id"]: t for t in parsed["tasks"]}
        self.assertEqual(by_id["a1"]["section"], "Diseno")
        self.assertEqual(by_id["a1"]["start"], "2026-01-01")
        self.assertEqual(by_id["a1"]["end"], "2026-01-06")
        self.assertEqual(parsed["sections"], ["Diseno", "Dev"])

    def test_after_resuelve_contra_task_ya_vista(self):
        parsed = vd.parse_gantt(GANTT_OK)
        by_id = {t["id"]: t for t in parsed["tasks"]}
        # a2 empieza 'after a1': a1 termina 2026-01-06, dura 3d -> termina 2026-01-09
        self.assertEqual(by_id["a2"]["start"], "2026-01-06")
        self.assertEqual(by_id["a2"]["end"], "2026-01-09")

    def test_after_no_resuelto_da_start_none(self):
        text = "gantt\n    section S\n    T1 :t1, after nunca-definido, 3d\n"
        parsed = vd.parse_gantt(text)
        self.assertIsNone(parsed["tasks"][0]["start"])
        self.assertIsNone(parsed["tasks"][0]["end"])


class TestParsePie(unittest.TestCase):
    def test_slices_valores_enteros(self):
        parsed = vd.parse_pie(PIE_OK)
        self.assertEqual(parsed["slices"], [
            {"label": "A", "value": 40}, {"label": "B", "value": 35}, {"label": "C", "value": 25},
        ])

    def test_title_se_ignora(self):
        parsed = vd.parse_pie(PIE_OK)
        self.assertEqual(len(parsed["slices"]), 3)


class TestParseJourney(unittest.TestCase):
    def test_tasks_secciones_y_actores(self):
        parsed = vd.parse_journey(JOURNEY_OK)
        self.assertEqual(parsed["sections"], ["Buscar", "Pagar"])
        self.assertEqual(parsed["actors"], ["Cliente", "Sistema"])
        confirmar = next(t for t in parsed["tasks"] if t["task"] == "Confirmar pago")
        self.assertEqual(confirmar["score"], 4)
        self.assertEqual(confirmar["people"], ["Cliente", "Sistema"])
        self.assertEqual(confirmar["section"], "Pagar")


class TestValidateGantt(_Fixture):
    def test_diagrama_valido_sin_findings(self):
        mmd, contract = self._pair(GANTT_OK, {
            "diagram_type": "gantt",
            "min_tasks": 2, "max_tasks": 5,
            "required_sections": ["Diseno", "Dev"],
            "required_tasks": [
                {"id": "a1", "section": "Diseno", "start": "2026-01-01", "end": "2026-01-06"},
                {"id": "a2", "start": "2026-01-06"},
            ],
        }, "gantt-ok")
        self.assertEqual(vd.validate_diagram(mmd, contract), [])

    def test_falta_section_y_task(self):
        mmd, contract = self._pair(GANTT_OK, {
            "diagram_type": "gantt",
            "required_sections": ["QA"],
            "required_tasks": [{"id": "z9"}],
        }, "gantt-fail")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["MISSING_SECTION", "MISSING_TASK"])

    def test_start_end_mismatch(self):
        mmd, contract = self._pair(GANTT_OK, {
            "diagram_type": "gantt",
            "required_tasks": [{"id": "a1", "start": "2020-01-01", "end": "2020-01-02"}],
        }, "gantt-dates")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["TASK_END_MISMATCH", "TASK_START_MISMATCH"])

    def test_min_max_tasks(self):
        mmd, contract = self._pair(GANTT_OK, {"diagram_type": "gantt", "min_tasks": 10}, "gantt-min")
        self.assertIn("MIN_TASKS", self._rules(vd.validate_diagram(mmd, contract)))

        mmd2, contract2 = self._pair(GANTT_OK, {"diagram_type": "gantt", "max_tasks": 1}, "gantt-max")
        self.assertIn("MAX_TASKS", self._rules(vd.validate_diagram(mmd2, contract2)))


class TestValidatePie(_Fixture):
    def test_diagrama_valido_sin_findings(self):
        mmd, contract = self._pair(PIE_OK, {
            "diagram_type": "pie",
            "min_slices": 2, "max_slices": 5,
            "required_slices": [{"label": "A", "value": 40}, {"label": "B"}],
        }, "pie-ok")
        self.assertEqual(vd.validate_diagram(mmd, contract), [])

    def test_falta_slice_y_value_no_coincide(self):
        mmd, contract = self._pair(PIE_OK, {
            "diagram_type": "pie",
            "required_slices": [{"label": "Z"}, {"label": "A", "value": 99}],
        }, "pie-fail")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["MISSING_SLICE", "SLICE_VALUE_MISMATCH"])

    def test_min_max_slices(self):
        mmd, contract = self._pair(PIE_OK, {"diagram_type": "pie", "min_slices": 10}, "pie-min")
        self.assertIn("MIN_SLICES", self._rules(vd.validate_diagram(mmd, contract)))

        mmd2, contract2 = self._pair(PIE_OK, {"diagram_type": "pie", "max_slices": 1}, "pie-max")
        self.assertIn("MAX_SLICES", self._rules(vd.validate_diagram(mmd2, contract2)))


class TestValidateJourney(_Fixture):
    def test_diagrama_valido_sin_findings(self):
        mmd, contract = self._pair(JOURNEY_OK, {
            "diagram_type": "journey",
            "min_tasks": 2, "max_tasks": 6,
            "required_sections": ["Buscar", "Pagar"],
            "required_actors": ["Cliente", "Sistema"],
            "required_tasks": [
                {"task": "Buscar producto", "section": "Buscar", "score": 5},
                {"task": "Confirmar pago", "people": ["Cliente", "Sistema"]},
            ],
        }, "journey-ok")
        self.assertEqual(vd.validate_diagram(mmd, contract), [])

    def test_falta_section_actor_y_task(self):
        mmd, contract = self._pair(JOURNEY_OK, {
            "diagram_type": "journey",
            "required_sections": ["Devolver"],
            "required_actors": ["Soporte"],
            "required_tasks": [{"task": "Reclamar garantia"}],
        }, "journey-fail")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["MISSING_ACTOR", "MISSING_SECTION", "MISSING_TASK"])

    def test_score_mismatch_y_persona_faltante(self):
        mmd, contract = self._pair(JOURNEY_OK, {
            "diagram_type": "journey",
            "required_tasks": [
                {"task": "Buscar producto", "score": 1},
                {"task": "Confirmar pago", "people": ["Soporte"]},
            ],
        }, "journey-mismatch")
        findings = vd.validate_diagram(mmd, contract)
        self.assertEqual(self._rules(findings), ["TASK_MISSING_PERSON", "TASK_SCORE_MISMATCH"])

    def test_min_max_tasks(self):
        mmd, contract = self._pair(JOURNEY_OK, {"diagram_type": "journey", "min_tasks": 10}, "journey-min")
        self.assertIn("MIN_TASKS", self._rules(vd.validate_diagram(mmd, contract)))

        mmd2, contract2 = self._pair(JOURNEY_OK, {"diagram_type": "journey", "max_tasks": 1}, "journey-max")
        self.assertIn("MAX_TASKS", self._rules(vd.validate_diagram(mmd2, contract2)))


class TestMain(_Fixture):
    def _run_main(self, argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = vd.main(argv)
        return exit_code, buf.getvalue()

    def test_path_inexistente_da_info_y_exit_0(self):
        exit_code, out = self._run_main([os.path.join(self.base, "no-existe")])
        self.assertEqual(exit_code, 0)
        self.assertIn("PATH_MISSING", out)

    def test_mmd_sin_contrato_da_warning_no_bloquea(self):
        mmd = self._write("solo.mmd", FLOWCHART_OK)
        exit_code, out = self._run_main([mmd])
        self.assertEqual(exit_code, 0)
        self.assertIn("CONTRACT_MISSING", out)

    def test_par_valido_exit_0(self):
        mmd, _ = self._pair(FLOWCHART_OK, {"diagram_type": "flowchart", "required_nodes": [{"id": "A"}]})
        exit_code, out = self._run_main([mmd])
        self.assertEqual(exit_code, 0)
        self.assertIn("Resumen: 0 error(es), 0 warning(s), 1 diagrama(s) verificados", out)

    def test_par_invalido_exit_1(self):
        mmd, _ = self._pair(FLOWCHART_OK, {"diagram_type": "flowchart", "required_nodes": [{"id": "Z"}]})
        exit_code, out = self._run_main([mmd])
        self.assertEqual(exit_code, 1)

    def test_directorio_recursivo(self):
        sub = os.path.join(self.base, "sub")
        os.makedirs(sub)
        with open(os.path.join(sub, "e.mmd"), "w", encoding="utf-8") as fh:
            fh.write(FLOWCHART_OK)
        with open(os.path.join(sub, "e.diagram-contract.json"), "w", encoding="utf-8") as fh:
            json.dump({"diagram_type": "flowchart"}, fh)
        exit_code, out = self._run_main([self.base])
        self.assertEqual(exit_code, 0)
        self.assertIn("1 diagrama(s) verificados", out)


if __name__ == "__main__":
    unittest.main()
