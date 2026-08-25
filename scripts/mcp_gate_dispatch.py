#!/usr/bin/env python3
"""Capa de despacho del MCP server de gates KDD (Contrato: mcp-gate-dispatch).

Logica PURA (stdlib, sin el SDK ``mcp``) que sabe que script ``scripts/*.py``
correr por cada gate y como armar su ``argv``. El wiring MCP real
(``scripts/mcp_server.py``, fuera de este contrato) importa este modulo y
expone cada entrada como una tool -- separado a proposito para que esta logica
sea testeable sin el SDK ``mcp`` instalado.

Reusa ``scripts/*.py`` TAL CUAL via ``subprocess.run``: cero reimplementacion,
cero drift entre el CLI y la tool MCP.

  API:
    ``GATE_SPECS`` -- dict ``{tool_name: {'script','params','defaults'}}``.
      ``script`` es la ruta relativa al repo_root (ej.
      ``scripts/validate_contracts.py``). ``params`` es la lista ordenada de
      nombres de parametro posicionales que el script CLI espera.
      ``defaults`` es un dict ``{param: valor}`` -- valores ``str`` para
      parametros simples, ``list[str]`` para parametros que se expanden a
      MULTIPLES argv (ej. ``dirs`` de ``scan_secrets`` / ``validate_skills``).
    ``build_argv(tool_name, params) -> list[str]`` -- arma
      ``[sys.executable, '<script>', ...args]``. ``params`` (dict) puede omitir
      claves -- se usa el default de ``GATE_SPECS``. Un valor ``list`` se
      expande a multiples argv (uno por elemento, EN ORDEN, sin unirlos con
      espacios -- subprocess.run recibe una lista, no pasa por shell).
      ``KeyError`` si ``tool_name`` no esta en ``GATE_SPECS``.
    ``run_gate(tool_name, params, repo_root='.', timeout=120) ->
      {'exit_code','stdout','stderr'}`` -- corre ``build_argv(...)`` via
      ``subprocess.run(cwd=repo_root, capture_output=True, text=True,
      timeout=timeout)``. Nunca lanza excepcion: un exit code !=0 es
      informacion, no un error; un timeout se traduce a
      ``{'exit_code': None, 'stdout': '', 'stderr': 'timeout after Ns'}``.
    ``run_all_level1(repo_root='.') -> {'overall_ok': bool, 'results':
      {tool_name: {'exit_code','stdout','stderr'}}}`` -- corre, EN ESTE
      ORDEN, los 18 gates de Nivel 1 (todas las claves de ``GATE_SPECS``
      EXCEPTO ``validate_attestation``, que es local-only) con sus params
      default, contra ``repo_root``. ``overall_ok`` es ``True`` solo si TODOS
      los ``exit_code`` son ``0``.
    ``seal_tests(tests_path, repo_root='.') -> {'hash': str|None,
      'exit_code': int, 'stdout': str}`` -- corre
      ``python scripts/validate_contracts.py --hash <tests_path>`` y extrae
      el hash (linea de 64 chars hex) del stdout. ``hash`` es ``None`` si el
      exit code no fue 0 o no se encontro un hash valido.
"""

import os
import re
import subprocess
import sys

# {tool_name: {'script', 'params', 'defaults'}}
# ``script``: ruta relativa al repo_root (la usa como argv[1]; run_gate la
#   resuelve contra cwd=repo_root).
# ``params``: nombres de parametros posicionales, en el orden que el CLI los
#   espera -- determina el orden de los argv.
# ``defaults``: valor por defecto por parametro. ``str`` -> un argv;
#   ``list[str]`` -> se expande a un argv por elemento.
#
# Los defaults mirror exactly lo que usa .github/workflows/validate.yml para
# cada gate (incluido lint_ascii que apunta a 'scripts' y no recibe input).
GATE_SPECS = {
    'validate_contracts': {
        'script': 'scripts/validate_contracts.py',
        'params': ['dir'],
        'defaults': {'dir': 'knowledge/contracts'},
    },
    'validate_specs': {
        'script': 'scripts/validate_specs.py',
        'params': ['dir'],
        'defaults': {'dir': 'specs'},
    },
    'validate_okf': {
        'script': 'scripts/validate_okf.py',
        'params': ['dir'],
        'defaults': {'dir': 'knowledge'},
    },
    'lint_ascii': {
        'script': 'scripts/lint_ascii.py',
        'params': ['dir'],
        'defaults': {'dir': 'scripts'},
    },
    'validate_rules': {
        'script': 'scripts/validate_rules.py',
        'params': ['dir'],
        'defaults': {'dir': 'examples/rules'},
    },
    'validate_skills': {
        'script': 'scripts/validate_skills.py',
        'params': ['dirs'],
        'defaults': {'dirs': ['skills', '.agents/skills']},
    },
    'validate_changelog': {
        'script': 'scripts/validate_changelog.py',
        'params': [],
        'defaults': {},
    },
    'validate_ux_page': {
        'script': 'scripts/validate_ux_page.py',
        'params': ['dir'],
        'defaults': {'dir': 'examples/ux-page'},
    },
    'validate_diagrams': {
        'script': 'scripts/validate_diagrams.py',
        'params': ['dir'],
        'defaults': {'dir': 'examples/diagrams'},
    },
    'validate_security_findings': {
        'script': 'scripts/validate_security_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'security/scan'},
    },
    'validate_compliance_findings': {
        'script': 'scripts/validate_compliance_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'compliance/scan'},
    },
    'validate_privacy_findings': {
        'script': 'scripts/validate_privacy_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'privacy/scan'},
    },
    'validate_accessibility_findings': {
        'script': 'scripts/validate_accessibility_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'accessibility/scan'},
    },
    'validate_dependency_eol_findings': {
        'script': 'scripts/validate_dependency_eol_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'dependency-eol/scan'},
    },
    'validate_observability_findings': {
        'script': 'scripts/validate_observability_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'observability/scan'},
    },
    'validate_test_coverage_findings': {
        'script': 'scripts/validate_test_coverage_findings.py',
        'params': ['dir'],
        'defaults': {'dir': 'test-coverage/scan'},
    },
    'validate_test_commands': {
        'script': 'scripts/validate_test_commands.py',
        'params': ['contracts_dir', 'root'],
        'defaults': {'contracts_dir': 'knowledge/contracts', 'root': '.'},
    },
    'scan_secrets': {
        'script': 'scripts/scan_secrets.py',
        'params': ['dirs'],
        'defaults': {'dirs': ['src']},
    },
    'validate_attestation': {
        'script': 'scripts/validate_attestation.py',
        'params': ['dirs'],
        'defaults': {'dirs': ['.agents/logs', '.']},
    },
}

# Gates de Nivel 1: TODOS excepto validate_attestation (local-only, ver
# knowledge/contracts/attestation-gate.md). El orden es el del pipeline de CI.
LEVEL1_GATES = [name for name in GATE_SPECS if name != 'validate_attestation']

_HEX64 = re.compile(r'^[0-9a-f]{64}$')


def _within(path, repo_root):
    """True si ``path`` (absoluta o relativa a ``repo_root``) resuelve
    (``os.path.realpath``) dentro de ``repo_root``.

    Un path inexistente pero lexicamente dentro de ``repo_root`` cuenta como
    confinado: el confinamiento es de frontera, no de existencia -- el gate
    propio reportara si falta. ``os.path.join`` descarta ``repo_root`` si
    ``path`` es absoluta, asi que una absoluta fuera del repo se detecta, y
    una absoluta dentro se acepta.
    """
    root = os.path.realpath(repo_root)
    resolved = os.path.realpath(os.path.join(root, str(path)))
    return resolved == root or resolved.startswith(root + os.sep)


def _confine_params(params, repo_root):
    """Dict de error (sin lanzar) si algun path en ``params`` escapa de
    ``repo_root``; ``None`` si todos confinados.

    Preserva el invariante del contrato ``run_gate`` nunca lanza``: devuelve
    un dict de error (``exit_code`` 2 + ``stderr`` claro), nunca raise. ``None``
    se salta (param no pasado -> se usa el default, que siempre es relativo a
    ``repo_root``). Valores ``list`` se chequean elemento por elemento.
    """
    for name, value in params.items():
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple)) else [value]
        for v in items:
            if not _within(v, repo_root):
                return {
                    'exit_code': 2,
                    'stdout': '',
                    'stderr': 'rejected: {}={!r} escapes repo_root={!r}'.format(
                        name, value, repo_root),
                }
    return None


def build_argv(tool_name, params):
    """Arma ``[sys.executable, script, ...args]`` para ``tool_name``.

    ``params`` (dict) sobreescribe los defaults de ``GATE_SPECS``. Un valor
    ``list`` se expande a multiples argv (uno por elemento, en orden); cualquier
    otro valor se appenda tal cual. ``KeyError`` si ``tool_name`` no existe.
    """
    spec = GATE_SPECS[tool_name]  # KeyError si no existe -- intencional
    argv = [sys.executable, spec['script']]
    for name in spec['params']:
        value = params.get(name, spec['defaults'].get(name))
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            argv.extend(str(v) for v in value)
        else:
            argv.append(str(value))
    return argv


def run_gate(tool_name, params, repo_root='.', timeout=120):
    """Corre el gate ``tool_name`` via subprocess y devuelve su resultado.

    Nunca lanza: exit code !=0 se devuelve como informacion; un timeout se
    traduce a ``{'exit_code': None, 'stdout': '', 'stderr': 'timeout after Ns'}``.
    """
    argv = build_argv(tool_name, params)
    # Confinamiento de frontera (defensa en profundidad): todo path que llega
    # en `params` debe resolver dentro de `repo_root` antes de tocar
    # subprocess.run. Si escapa, se rechaza con un dict de error (exit_code 2)
    # sin correr nada -- preserva el invariante "nunca lanza". El wiring MCP
    # (mcp_server.py) confina contra el repo_root real ANTES de llegar aqui;
    # este check protege a cualquier otro caller directo de este modulo.
    rejected = _confine_params(params, repo_root)
    if rejected is not None:
        return rejected
    try:
        proc = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            'exit_code': None,
            'stdout': '',
            'stderr': 'timeout after {}s'.format(timeout),
        }
    except OSError as exc:
        # repo_root/cwd inexistente (NotADirectoryError/FileNotFoundError):
        # "Nunca lanza" cubre el OSError del propio subprocess, no solo el
        # exit code del gate. AUDIT-05 H-2.
        return {
            'exit_code': 1,
            'stdout': '',
            'stderr': str(exc),
        }
    return {
        'exit_code': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def run_all_level1(repo_root='.'):
    """Corre los 18 gates de Nivel 1 con sus defaults contra ``repo_root``.

    ``overall_ok`` es ``True`` solo si todos los ``exit_code`` son ``0``.
    ``validate_attestation`` NUNCA esta en ``results`` (es local-only).
    """
    results = {}
    for tool_name in LEVEL1_GATES:
        results[tool_name] = run_gate(tool_name, {}, repo_root=repo_root)
    overall_ok = all(r['exit_code'] == 0 for r in results.values())
    return {'overall_ok': overall_ok, 'results': results}


def seal_tests(tests_path, repo_root='.'):
    """Corre ``validate_contracts.py --hash <tests_path>`` y extrae el hash.

    ``hash`` es el primer renglon de 64 hex del stdout, o ``None`` si el exit
    code no fue 0 o no se encontro un hash valido.
    """
    # Confinamiento de frontera (defensa en profundidad): ``tests_path`` debe
    # resolver dentro de ``repo_root`` antes de pasar a
    # ``validate_contracts.py --hash``. Si escapa, se rechaza sin correr el
    # subprocess (hash None, exit_code 2, stderr claro).
    if not _within(tests_path, repo_root):
        return {
            'hash': None,
            'exit_code': 2,
            'stdout': '',
            'stderr': 'rejected: tests_path={!r} escapes repo_root={!r}'.format(
                tests_path, repo_root),
        }
    argv = [
        sys.executable,
        GATE_SPECS['validate_contracts']['script'],
        '--hash',
        tests_path,
    ]
    try:
        proc = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {'hash': None, 'exit_code': None, 'stdout': ''}

    exit_code = proc.returncode
    found = None
    if exit_code == 0:
        for line in proc.stdout.splitlines():
            if _HEX64.match(line.strip()):
                found = line.strip()
                break
    return {'hash': found, 'exit_code': exit_code, 'stdout': proc.stdout}