"""Oraculo congelado de la herramienta de benchmark (Contrato 29).

Fija el comportamiento de ``scripts/benchmark_gates.py`` — mide los 9 gates de
nivel 1 y la suite. La tension central: un benchmark real necesita subprocess
+ reloj de pared, lo opuesto a "determinista, sin subprocess". Se resuelve por
INYECCION DE DEPENDENCIAS: toda la orquestacion (``measure_repeated``,
``measure_suite``, ``benchmark_gates``, ``format_report``, ``count_errors``) es
PURA y recibe ``run_fn``/``timer_fn`` como parametros obligatorios (sin
default) — este oraculo SIEMPRE inyecta fakes deterministas y jamas dispara un
subprocess real ni depende del reloj. Solo ``main`` (sin inyeccion explicita)
construye los reales (``subprocess.run`` + ``time.perf_counter``) — esa rama
NO esta cubierta por este oraculo (es la unica no-determinista, por diseno).

Contratos de las funciones:
  ``run_fn(cmd, cwd) -> int``      devuelve el returncode de ejecutar cmd.
  ``timer_fn() -> float``          devuelve un timestamp; se llama antes y
                                    despues de cada invocacion de run_fn.

  ``measure_repeated(cmd, cwd, run_fn, timer_fn, reps=3, warmup=1) -> dict``
    Corre ``warmup`` invocaciones DESCARTADAS (su tiempo no cuenta, pero su
    exit code SI se recuerda) seguidas de ``reps`` invocaciones MEDIDAS.
    Devuelve {'times': [...] (solo medidas, len==reps),
    'min': float, 'median': float, 'max': float,
    'exit_codes': sorted(set) de TODOS los codes vistos (warmup+medidas)}.

  ``measure_suite(cmd, cwd, run_fn, timer_fn, passes=2) -> dict``
    Corre ``passes`` invocaciones CRUDAS (sin warmup, sin descarte).
    Devuelve {'times': [...] (len==passes, EN ORDEN), 'total': sum(times),
    'exit_codes': [...] (len==passes, EN ORDEN, sin dedup)}.

  ``benchmark_gates(gates, suite_cmd, repo_root, run_fn, timer_fn,
                    reps=3, warmup=1, suite_passes=2) -> dict``
    ``gates``: lista de (name, cmd). Orquesta measure_repeated por cada gate
    (en el orden dado) + measure_suite una vez. Devuelve
    {'gates': {name: <resultado measure_repeated>, ...} (orden preservado),
    'suite': <resultado measure_suite>}. repo_root se pasa como cwd a
    run_fn en TODAS las invocaciones (gates y suite).

  ``count_errors(report) -> int``
    (# gates con algun exit_code != 0) + (# pasadas de suite con exit != 0).

  ``format_report(report) -> str``
    String determinista (ver TestFormatReport para el formato EXACTO).

  ``main(argv, run_fn=None, timer_fn=None, gates=None, suite_cmd=None) -> int``
    CLI. argv acepta ``--repo-root <path>``, ``--reps <n>``, ``--warmup <n>``,
    ``--suite-passes <n>`` (cualquier orden; flags desconocidas se ignoran).
    run_fn/timer_fn/gates/suite_cmd ausentes -> se usan los reales/del modulo
    (``GATES``, ``SUITE_CMD``, subprocess.run, time.perf_counter) — la UNICA
    rama con efecto de lado real. Imprime format_report(...); devuelve 0 si
    count_errors(...) == 0, si no 1.

Este archivo es un ORACULO CONGELADO (tests_sha256): el implementador no lo
modifica. Ver knowledge/contracts/benchmark-gates.md.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import benchmark_gates as bg  # noqa: E402


def _seq_timer(values):
    """timer_fn fake: devuelve los valores de `values` en orden, uno por llamada."""
    it = iter(values)

    def timer():
        return next(it)

    return timer


def _seq_run(codes):
    """run_fn fake: devuelve `codes` en orden; registra (cmd, cwd) recibidos."""
    it = iter(codes)
    calls = []

    def run_fn(cmd, cwd):
        calls.append((cmd, cwd))
        return next(it)

    run_fn.calls = calls
    return run_fn


class TestMeasureRepeated(unittest.TestCase):
    def test_warmup_excluded_y_stats(self):
        # warmup=1 (0->1, elapsed 1.0, descartado); reps=3: 0.5, 0.3, 0.7
        timer = _seq_timer([0, 1, 10, 10.5, 20, 20.3, 30, 30.7])
        run_fn = _seq_run([0, 0, 0, 0])
        result = bg.measure_repeated(["cmd"], "/repo", run_fn, timer,
                                     reps=3, warmup=1)
        self.assertEqual(result["times"], [0.5, 0.3, 0.7])
        self.assertAlmostEqual(result["min"], 0.3)
        self.assertAlmostEqual(result["median"], 0.5)
        self.assertAlmostEqual(result["max"], 0.7)
        self.assertEqual(result["exit_codes"], [0])

    def test_exit_codes_incluye_falla_de_warmup(self):
        timer = _seq_timer([0, 1, 10, 10.5])
        run_fn = _seq_run([1, 0])  # warmup falla, la medida ok
        result = bg.measure_repeated(["cmd"], "/repo", run_fn, timer,
                                     reps=1, warmup=1)
        self.assertEqual(result["times"], [0.5])
        self.assertEqual(result["exit_codes"], [0, 1])

    def test_cmd_y_cwd_pasan_a_run_fn(self):
        timer = _seq_timer([0, 1])
        run_fn = _seq_run([0])
        bg.measure_repeated(["x", "y"], "/some/repo", run_fn, timer,
                            reps=1, warmup=0)
        self.assertEqual(run_fn.calls, [(["x", "y"], "/some/repo")])

    def test_warmup_cero(self):
        timer = _seq_timer([0, 0.2])
        run_fn = _seq_run([0])
        result = bg.measure_repeated(["cmd"], "/repo", run_fn, timer,
                                     reps=1, warmup=0)
        self.assertEqual(result["times"], [0.2])

    def test_defaults_reps3_warmup1(self):
        # 1 warmup + 3 reps = 4 invocaciones -> 8 timestamps
        timer = _seq_timer([0, 1, 10, 10.1, 20, 20.2, 30, 30.3])
        run_fn = _seq_run([0, 0, 0, 0])
        result = bg.measure_repeated(["cmd"], "/repo", run_fn, timer)
        self.assertEqual(len(result["times"]), 3)
        self.assertEqual(len(run_fn.calls), 4)


class TestMeasureSuite(unittest.TestCase):
    def test_dos_pasadas_sin_warmup(self):
        timer = _seq_timer([0, 21.572, 100, 112.952])
        run_fn = _seq_run([0, 0])
        result = bg.measure_suite(["suite"], "/repo", run_fn, timer, passes=2)
        self.assertEqual(result["times"], [21.572, 12.952])
        self.assertAlmostEqual(result["total"], 34.524)
        self.assertEqual(result["exit_codes"], [0, 0])

    def test_exit_codes_en_orden_sin_dedup(self):
        timer = _seq_timer([0, 1, 10, 11])
        run_fn = _seq_run([0, 1])
        result = bg.measure_suite(["suite"], "/repo", run_fn, timer, passes=2)
        self.assertEqual(result["exit_codes"], [0, 1])

    def test_default_passes_2(self):
        timer = _seq_timer([0, 1, 10, 11])
        run_fn = _seq_run([0, 0])
        result = bg.measure_suite(["suite"], "/repo", run_fn, timer)
        self.assertEqual(len(result["times"]), 2)


class TestBenchmarkGates(unittest.TestCase):
    def test_orquesta_gates_y_suite_orden_preservado(self):
        gates = [("g1", ["cmd1"]), ("g2", ["cmd2"])]
        suite_cmd = ["suite"]
        # g1: 1 invocacion (reps=1,warmup=0) -> 2 timestamps
        # g2: idem -> 2 timestamps
        # suite: 1 pasada (suite_passes=1) -> 2 timestamps
        timer = _seq_timer([0, 0.1, 10, 10.2, 20, 20.05])
        run_fn = _seq_run([0, 0, 0])
        report = bg.benchmark_gates(gates, suite_cmd, "/repo", run_fn, timer,
                                    reps=1, warmup=0, suite_passes=1)
        self.assertEqual(list(report["gates"].keys()), ["g1", "g2"])
        self.assertAlmostEqual(report["gates"]["g1"]["times"][0], 0.1)
        self.assertAlmostEqual(report["gates"]["g2"]["times"][0], 0.2)
        self.assertAlmostEqual(report["suite"]["times"][0], 0.05)
        self.assertEqual(
            [c[1] for c in run_fn.calls], ["/repo", "/repo", "/repo"])

    def test_defaults_reps3_warmup1_suitepasses2(self):
        gates = [("g1", ["cmd1"])]
        suite_cmd = ["suite"]
        # g1: 1 warmup + 3 reps = 4 invocaciones; suite: 2 pasadas -> 6 total
        timer = _seq_timer([float(i) for i in range(12)])
        run_fn = _seq_run([0] * 6)
        report = bg.benchmark_gates(gates, suite_cmd, "/repo", run_fn, timer)
        self.assertEqual(len(report["gates"]["g1"]["times"]), 3)
        self.assertEqual(len(report["suite"]["times"]), 2)


class TestCountErrors(unittest.TestCase):
    def _report(self, gate_exit_codes, suite_exit_codes):
        return {
            "gates": {
                "g%d" % i: {"times": [0.1], "min": 0.1, "median": 0.1,
                           "max": 0.1, "exit_codes": codes}
                for i, codes in enumerate(gate_exit_codes)
            },
            "suite": {"times": [0.1] * len(suite_exit_codes),
                     "total": 0.1 * len(suite_exit_codes),
                     "exit_codes": suite_exit_codes},
        }

    def test_todo_sano_cero_errores(self):
        report = self._report([[0], [0]], [0, 0])
        self.assertEqual(bg.count_errors(report), 0)

    def test_un_gate_fallido(self):
        report = self._report([[0], [0, 1]], [0, 0])
        self.assertEqual(bg.count_errors(report), 1)

    def test_gate_y_pasada_de_suite_fallidos(self):
        report = self._report([[1], [0]], [0, 1])
        self.assertEqual(bg.count_errors(report), 2)


class TestFormatReport(unittest.TestCase):
    def test_formato_exacto(self):
        report = {
            "gates": {
                "validate_contracts": {"times": [0.062, 0.063, 0.064],
                                      "min": 0.062, "median": 0.063,
                                      "max": 0.064, "exit_codes": [0]},
                "lint_ascii": {"times": [0.094, 0.100, 0.103],
                              "min": 0.094, "median": 0.100,
                              "max": 0.103, "exit_codes": [0]},
            },
            "suite": {"times": [21.572, 12.952], "total": 34.524,
                     "exit_codes": [0, 0]},
        }
        expected = (
            "Gates (nivel 1):\n"
            "  validate_contracts: min=0.062s med=0.063s max=0.064s exit=[0]\n"
            "  lint_ascii: min=0.094s med=0.100s max=0.103s exit=[0]\n"
            "\n"
            "Suite (2 corridas):\n"
            "  corrida 1: 21.572s (exit=0)\n"
            "  corrida 2: 12.952s (exit=0)\n"
            "  total: 34.524s\n"
            "\n"
            "Resumen: 2 gate(s) medidos, 0 error(es) detectados durante el "
            "benchmark"
        )
        self.assertEqual(bg.format_report(report), expected)

    def test_resumen_cuenta_errores(self):
        report = {
            "gates": {
                "g1": {"times": [0.1], "min": 0.1, "median": 0.1, "max": 0.1,
                      "exit_codes": [0, 1]},
            },
            "suite": {"times": [0.1], "total": 0.1, "exit_codes": [1]},
        }
        out = bg.format_report(report)
        self.assertIn(
            "Resumen: 1 gate(s) medidos, 2 error(es) detectados durante el "
            "benchmark", out)


class TestMain(unittest.TestCase):
    def test_exit_0_todo_sano(self):
        gates = [("g1", ["cmd1"]), ("g2", ["cmd2"])]
        suite_cmd = ["suite"]
        # reps=1,warmup=0 -> 1 gate=1 inv c/u (2 gates=2 inv); suite_passes=1
        # -> 3 invocaciones -> 6 timestamps
        timer = _seq_timer([0, 0.1, 10, 0.2 + 10, 20, 20.05])
        run_fn = _seq_run([0, 0, 0])
        code = bg.main(
            ["--reps", "1", "--warmup", "0", "--suite-passes", "1"],
            run_fn=run_fn, timer_fn=timer, gates=gates, suite_cmd=suite_cmd)
        self.assertEqual(code, 0)

    def test_exit_1_si_algo_fallo(self):
        gates = [("g1", ["cmd1"])]
        suite_cmd = ["suite"]
        timer = _seq_timer([0, 0.1, 10, 10.1])
        run_fn = _seq_run([1, 0])  # gate falla, suite ok
        code = bg.main(
            ["--reps", "1", "--warmup", "0", "--suite-passes", "1"],
            run_fn=run_fn, timer_fn=timer, gates=gates, suite_cmd=suite_cmd)
        self.assertEqual(code, 1)

    def test_flags_desconocidas_se_ignoran(self):
        gates = [("g1", ["cmd1"])]
        suite_cmd = ["suite"]
        timer = _seq_timer([0, 0.1, 10, 10.1])
        run_fn = _seq_run([0, 0])
        code = bg.main(
            ["--reps", "1", "--warmup", "0", "--suite-passes", "1",
             "--algo-raro", "valor"],
            run_fn=run_fn, timer_fn=timer, gates=gates, suite_cmd=suite_cmd)
        self.assertEqual(code, 0)


class TestConstantes(unittest.TestCase):
    def test_gates_son_los_9_reales_en_orden(self):
        # Lista explicita (sin heuristicas, precedente MANIFEST de
        # init_project.py): fija el orden real de knowledge/validacion.md.
        nombres = [name for name, _cmd in bg.GATES]
        self.assertEqual(nombres, [
            "validate_contracts", "validate_specs", "validate_okf",
            "lint_ascii", "validate_rules", "validate_skills",
            "validate_changelog", "validate_ux_page", "validate_diagrams",
        ])

    def test_no_hay_subprocess_ni_perf_counter_fuera_de_main(self):
        # Grep estructural: subprocess.run/time.perf_counter solo dentro de
        # la funcion main (la unica rama con efecto de lado real).
        import inspect
        src = inspect.getsource(bg)
        main_src = inspect.getsource(bg.main)
        rest = src.replace(main_src, "")
        self.assertNotIn("subprocess.run(", rest)
        self.assertNotIn("time.perf_counter(", rest)


if __name__ == "__main__":
    unittest.main()
