"""Tests unitarios del ensamblador de contexto CCDD Nivel 2 (KDD).

Cubren lo que lista la seccion Tests del task contract
``knowledge/contracts/assemble-context.md``: presupuesto respetado,
prioridades, truncado, min_tokens, firma estable, determinismo 2x,
retriever por mencion/tags/fallback, regex_deny aborta, reference_check
detecta y pasa, exit codes del CLI.

Los tests PUEDEN usar subprocess para probar el CLI (patron estandar); el
target ``scripts/assemble_context.py`` NO usa subprocess (forbids del task
contract).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import assemble_context as ac  # noqa: E402


def _write(d, name, content):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content)
    return p


def _node(name, tags, body):
    fm = "---\ntype: 'Concept'\ntitle: '{}'\ndescription: 'x'\ntags: {}\n---\n" \
        .format(name, tags)
    return fm + "# " + name + "\n\n" + body


# ---------------------------------------------------------------------------
# Funcion assemble()
# ---------------------------------------------------------------------------

class TestBudgetAndPriorities(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.makedirs(os.path.join(self.d, "knowledge"))
        # aaa (prio 0) cabe holgado; bbb (prio 10) es enorme y con none no recorta
        _write(self.d, "knowledge/aaa.md", _node("aaa", "['x']",
                "x" * 1000))  # ~250 tokens
        _write(self.d, "knowledge/bbb.md", _node("bbb", "['y']",
                "y" * 60000))  # ~15000 tokens, excede el remanente

    def tearDown(self):
        self.tmp.cleanup()

    def _contract(self):
        return {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "big", "source": "static", "path": "knowledge/aaa.md",
                 "compaction": "none", "max_tokens": 1800, "priority": 0},
                {"id": "small", "source": "static", "path": "knowledge/bbb.md",
                 "compaction": "none", "priority": 10},
            ],
        }

    def test_presupuesto_respetado(self):
        r = ac.assemble(self._contract(), "tarea", self.d)
        self.assertLessEqual(r["used"], r["available"])

    def test_prioridades_orden_y_omision(self):
        # prio 0 (big/aaa, none, max 1800): ~250 tokens < 1800 -> incluido.
        # prio 10 (small/bbb, none): remanente ~1750, contenido ~15000 tokens
        # -> con none no recorta y excede -> omitido. Confirma orden: el de
        # prioridad mas baja se lleva el presupuesto primero.
        r = ac.assemble(self._contract(), "tarea", self.d)
        by_id = {s["id"]: s for s in r["slots"]}
        self.assertEqual(by_id["big"]["status"], "included")
        self.assertEqual(by_id["small"]["status"], "omitted")
        self.assertLessEqual(r["used"], r["available"])


class TestTruncateAndMinTokens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.makedirs(os.path.join(self.d, "knowledge"))
        _write(self.d, "knowledge/big.md", _node("big", "['t']",
                "abcdefghij " * 5000))  # ~60000 chars ~15000 tokens

    def tearDown(self):
        self.tmp.cleanup()

    def test_truncate_recorta_y_marca(self):
        contract = {
            "budget": {"max_tokens": 400, "output_reserve": 0},
            "slots": [
                {"id": "s", "source": "static", "path": "knowledge/big.md",
                 "compaction": "truncate", "max_tokens": 100, "priority": 0},
            ],
        }
        r = ac.assemble(contract, "tarea", self.d)
        s = r["slots"][0]
        self.assertEqual(s["status"], "included")
        self.assertLessEqual(s["tokens"], 100)  # respeta el tope
        self.assertIn(ac._TRUNC_MARKER, r["context"])

    def test_min_tokens_piso_omite(self):
        # cap = 100, min_tokens = 200 -> omitido pese a compaction truncate
        contract = {
            "budget": {"max_tokens": 100, "output_reserve": 0},
            "slots": [
                {"id": "s", "source": "static", "path": "knowledge/big.md",
                 "compaction": "truncate", "max_tokens": 100,
                 "min_tokens": 200, "priority": 0},
            ],
        }
        r = ac.assemble(contract, "tarea", self.d)
        self.assertEqual(r["slots"][0]["status"], "omitted")
        self.assertEqual(r["slots"][0]["tokens"], 0)


class TestSignAndDeterminism(unittest.TestCase):
    def test_firma_estable_y_sha12(self):
        contract = {
            "budget": {"max_tokens": 100000, "output_reserve": 0},
            "slots": [
                {"id": "spec", "source": "static",
                 "path": "knowledge/OKF-SPEC.md", "compaction": "none",
                 "sign": True, "priority": 0},
            ],
        }
        r1 = ac.assemble(contract, "t", ROOT)
        r2 = ac.assemble(contract, "t", ROOT)
        sign1 = r1["slots"][0]["sign"]
        sign2 = r2["slots"][0]["sign"]
        self.assertEqual(sign1, sign2)
        # sha256[:12] del contenido incluido
        import hashlib
        expected = hashlib.sha256(
            r1["context"].split("### slot: spec\n", 1)[1].encode("utf-8")
        ).hexdigest()[:12]
        self.assertEqual(sign1, expected)

    @unittest.skipUnless(
        os.path.isfile(os.path.join(ROOT, "knowledge", "data_models",
                                    "users_table.md")),
        "ejemplo removido por init: knowledge/data_models/users_table.md")
    def test_determinismo_dos_corridas(self):
        # Skip-guard preventivo (acoplamiento autorizado por C06): corre el
        # retriever sobre la KB real con la tarea "documentar la tabla users"
        # (nodo de ejemplo users_table). Post-init users_table se elimina,
        # pero el fallback del retriever preserva el determinismo; el guard es
        # preventivo (post-init nada falla aca) y se saltea limpio.
        contract = {
            "budget": {"max_tokens": 16000, "output_reserve": 3000},
            "slots": [
                {"id": "okf_spec", "source": "static",
                 "path": "knowledge/OKF-SPEC.md", "compaction": "none",
                 "sign": True, "priority": 0},
                {"id": "okf_index", "source": "dynamic",
                 "provider": "okf_index", "compaction": "none", "priority": 10},
                {"id": "okf_nodes", "source": "dynamic",
                 "provider": "okf_nodes", "compaction": "summarize",
                 "max_tokens": 6000, "priority": 20},
                {"id": "user_task", "source": "runtime",
                 "compaction": "truncate", "priority": 30},
            ],
            "guardrails": {
                "regex_deny": {"patterns": ["api_key="], "on_fail": "abort"},
                "reference_check": {"on_fail": "report"},
            },
        }
        r1 = ac.assemble(contract, "documentar la tabla users", ROOT)
        r2 = ac.assemble(contract, "documentar la tabla users", ROOT)
        a = json.dumps(r1, sort_keys=True)
        b = json.dumps(r2, sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(r1["context"], r2["context"])


class TestRetriever(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.makedirs(os.path.join(self.d, "knowledge"))
        os.makedirs(os.path.join(self.d, "knowledge", "data_models"))
        _write(self.d, "knowledge/data_models/users_table.md",
               _node("users_table", "['data-model','users','example']",
                     "campos de users"))
        _write(self.d, "knowledge/architecture_overview.md",
               _node("architecture_overview", "['architecture','overview']",
                     "vista general"))
        _write(self.d, "knowledge/concept_zzz.md",
               _node("concept_zzz", "['zzztag']", "sin relacion"))
        _write(self.d, "knowledge/index.md",
               "# Index\n\n- [users](data_models/users_table.md)\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _nodes(self, task):
        contract = {
            "budget": {"max_tokens": 100000, "output_reserve": 0},
            "slots": [
                {"id": "n", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        r = ac.assemble(contract, task, self.d)
        return r["slots"][0]["selected"]

    def test_match_por_tag(self):
        # "users" es un tag de users_table -> match por tag
        sel = self._nodes("documentar la tabla users")
        self.assertIn("users_table", sel)

    def test_match_por_mencion(self):
        # nombre de archivo "architecture_overview" mencionado en la tarea
        sel = self._nodes("explicar architecture_overview del sistema")
        self.assertIn("architecture_overview", sel)
        self.assertNotIn("users_table", sel)

    def test_fallback_todos(self):
        sel = self._nodes("tarea sin relacion con nodos")
        # todos los .md de knowledge/ en orden alfabetico
        self.assertEqual(sel, sorted(sel))
        self.assertIn("users_table", sel)
        self.assertIn("architecture_overview", sel)
        self.assertIn("concept_zzz", sel)
        self.assertIn("index", sel)


class TestGuardrails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.makedirs(os.path.join(self.d, "knowledge"))
        _write(self.d, "knowledge/index.md", "# Index\n")
        _write(self.d, "knowledge/real.md", _node("real", "['t']", "ok"))

    def tearDown(self):
        self.tmp.cleanup()


    def test_reference_check_detecta_inexistente(self):
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {"reference_check": {"on_fail": "report"}},
        }
        r = ac.assemble(contract, "revisar knowledge/no-existe.md", self.d)
        self.assertFalse(r["guardrails"]["ok"])
        joined = " ".join(r["guardrails"]["findings"])
        self.assertIn("knowledge/no-existe.md", joined)
        self.assertIn("reference_check", joined)

    def test_reference_check_pasa_con_existentes(self):
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {"reference_check": {"on_fail": "report"}},
        }
        r = ac.assemble(contract, "revisar knowledge/real.md", self.d)
        self.assertTrue(r["guardrails"]["ok"])
        self.assertEqual(r["guardrails"]["findings"], [])

    # --- CTX-HONESTO (T8): regex real + reporte honesto --------------------

    def test_regex_deny_evalua_con_re_search(self):
        # 'secret\\s*:' es un patron regex: matchea 'secret :' y 'secret:'.
        # Como substring literal, la cadena 'secret\\s*:' NO estaria en el
        # contexto -> el behavior viejo (pat in context) no abortaria. Con
        # re.search real si aborta. Prueba que regex_deny evalua de verdad.
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {
                "regex_deny": {"patterns": [r"secret\s*:"], "on_fail": "abort"},
            },
        }
        # 'secret :' (con espacio) matchea por \s*; substring literal no.
        with self.assertRaises(ac.GuardrailAbort):
            ac.assemble(contract, "log line: secret : value", self.d)
        # 'secret:' (sin espacio) tambien matchea por \s* (cero espacios).
        with self.assertRaises(ac.GuardrailAbort):
            ac.assemble(contract, "log line: secret:value", self.d)

    def test_regex_deny_patron_invalido_lanza_valueerror(self):
        # '[' no compila como regex -> ValueError que nombra el patron,
        # no silencio ni fallback a matching literal.
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {
                "regex_deny": {"patterns": ["["], "on_fail": "abort"},
            },
        }
        with self.assertRaises(ValueError) as cm:
            ac.assemble(contract, "tarea", self.d)
        msg = str(cm.exception)
        self.assertIn("regex_deny", msg)
        self.assertIn("[", msg)

    def test_regex_deny_patron_alfanumerico_mismo_veredicto(self):
        # 'api_key=' no tiene metacaracteres regex: mismo veredicto que con
        # substring literal (compatibilidad con ccdd/context.json).
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {
                "regex_deny": {"patterns": ["api_key="], "on_fail": "abort"},
            },
        }
        with self.assertRaises(ac.GuardrailAbort):
            ac.assemble(contract, "mi api_key=secret123", self.d)
        # sin la cadena literal presente, no aborta.
        r = ac.assemble(contract, "tarea sin secreto", self.d)
        self.assertTrue(r["guardrails"]["ok"])

    def test_reporte_omite_guardrails_no_configurados(self):
        # Contrato SIN ningun guardrail: el reporte no menciona regex_deny ni
        # reference_check.
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
        }
        r = ac.assemble(contract, "tarea", self.d)
        report = ac.format_report(r, "contract.json", "tarea")
        self.assertNotIn("regex_deny", report)
        self.assertNotIn("reference_check", report)
        self.assertEqual(r["guardrails"]["configured"], [])

    def test_reporte_lista_solo_guardrails_configurados(self):
        # Solo reference_check configurado (sin regex_deny): el reporte
        # menciona 'reference_check: ok' pero NO menciona regex_deny.
        contract = {
            "budget": {"max_tokens": 10000, "output_reserve": 0},
            "slots": [
                {"id": "task", "source": "runtime", "compaction": "none",
                 "priority": 0},
            ],
            "guardrails": {"reference_check": {"on_fail": "report"}},
        }
        r = ac.assemble(contract, "tarea sin refs", self.d)
        report = ac.format_report(r, "contract.json", "tarea sin refs")
        self.assertIn("reference_check", report)
        self.assertNotIn("regex_deny", report)
        self.assertEqual(r["guardrails"]["configured"], ["reference_check"])


class TestContractValidation(unittest.TestCase):
    def test_budget_ausente_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            ac.assemble({"slots": []}, "t", ROOT)

    def test_max_tokens_no_positivo(self):
        with self.assertRaises(ValueError):
            ac.assemble({"budget": {"max_tokens": 0, "output_reserve": 0},
                         "slots": [{"id": "a", "source": "runtime",
                                    "priority": 0}]}, "t", ROOT)

    def test_slots_vacio(self):
        with self.assertRaises(ValueError):
            ac.assemble({"budget": {"max_tokens": 10, "output_reserve": 0},
                         "slots": []}, "t", ROOT)

    def test_static_sin_path(self):
        with self.assertRaises(ValueError):
            ac.assemble({"budget": {"max_tokens": 10, "output_reserve": 0},
                         "slots": [{"id": "a", "source": "static",
                                    "priority": 0}]}, "t", ROOT)


# ---------------------------------------------------------------------------
# CLI via subprocess (exit codes)
# ---------------------------------------------------------------------------

def _run_cli(args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "assemble_context.py")]
        + args,
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


class TestCLIExitCodes(unittest.TestCase):
    def test_exit_0_ok(self):
        r = _run_cli(["ccdd/context.json", "documentar la tabla users"])
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        self.assertIn("guardrails: ok", r.stdout)

    def test_exit_2_contrato_invalido(self):
        with tempfile.TemporaryDirectory() as d:
            bad = _write(d, "bad.json",
                         json.dumps({"budget": {"max_tokens": 0,
                                                 "output_reserve": 0}}))
            r = _run_cli([bad, "t"], cwd=d)
        self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)

    def test_exit_2_guardrail_abort(self):
        r = _run_cli(["ccdd/context.json", "mi api_key=secret123"])
        self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)
        self.assertIn("ABORT", r.stderr)

    def test_exit_1_io_contrato_inexistente(self):
        r = _run_cli(["ccdd/no-existe.json", "t"])
        self.assertEqual(r.returncode, 1, msg=r.stdout + r.stderr)

    def test_cli_determinismo_stdout(self):
        r1 = _run_cli(["ccdd/context.json", "documentar la tabla users"])
        r2 = _run_cli(["ccdd/context.json", "documentar la tabla users"])
        self.assertEqual(r1.stdout, r2.stdout)


# ---------------------------------------------------------------------------
# Tests para CONTRACT-15: ranking, corte por nodo, reporte honesto, chars_per_token
# ---------------------------------------------------------------------------

class TestRankingAndCutting(unittest.TestCase):
    """Tests para las 4 decisiones de diseño de CONTRACT-15."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        os.makedirs(os.path.join(self.d, "knowledge"))

        # Crea 3 nodos para testing:
        # - high_priority: nombre mencionado en tarea (score=2)
        # - medium_match: solo match por tag (score=1)
        # - low_no_match: sin match
        # Cada nodo: ~2000 chars = ~500 tokens (con chars_per_token=4)
        _write(self.d, "knowledge/high_priority.md",
               _node("high_priority", "['tag_x']", "x" * 2000))  # ~500 tokens
        _write(self.d, "knowledge/medium_match.md",
               _node("medium_match", "['special_tag']",
                     "y" * 2000))  # ~500 tokens
        _write(self.d, "knowledge/low_no_match.md",
               _node("low_no_match", "['tag_z']", "z" * 2000))  # ~500 tokens

    def tearDown(self):
        self.tmp.cleanup()

    def _nodes(self, task, max_tokens_slot=None):
        """Helper que retorna el resultado de okf_nodes para una tarea."""
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        if max_tokens_slot is not None:
            contract["slots"][0]["max_tokens"] = max_tokens_slot
        r = ac.assemble(contract, task, self.d)
        return r["slots"][0]

    def test_ranking_mencion_gana_a_tag(self):
        # task menciona "high_priority" (nombre) y "special_tag" (tag de medium_match)
        # esperado: high_priority (score 2) ANTES que medium_match (score 1) en
        # el ORDEN DE ENSAMBLADO del contexto (selected es alfabetico, compat)
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        r = ac.assemble(contract, "explicar high_priority y special_tag",
                        self.d)
        ctx = r["context"]
        self.assertLess(ctx.index("# high_priority"),
                        ctx.index("# medium_match"),
                        "mencion de nombre debe vencer a match por tag")
        # selected sigue siendo alfabetico con TODOS los recuperados
        self.assertEqual(r["slots"][0]["selected"],
                         ["high_priority", "medium_match"])

    def test_ranking_empate_alfabetico(self):
        # Crea dos nodos con mismo score (ambos solo match por tag)
        _write(self.d, "knowledge/aaa_tag.md",
               _node("aaa_tag", "['shared_tag']", "a" * 100))
        _write(self.d, "knowledge/zzz_tag.md",
               _node("zzz_tag", "['shared_tag']", "z" * 100))
        # Task menciona solo el tag (ambos tienen score 1): en el empate el
        # orden de ensamblado del contexto es alfabetico
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        r = ac.assemble(contract, "documento con shared_tag", self.d)
        ctx = r["context"]
        self.assertLess(ctx.index("# aaa_tag"), ctx.index("# zzz_tag"),
                        "en caso de empate de score, alfabetico gana")
        self.assertEqual(r["slots"][0]["selected"], ["aaa_tag", "zzz_tag"])

    def test_corte_por_nodo_con_presupuesto_justo(self):
        # Presupuesto justo para ranking con 3 nodos matched.
        # Crea un tercer nodo que matchea por tag
        _write(self.d, "knowledge/third_match.md",
               _node("third_match", "['special_tag']", "t" * 2000))  # ~500 tokens
        # Task menciona high_priority (score 2), y dos nodos con special_tag (score 1)
        # Ranking: high_priority, medium_match, third_match (empate 1-1 alfabetico)
        # max_tokens=900 -> cabe high_priority entero + medium_match compactado,
        # third_match omitido. Aserciones EXACTAS sobre el REPORTE del slot.
        slot = self._nodes("high_priority special_tag", max_tokens_slot=900)
        # selected = universo COMPLETO recuperado (compat, alfabetico)
        self.assertEqual(slot["selected"],
                         ["high_priority", "medium_match", "third_match"],
                         "selected lista TODOS los recuperados (compat)")
        self.assertEqual(slot.get("cut"), "medium_match",
                         "el reporte declara el nodo compactado exacto")
        self.assertEqual(slot.get("omitted_nodes"), ["third_match"],
                         "el reporte declara los omitidos exactos")
        # Particion: selected = incluidos enteros | {cut} | omitidos
        incluidos = (set(slot["selected"]) - {slot["cut"]}
                     - set(slot["omitted_nodes"]))
        self.assertEqual(incluidos, {"high_priority"},
                         "incluidos enteros = selected - cut - omitidos")
        self.assertEqual(set(slot["selected"]),
                         incluidos | {slot["cut"]} | set(slot["omitted_nodes"]),
                         "selected es la union exacta de las tres partes")

    def test_fallback_presupuesto_justo_declara_cut_y_omitidos(self):
        # Fixture estilo PM: tarea SIN matches (fallback, orden alfabetico)
        # con presupuesto justo -> el REPORTE igual declara cut y omitted_nodes.
        # Orden alfabetico: high_priority, low_no_match, medium_match
        # max_tokens=900 -> high_priority entero, low_no_match cut,
        # medium_match omitido.
        slot = self._nodes("tarea sin relacion xyz", max_tokens_slot=900)
        # selected = universo COMPLETO recuperado (fallback: todos)
        self.assertEqual(slot["selected"],
                         ["high_priority", "low_no_match", "medium_match"])
        self.assertEqual(slot.get("cut"), "low_no_match",
                         "fallback con presupuesto justo declara cut")
        self.assertEqual(slot.get("omitted_nodes"), ["medium_match"],
                         "fallback con presupuesto justo declara omitidos")

    def test_format_report_muestra_cut_y_omitted(self):
        # La linea del slot en el reporte CLI muestra cut=<id> y omitted=[...]
        # cuando existen (y no los muestra cuando no)
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "max_tokens": 900, "priority": 0},
            ],
        }
        r = ac.assemble(contract, "tarea sin relacion xyz", self.d)
        report = ac.format_report(r, "contract.json", "tarea sin relacion xyz")
        self.assertIn("cut=low_no_match", report)
        self.assertIn("omitted=[medium_match]", report)
        # Con presupuesto holgado, ninguna de las dos aparece
        contract["slots"][0]["max_tokens"] = 2000
        r2 = ac.assemble(contract, "tarea sin relacion xyz", self.d)
        report2 = ac.format_report(r2, "contract.json",
                                   "tarea sin relacion xyz")
        self.assertNotIn("cut=", report2)
        self.assertNotIn("omitted=", report2)

    def test_reporte_sin_cut_cuando_todo_cabe(self):
        # Presupuesto holgado: caben todos sin corte
        slot = self._nodes("fallback", max_tokens_slot=2000)
        # Todos deben estar seleccionados
        self.assertEqual(len(slot["selected"]), 3)
        # No debe haber "cut" ni "omitted_nodes" cuando todo cabe
        self.assertNotIn("cut", slot,
                        "no debe haber cut key cuando todo cabe")
        self.assertNotIn("omitted_nodes", slot,
                        "no debe haber omitted_nodes key cuando todo cabe")

    def test_fallback_sin_matches_byte_identico(self):
        # Tarea sin relacion alguna -> fallback a todos con score 0.
        # Con presupuesto holgado, el contexto queda CONGELADO al comportamiento
        # previo: concatenacion "\n\n" de TODOS los nodos en orden alfabetico
        # (byte-identico), sin claves cut/omitted_nodes en el reporte.
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "none", "priority": 0},
            ],
        }
        r1 = ac.assemble(contract, "tarea sin relacion xyz", self.d)
        r2 = ac.assemble(contract, "tarea sin relacion xyz", self.d)
        self.assertEqual(r1["context"], r2["context"],
                        "fallback sin matches debe ser byte-identico 2x")
        # Congela el output del camino viejo: join alfabetico de todos
        parts = []
        for name in ["high_priority", "low_no_match", "medium_match"]:
            with open(os.path.join(self.d, "knowledge", name + ".md"),
                      encoding="utf-8") as fh:
                parts.append(fh.read())
        expected = "### slot: nodes\n" + "\n\n".join(parts)
        self.assertEqual(r1["context"], expected,
                        "fallback holgado byte-identico al comportamiento previo")
        self.assertEqual(r1["slots"][0]["selected"],
                         ["high_priority", "low_no_match", "medium_match"])
        self.assertNotIn("cut", r1["slots"][0])
        self.assertNotIn("omitted_nodes", r1["slots"][0])

    def test_chars_per_token_configurable(self):
        # chars_per_token=2 duplica el costo en tokens
        # Cada nodo: 2000 chars = ~500 tokens con cpt=4, ~1000 tokens con cpt=2
        # Concat de 3 nodos: ~1559 tokens con cpt=4, ~3118 tokens con cpt=2
        # Presupuesto: 2000 tokens -> caben los 3 nodos con cpt=4 (sin compaction),
        # pero se compacta la concat con cpt=2
        contract_cpt4 = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        contract_cpt2 = {
            "budget": {"max_tokens": 2000, "output_reserve": 0,
                      "chars_per_token": 2},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        r4 = ac.assemble(contract_cpt4, "fallback", self.d)
        r2 = ac.assemble(contract_cpt2, "fallback", self.d)
        # Con chars_per_token=4, no hay marker de compaction; con cpt=2 si hay
        has_summarized_cpt4 = "[...summarized]" in r4["context"]
        has_summarized_cpt2 = "[...summarized]" in r2["context"]
        self.assertFalse(has_summarized_cpt4,
                        "con cpt=4 y presupuesto holgado, no debe haber compaction")
        self.assertTrue(has_summarized_cpt2,
                       "con cpt=2, el doble de costo obliga a compactar")

    def test_chars_per_token_invalido_lanza_valueerror(self):
        # chars_per_token=0 o negativo debe lanzar ValueError
        contract = {
            "budget": {"max_tokens": 1000, "output_reserve": 0,
                      "chars_per_token": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "none", "priority": 0},
            ],
        }
        with self.assertRaises(ValueError) as cm:
            ac.assemble(contract, "tarea", self.d)
        msg = str(cm.exception)
        self.assertIn("chars_per_token", msg)

    def test_determinismo_2x_ranking(self):
        # Dos corridas con ranking deben ser byte-identicas
        contract = {
            "budget": {"max_tokens": 2000, "output_reserve": 0},
            "slots": [
                {"id": "nodes", "source": "dynamic", "provider": "okf_nodes",
                 "compaction": "summarize", "priority": 0},
            ],
        }
        r1 = ac.assemble(contract, "high_priority special_tag", self.d)
        r2 = ac.assemble(contract, "high_priority special_tag", self.d)
        a = json.dumps(r1, sort_keys=True)
        b = json.dumps(r2, sort_keys=True)
        self.assertEqual(a, b,
                        "determinismo: dos corridas identicas deben serlo")


if __name__ == "__main__":
    unittest.main()