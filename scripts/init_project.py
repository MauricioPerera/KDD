#!/usr/bin/env python3
"""Inicializador de plantilla KDD: estrena la plantilla en un proyecto real.

Elimina los artefactos de EJEMPLO del manifiesto explicito (constante
documentada; sin heuristicas por tags), reescribe ``knowledge/index.md``
quitando los enlaces a nodos eliminados (sin enlaces muertos ni secciones
de lista vacias/rotas), y con ``--name`` reemplaza SOLO el titulo H1 del
README. Dry-run por default: calcula el plan sin tocar nada.

Todo-o-nada: valida que todos los artefactos del manifiesto existen ANTES de
borrar el primero; si falta alguno -> ValueError (CLI exit 2) sin tocar nada.

Exit codes: 0 ok · 1 I/O · 2 manifiesto incompleto.
Python stdlib puro; sin red; sin subprocess en el target.

Task contract: ``knowledge/contracts/init-project.md``.
Spec: ``specs/CONTRACT-06-init-project.md``.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Manifiesto explicito de artefactos de EJEMPLO (sin heuristicas).
# Quien clona la plantilla hereda estos 8 mezclados con la infraestructura;
# el init los quita para que la plantilla estrenada nazca limpia y los 3
# gates (validate_contracts, validate_okf, unittest discover) sigan verdes.
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
)

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
_LIST_RE = re.compile(r"^\s*[-+*]\s+")


def _missing(repo):
    """Lista de rutas del manifiesto que no existen como archivo."""
    return [rel for rel in MANIFEST if not (Path(repo) / rel).is_file()]


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
        if _LIST_RE.match(line):
            target = _link_target(line)
            if target:
                resolved = (index.parent / target).resolve()
                rel = _rel_posix(resolved, repo)
                if rel in deleted:
                    continue
                if resolved.is_dir():
                    if not _dir_has_md(resolved):
                        continue
                elif not resolved.exists():
                    continue
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


def init_project(repo_dir, apply, name) -> dict:
    """Plan/aplicacion de la instanciacion. Ver task contract para el dict."""
    repo = Path(repo_dir).resolve()
    missing = _missing(repo)
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
    print("  Artefactos de ejemplo a eliminar ({}):".format(len(result["removed"])))
    for rel in result["removed"]:
        print("    - {}".format(rel))
    print("  Reescribir knowledge/index.md (quitar enlaces a nodos eliminados).")
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
    args = p.parse_args(argv)

    try:
        result = init_project(args.repo_dir, args.apply, args.name)
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