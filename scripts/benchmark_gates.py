#!/usr/bin/env python3
"""Benchmark de los 11 gates de nivel 1 + la suite (Contrato 29).

Mide tiempos de ejecución de gates y tests con orquestación pura (inyectable).
Oraculo congelado: tests/test_benchmark_gates.py
Task contract: knowledge/contracts/benchmark-gates.md
"""

import sys
import subprocess
import time
import statistics

# Lista explicita (sin heuristicas, precedente MANIFEST de init_project.py):
# los 11 gates reales de Nivel 1, en el mismo orden que knowledge/validacion.md y
# que mcp_gate_dispatch.LEVEL1_GATES (todos los gates de CI salvo validate_attestation,
# que es local-only). Antes faltaban validate_test_commands y scan_secrets (AUDIT-01 H-5).
GATES = (
    ("validate_contracts", [sys.executable, "scripts/validate_contracts.py", "knowledge/contracts"]),
    ("validate_specs", [sys.executable, "scripts/validate_specs.py", "specs"]),
    ("validate_okf", [sys.executable, "scripts/validate_okf.py", "knowledge"]),
    ("lint_ascii", [sys.executable, "scripts/lint_ascii.py", "scripts"]),
    ("validate_rules", [sys.executable, "scripts/validate_rules.py", "examples/rules"]),
    ("validate_skills", [sys.executable, "scripts/validate_skills.py", "skills", ".agents/skills"]),
    ("validate_changelog", [sys.executable, "scripts/validate_changelog.py"]),
    ("validate_ux_page", [sys.executable, "scripts/validate_ux_page.py", "examples/ux-page"]),
    ("validate_diagrams", [sys.executable, "scripts/validate_diagrams.py", "examples/diagrams"]),
    ("validate_test_commands", [sys.executable, "scripts/validate_test_commands.py", "knowledge/contracts", "."]),
    ("scan_secrets", [sys.executable, "scripts/scan_secrets.py", "src"]),
)
SUITE_CMD = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]


def measure_repeated(cmd, cwd, run_fn, timer_fn, reps=3, warmup=1):
    """Mide cmd con warmup y reps, retornando tiempos, stats y exit codes."""
    times = []
    all_exit_codes = []

    # Warmup: se corre pero el tiempo se descarta
    for _ in range(warmup):
        timer_fn()
        exit_code = run_fn(cmd, cwd)
        timer_fn()
        all_exit_codes.append(exit_code)

    # Reps: se mide el tiempo
    for _ in range(reps):
        t_start = timer_fn()
        exit_code = run_fn(cmd, cwd)
        t_end = timer_fn()
        elapsed = round(t_end - t_start, 3)
        times.append(elapsed)
        all_exit_codes.append(exit_code)

    return {
        "times": times,
        "min": min(times),
        "median": statistics.median(times),
        "max": max(times),
        "exit_codes": sorted(set(all_exit_codes)),
    }


def measure_suite(cmd, cwd, run_fn, timer_fn, passes=2):
    """Mide cmd con passes invocaciones crudas (sin warmup, sin descarte)."""
    times = []
    exit_codes = []

    for _ in range(passes):
        t_start = timer_fn()
        exit_code = run_fn(cmd, cwd)
        t_end = timer_fn()
        elapsed = round(t_end - t_start, 3)
        times.append(elapsed)
        exit_codes.append(exit_code)

    return {
        "times": times,
        "total": round(sum(times), 3),
        "exit_codes": exit_codes,
    }


def benchmark_gates(gates, suite_cmd, repo_root, run_fn, timer_fn,
                    reps=3, warmup=1, suite_passes=2):
    """Orquesta medición de gates y suite, preservando orden."""
    result = {"gates": {}, "suite": None}

    # Medir cada gate en el orden dado
    for name, cmd in gates:
        result["gates"][name] = measure_repeated(
            cmd, repo_root, run_fn, timer_fn, reps=reps, warmup=warmup
        )

    # Medir suite
    result["suite"] = measure_suite(
        suite_cmd, repo_root, run_fn, timer_fn, passes=suite_passes
    )

    return result


def count_errors(report):
    """Cuenta gates y pasadas de suite que fallaron (exit != 0)."""
    error_count = 0

    # Contar gates con algún exit_code != 0
    for gate_result in report["gates"].values():
        if any(code != 0 for code in gate_result["exit_codes"]):
            error_count += 1

    # Contar pasadas de suite con exit_code != 0
    for exit_code in report["suite"]["exit_codes"]:
        if exit_code != 0:
            error_count += 1

    return error_count


def format_report(report):
    """Formatea el reporte de benchmark como string determinista."""
    lines = []

    # Sección Gates
    lines.append("Gates (nivel 1):")
    for name, result in report["gates"].items():
        exit_str = str(result["exit_codes"])
        line = (f"  {name}: min={result['min']:.3f}s med={result['median']:.3f}s "
                f"max={result['max']:.3f}s exit={exit_str}")
        lines.append(line)

    lines.append("")

    # Sección Suite
    num_corridas = len(report["suite"]["times"])
    lines.append(f"Suite ({num_corridas} corridas):")
    for i, (time_val, exit_code) in enumerate(
        zip(report["suite"]["times"], report["suite"]["exit_codes"]), 1
    ):
        lines.append(f"  corrida {i}: {time_val:.3f}s (exit={exit_code})")
    lines.append(f"  total: {report['suite']['total']:.3f}s")

    lines.append("")

    # Resumen
    num_gates = len(report["gates"])
    num_errors = count_errors(report)
    lines.append(
        f"Resumen: {num_gates} gate(s) medidos, {num_errors} error(es) "
        f"detectados durante el benchmark"
    )

    return "\n".join(lines)


def main(argv, run_fn=None, timer_fn=None, gates=None, suite_cmd=None):
    """CLI: parsea args, corre benchmark, imprime reporte, devuelve exit code."""
    # Defaults de parámetros
    repo_root = "."
    reps = 3
    warmup = 1
    suite_passes = 2

    # Parsear argv (ignorar flags desconocidas)
    i = 0
    while i < len(argv):
        if argv[i] == "--repo-root" and i + 1 < len(argv):
            repo_root = argv[i + 1]
            i += 2
        elif argv[i] == "--reps" and i + 1 < len(argv):
            reps = int(argv[i + 1])
            i += 2
        elif argv[i] == "--warmup" and i + 1 < len(argv):
            warmup = int(argv[i + 1])
            i += 2
        elif argv[i] == "--suite-passes" and i + 1 < len(argv):
            suite_passes = int(argv[i + 1])
            i += 2
        else:
            i += 1

    # Usar defaults si no inyectados
    if gates is None:
        gates = GATES
    if suite_cmd is None:
        suite_cmd = SUITE_CMD

    # Construir funciones reales si no inyectadas
    if run_fn is None:
        def run_fn(cmd, cwd):
            return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).returncode

    if timer_fn is None:
        def timer_fn():
            return time.perf_counter()

    # Ejecutar benchmark
    report = benchmark_gates(
        gates, suite_cmd, repo_root, run_fn, timer_fn,
        reps=reps, warmup=warmup, suite_passes=suite_passes
    )

    # Imprimir reporte
    print(format_report(report))

    # Devolver exit code
    return 0 if count_errors(report) == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
