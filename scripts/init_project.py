#!/usr/bin/env python3
"""Inicializador de plantilla KDD: estrena la plantilla en un proyecto real.

Elimina ejemplos e historia propia de KDD del manifiesto explicito, reescribe
``knowledge/index.md`` sin enlaces muertos, reinicia CHANGELOG y la politica
de completion para el repositorio nuevo. ``--name`` cambia solo el H1 del
README. Dry-run por default: calcula el plan sin tocar nada.

Todo-o-nada: valida que los artefactos del manifiesto y los archivos que se
reescriben existen ANTES de borrar el primero;
si falta alguno -> ValueError (CLI exit 2) sin tocar nada.

Exit codes: 0 ok · 1 I/O · 2 manifiesto incompleto.
Python stdlib puro; sin red; sin subprocess en el target.

Task contract: ``knowledge/contracts/init-project.md``.
Spec: ``specs/CONTRACT-06-init-project.md``.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Manifiesto explicito de artefactos de EJEMPLO (sin heuristicas).
# Quien clona la plantilla hereda estos artefactos mezclados con la
# infraestructura; el init los quita para que la plantilla estrenada nazca
# limpia y los gates de nivel 1 + la suite sigan verdes.
# Nada fuera del manifiesto se elimina.
# ---------------------------------------------------------------------------
MANIFEST = (
    "src/hello.py",
    "src/users.py",
    "tests/test_sample.py",
    "tests/test_users.py",
    "knowledge/data_models/users_table.md",
    "knowledge/architecture/overview.md",
    "knowledge/contracts/sample_task.md",
    "knowledge/contracts/validate-user-record.md",
    "src/payment_limit.py",
    "tests/test_payment_limit.py",
    "knowledge/data_models/payment_limits.md",
    "knowledge/contracts/validate-payment-limit.md",
    "examples/rules/payment-compliance.rules.json",
    "examples/rules/payment-golden.json",
    "tests/test_payment_rules_equivalence.py",
    "examples/rules/border-control.rules.json",
    "examples/rules/border-golden.json",
    "knowledge/data_models/border_rules.md",
    "examples/rules/workflow-policy.rules.json",
    "examples/rules/workflow-golden.json",
    "knowledge/data_models/workflow_policy.md",
    "src/route_message.py",
    "tests/test_route_message.py",
    "knowledge/contracts/route-message.md",
    "knowledge/data_models/message_routing.md",
    "examples/rules/routing-audit.rules.json",
    "examples/rules/routing-golden.json",
    "src/check_workflow_graph.py",
    "tests/test_check_graph.py",
    "knowledge/contracts/check-graph.md",
    "src/validate_article.py",
    "tests/test_validate_article.py",
    "knowledge/contracts/validate-article.md",
    "knowledge/data_models/editorial_style.md",
    "examples/rules/mcp-registry.rules.json",
    "examples/rules/mcp-golden.json",
    "knowledge/data_models/mcp_registry.md",
    "src/check_agent_wiring.py",
    "tests/test_check_wiring.py",
    "knowledge/contracts/check-agent-wiring.md",
    "knowledge/data_models/agent_wiring.md",
    "examples/rules/agent-wiring.rules.json",
    "examples/rules/agent-wiring-golden.json",
    "examples/ux-page/demo.html",
    "knowledge/data_models/ux_page_contract.md",
    "examples/git/commit-convention.json",
    "knowledge/data_models/commit_message_contract.md",
    "examples/multi-lang/node/greet.js",
    "examples/multi-lang/node/greet.test.js",
    "knowledge/contracts/example-node-greet.md",
)

# Historia del desarrollo de KDD, no del proyecto que se instancia. Rutas
# congeladas: nunca descubrir specs/reportes con glob al aplicar el borrado.
HISTORY_SPECS = (
    "specs/CONTRACT-01-completar-plantilla.md",
    "specs/CONTRACT-02-agents-context.md",
    "specs/CONTRACT-03-validador-okf.md",
    "specs/CONTRACT-04-dogfood-e2e.md",
    "specs/CONTRACT-05-gate-nivel-2.md",
    "specs/CONTRACT-06-init-project.md",
    "specs/CONTRACT-07-audit-fixes.md",
    "specs/CONTRACT-08-export-cross-drive.md",
    "specs/CONTRACT-09-validador-specs.md",
    "specs/CONTRACT-10-endurecer-validadores.md",
    "specs/CONTRACT-11-ci-windows-suite2x.md",
    "specs/CONTRACT-12-tests-sha256-obligatoria.md",
    "specs/CONTRACT-13-lint-ascii-scripts.md",
    "specs/CONTRACT-14-versionado-plantilla.md",
    "specs/CONTRACT-15-ensamblador-ranking.md",
    "specs/CONTRACT-16-ejemplo-pagos.md",
    "specs/CONTRACT-17-rule-contract.md",
    "specs/CONTRACT-18-rules-gate.md",
    "specs/CONTRACT-19-border-control.md",
    "specs/CONTRACT-20-workflow-policy.md",
    "specs/CONTRACT-21-message-router.md",
    "specs/CONTRACT-22-graph-cycles.md",
    "specs/CONTRACT-23-editorial.md",
    "specs/CONTRACT-24-skills-gate.md",
    "specs/CONTRACT-25-mcp-registry.md",
    "specs/CONTRACT-26-agent-wiring.md",
    "specs/CONTRACT-27-changelog-gate.md",
    "specs/CONTRACT-28-perimeter-gate.md",
    "specs/CONTRACT-29-benchmark-gates.md",
    "specs/CONTRACT-30-ux-page-gate.md",
    "specs/CONTRACT-31-commit-message-gate.md",
    "specs/CONTRACT-32-preflight.md",
    "specs/CONTRACT-33-seal-audit.md",
)
HISTORY_REPORTS = tuple(
    "docs/reports/CONTRACT-{:02d}-REPORT.md".format(number)
    for number in range(1, 34)
)
KDD_ONLY_REPORTS = (
    "docs/reports/AUDIT-HARDENING-REPORT.md",
    "docs/reports/LEGACY-COMPLETION-AUDIT.md",
    "docs/reports/PROFILE-PILOT-REPORT.md",
    "docs/reports/QUALITY-APPROVAL-REPORT.md",
    "docs/reports/VERIFICATION-BROWSER-REPORT.md",
)
SPRINT_EXAMPLES = (
    "specs/sprints/PILOT.md",
    "specs/sprints/SPRINT-00-ensayo.md",
    "specs/sprints/SPRINT-01-admission.md",
    "specs/sprints/SPRINT-02-backlog.md",
    "specs/sprints/SPRINT-03-authority.md",
    "specs/sprints/SPRINT-04-native-level2.md",
)
MANIFEST += HISTORY_SPECS + HISTORY_REPORTS + KDD_ONLY_REPORTS + SPRINT_EXAMPLES

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
_LIST_RE = re.compile(r"^\s*[-+*]\s+")


def _missing(repo):
    """Lista de rutas del manifiesto que no existen como archivo."""
    return [rel for rel in MANIFEST if not (Path(repo) / rel).is_file()]


# Artefactos que NO estan en MANIFEST pero apply lee/necesita despues del
# bucle de borrado: _rewrite_index lee knowledge/index.md y _rename_readme
# lee README.md. El pre-check de atomicidad debe cubrirlos para que la
# limpieza sea de verdad todo-o-nada (borrarlos-los-50 y luego crashear con
# FileNotFoundError viola la garantia del docstring).
REQUIRED_AFTER_DELETE = (
    "knowledge/index.md",
    "README.md",
    "CHANGELOG.md",
    "completion-legacy.json",
)

_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _rel_posix(path, base):
    return os.path.relpath(str(path), str(base)).replace(os.sep, "/")


def _dir_has_md(d):
    return any(Path(d).rglob("*.md"))


def _link_target(line):
    m = _LINK_RE.search(line)
    if not m:
        return None
    return m.group(1).split("#")[0].strip()


def _drop_empty_sections(lines):
    """Quita encabezados ``## X`` cuya seccion no tenga ningun item de lista."""
    result = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].startswith("## "):
            j = i + 1
            has_item = False
            while j < n and not lines[j].startswith("## "):
                if _LIST_RE.match(lines[j]):
                    has_item = True
                    break
                j += 1
            if not has_item:
                i += 1
                continue
        result.append(lines[i])
        i += 1
    return result


def _keep_index_line(line, index, repo, deleted):
    if not _LIST_RE.match(line):
        return True
    target = _link_target(line)
    if not target:
        return True
    resolved = (index.parent / target).resolve()
    if _rel_posix(resolved, repo) in deleted:
        return False
    if resolved.is_dir():
        return _dir_has_md(resolved)
    return resolved.exists()


def _rewrite_index(repo):
    """Reescribe knowledge/index.md sin enlaces a nodos eliminados.

    Para cada item de lista con un enlace: lo quita si apunta a un archivo
    del manifiesto (eliminado), a un directorio que quedo sin nodos .md
    (seccion vacia), o a una ruta inexistente (enlace roto). El resto de las
    lineas se preserva. Devuelve True si escribio el index.
    """
    index = Path(repo) / "knowledge" / "index.md"
    text = index.read_text(encoding="utf-8")
    deleted = set(MANIFEST)
    kept = []
    for line in text.split("\n"):
        if _keep_index_line(line, index, repo, deleted):
            kept.append(line)
    final = _drop_empty_sections(kept)
    index.write_text("\n".join(final), encoding="utf-8")
    return True


def _rename_readme(repo, name):
    """Reemplaza SOLO la primera linea ``# ...`` (H1) del README. Devuelve True."""
    readme = Path(repo) / "README.md"
    lines = readme.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines[i] = "# {}".format(name)
            readme.write_text("\n".join(lines), encoding="utf-8")
            return True
    return False


def _reset_changelog(repo):
    changelog = Path(repo) / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## v0.1.0\n\n- Proyecto inicializado desde KDD.\n",
        encoding="utf-8")


def _reset_completion(repo, repository):
    policy = Path(repo) / "completion-legacy.json"
    policy.write_text(json.dumps({
        "schema_version": 1,
        "repository": repository,
        "legacy_pairs": {},
    }, indent=2) + "\n", encoding="utf-8")


def init_project(repo_dir, apply, name, repository=None) -> dict:
    """Plan/aplicacion de la instanciacion. Ver task contract para el dict."""
    repo = Path(repo_dir).resolve()
    if repository is not None and not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError("--repository debe tener formato OWNER/REPO")
    if apply and not repository:
        raise ValueError("--apply requiere --repository OWNER/REPO")
    missing = _missing(repo)
    # Pre-check de atomicidad: incluye lo que apply lee tras el borrado.
    missing += [rel for rel in REQUIRED_AFTER_DELETE
                if not (repo / rel).is_file()]
    if missing:
        raise ValueError(
            "manifiesto incompleto, faltan: {}".format(", ".join(missing)))

    removed = list(MANIFEST)
    index_rewritten = False
    readme_renamed = False

    if apply:
        for rel in MANIFEST:
            (repo / rel).unlink()
        _rewrite_index(repo)
        index_rewritten = True
        _reset_changelog(repo)
        _reset_completion(repo, repository)
        if name:
            readme_renamed = _rename_readme(repo, name)

    return {
        "removed": removed,
        "index_rewritten": index_rewritten,
        "readme_renamed": readme_renamed,
        "applied": bool(apply),
    }


def _print_plan(result, name):
    print("Plan de inicializacion del proyecto:")
    print("  Artefactos de ejemplo e historia KDD a eliminar ({}):".format(len(result["removed"])))
    for rel in result["removed"]:
        print("    - {}".format(rel))
    print("  Reescribir knowledge/index.md (quitar enlaces a nodos eliminados).")
    print("  Reiniciar CHANGELOG.md y completion-legacy.json para el repositorio nuevo.")
    if name:
        print("  Reemplazar el titulo H1 del README por: {}".format(name))
    if result["applied"]:
        print("\nAplicado: plantilla inicializada.")
    else:
        print("\n(dry-run: no se modifico nada. Use --apply para ejecutar.)")


def main(argv):
    p = argparse.ArgumentParser(
        prog="init_project",
        description="Instancia la plantilla KDD eliminando los ejemplos del manifiesto.")
    p.add_argument("--apply", action="store_true",
                   help="Aplica el plan (default: dry-run, no toca nada).")
    p.add_argument("--name", default=None,
                   help="Nuevo titulo H1 del README (opcional).")
    p.add_argument("--repo-dir", default=".",
                   help="Directorio raiz del repo a inicializar (default: .).")
    p.add_argument("--repository", default=None,
                   help="OWNER/REPO de GitHub para la politica de completion.")
    args = p.parse_args(argv)

    try:
        result = init_project(args.repo_dir, args.apply, args.name, args.repository)
    except ValueError as e:
        print("ERROR: {}".format(e))
        return 2
    except OSError as e:
        print("ERROR de I/O: {}".format(e))
        return 1

    _print_plan(result, args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
