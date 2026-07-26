#!/usr/bin/env python3
"""Servidor MCP que expone los gates de KDD como tools (stdio).

Envuelve scripts/mcp_gate_dispatch.py (logica pura, sin el SDK mcp) con el
SDK oficial (FastMCP). Cada tool corre el script scripts/*.py real via
subprocess -- cero reimplementacion, cero drift entre el CLI y la tool MCP.

NO gobernado por un task contract CCDD (a diferencia de mcp_gate_dispatch.py):
depende del paquete externo `mcp`, que rompe la convencion deps_allowed: []
de todos los demas contratos de este repo. Ver
knowledge/contracts/mcp-gate-dispatch.md para el modulo que SI tiene
contrato+oraculo sellado; este archivo es wiring delgado sobre ese modulo.

Uso:
    pip install mcp
    python scripts/mcp_server.py

El repo_root que cada tool usa como cwd es la raiz de ESTE repo (donde vive
este script), no el cwd del proceso que lo invoca -- un cliente MCP puede
spawnear este server desde cualquier directorio.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mcp_gate_dispatch as gd  # noqa: E402
import rule_hints  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mcp = FastMCP("kdd-gates")


def _params(**kwargs):
    """Descarta claves con valor None (el caller no las paso -> usar default)."""
    return {k: v for k, v in kwargs.items() if v is not None}


@mcp.tool()
def validate_contracts(dir: str | None = None) -> dict:
    """Valida frontmatter, secciones obligatorias y sello tests_sha256 de cada
    knowledge/contracts/*.md. Default dir: knowledge/contracts."""
    return gd.run_gate('validate_contracts', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_specs(dir: str | None = None) -> dict:
    """Valida los contratos de ejecucion de nivel proyecto (specs/CONTRACT-NN-*.md):
    criterios de aceptacion verificables, perimetro, condiciones de aborto.
    Default dir: specs."""
    return gd.run_gate('validate_specs', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_okf(dir: str | None = None) -> dict:
    """Valida estructura/frontmatter de los nodos OKF y que no haya enlaces rotos
    ni nodos huerfanos. Default dir: knowledge."""
    return gd.run_gate('validate_okf', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def lint_ascii(dir: str | None = None) -> dict:
    """Exige ASCII en los literales string de scripts/*.py (docstrings excluidas).
    Default dir: scripts."""
    return gd.run_gate('lint_ascii', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_rules(dir: str | None = None) -> dict:
    """Gate de rule contracts (reglas de negocio como datos): familias conocidas,
    golden sellado por hash. Capa opcional, INFO si no hay rule contracts.
    Default dir: examples/rules."""
    return gd.run_gate('validate_rules', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_skills(dirs: list[str] | None = None) -> dict:
    """Gate de skills de agente: SKILL.md presente, frontmatter parseable, enlaces
    resuelven. Capa opcional. Default dirs: ['skills', '.agents/skills']."""
    return gd.run_gate('validate_skills', _params(dirs=dirs), repo_root=REPO_ROOT)


@mcp.tool()
def validate_changelog() -> dict:
    """Coherencia bidireccional CHANGELOG.md <-> docs/reports/CONTRACT-NN-REPORT.md.
    Capa opcional, INFO si no hay CHANGELOG o reportes."""
    return gd.run_gate('validate_changelog', {}, repo_root=REPO_ROOT)


@mcp.tool()
def validate_ux_page(dir: str | None = None) -> dict:
    """Gate de UX/accesibilidad sobre paginas HTML autocontenidas: balance de tags,
    i18n, contraste WCAG. Capa opcional. Default dir: examples/ux-page."""
    return gd.run_gate('validate_ux_page', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_diagrams(dir: str | None = None) -> dict:
    """Gate de diagramas Mermaid (flowchart/gantt/pie/journey) contra un contrato
    JSON declarativo. Capa opcional. Default dir: examples/diagrams."""
    return gd.run_gate('validate_diagrams', _params(dir=dir), repo_root=REPO_ROOT)


@mcp.tool()
def validate_test_commands(contracts_dir: str | None = None, root: str | None = None) -> dict:
    """Corre el test_command real de cada contrato y falla si algun exit code no
    es 0. Unico gate del repo cuyo forbids permite subprocess. Defaults:
    contracts_dir=knowledge/contracts, root=. (el repo_root que
    validate_test_commands.py usa como cwd de cada test_command, NO el
    repo_root de este server -- son dos cosas distintas)."""
    return gd.run_gate(
        'validate_test_commands',
        _params(contracts_dir=contracts_dir, root=root),
        repo_root=REPO_ROOT,
    )


@mcp.tool()
def scan_secrets(dirs: list[str] | None = None) -> dict:
    """Escaneo determinista de credenciales filtradas por prefijo de proveedor
    conocido (AWS/GitHub/Slack/Google/Stripe + private keys). Default dirs: ['src']."""
    return gd.run_gate('scan_secrets', _params(dirs=dirs), repo_root=REPO_ROOT)


@mcp.tool()
def validate_attestation(logs_dir: str | None = None, repo_root: str | None = None) -> dict:
    """Verifica el envelope de atestacion (identidad + hashes) de cada
    .agents/logs/<task>-REPORT.md. NO es parte de Nivel 1 CI (evidencia local).
    Defaults: logs_dir=.agents/logs, repo_root=."""
    dirs = None
    if logs_dir is not None or repo_root is not None:
        dirs = [
            logs_dir if logs_dir is not None else '.agents/logs',
            repo_root if repo_root is not None else '.',
        ]
    return gd.run_gate('validate_attestation', _params(dirs=dirs), repo_root=REPO_ROOT)


@mcp.tool()
def run_all_level1() -> dict:
    """Corre los 11 gates de Nivel 1 (todos excepto validate_attestation, que es
    local-only) contra este repo, con sus defaults. Una sola llamada = veredicto
    completo de Nivel 1. Devuelve {'overall_ok': bool, 'results': {...}}."""
    return gd.run_all_level1(repo_root=REPO_ROOT)


@mcp.tool()
def seal_tests(tests_path: str) -> dict:
    """Calcula el sha256 LF-normalizado de un archivo de tests (el mismo que
    validate_contracts.py --hash produce) para pegarlo en tests_sha256 de un
    contrato. Devuelve {'hash': str|None, 'exit_code': int, 'stdout': str}."""
    return gd.seal_tests(tests_path, repo_root=REPO_ROOT)


@mcp.tool()
def rule_hint(rule_id: str) -> dict:
    """Receta de arreglo de un rule-id de los gates: el QUE HACER que el
    mensaje del gate no da. Ej: 'FM_TESTS_FROZEN' -> como sellar el oraculo.
    Devuelve {'rule_id': str, 'hint': str, 'known': bool}. Un rule_id
    desconocido NO es un error: devuelve el fallback generico con known=False,
    para que un agente que pregunta de mas reciba orientacion, no una
    excepcion."""
    # No pasa por mcp_gate_dispatch: no es un gate y no corre subprocess.
    # rule_hints es stdlib pura, asi que la tool es una llamada directa.
    return {
        'rule_id': rule_id,
        'hint': rule_hints.hint_for(rule_id),
        'known': rule_id in rule_hints.HINTS,
    }


if __name__ == '__main__':
    mcp.run()
