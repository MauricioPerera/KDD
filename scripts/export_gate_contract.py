#!/usr/bin/env python3
"""Exportador de contratos KDD a su variante gate-nativa (CCDD nivel 2).

El gate CCDD real (servidor MCP ``ccdd-complexity``) exige ASCII estable y
rutas ``target``/``tests`` relativas al ``.md`` del contrato que lee. Los
contratos KDD viven en espanol con acentos y con rutas relativas a la raiz
del repo. Este exportador es el puente determinista: lee un contrato KDD
(UFT-8) y emite ``<out_dir>/<task>.gate.md`` gate-nativo, sin tocar el
contrato fuente (artefacto derivado).

Default de salida: la RAIZ del repo (``--out-dir .``), archivo
``<task>.gate.md``. El gate real RECHAZA rutas ``target``/``tests`` que
escapan del directorio del contrato (cualquier ``..``): el lint falla con
``tc-tests-frozen`` cuando ``tests`` no existe relativo al ``.md``. Como
``run_integration_gate`` resuelve ``target``/``tests`` relativos al ``.md``
del export, el unico lugar donde ambas cosas (lint sin ``..`` + resolucion
correcta) coinciden a la vez es la raiz del repo: ahi las rutas quedan
iguales a las originales del contrato (``src/users.py``,
``tests/test_users.py``) sin ``..``. Por eso la raiz es el default correcto.
Si se pasa ``--out-dir`` en otro directorio, la reescritura se calcula igual
(relativa al archivo de export), pero el gate real puede rechazarlo si
introduce ``..``.

Transformaciones (segun ``knowledge/contracts/export-gate-contract.md``):

  (1) Normalizacion ASCII de TODO el texto:
        - NFKD + eliminacion de marcas combinantes (acentos -> base ASCII).
        - Tabla explicita de mapeos para tipograficos: em/en-dash -> '-',
          flecha -> '->', '<=' / '>=' comillas tipograficas -> rectas,
          bullets y '·' -> '-'. Resto no-ASCII: se elimina.
  (2) ``target`` y ``tests`` del frontmatter se reescriben relativos al
        archivo de export ``<out_dir>/<task>.gate.md`` (separador '/'); como
        el export vive directo bajo ``out_dir``, equivale a relativo a
        ``out_dir``. ``test_command`` se reescribe a
        ``python <ruta-relativa-desde-el-dir-del-target-hasta-el-archivo-
        de-tests>`` (POSIX): el gate ejecuta ``test_command`` con ``cwd``
        = directorio del ``target``, y el archivo de tests debe ser
        auto-ejecutable (``unittest.main()``) — se invoca como
        ``python <rel>`` (no ``python -m unittest``). El resto del
        frontmatter va verbatim.
  (3) El cuerpo va verbatim (solo normalizado a ASCII).

Determinista: mismo input -> bytes identicos. ``ValueError`` si falta
frontmatter o las claves ``task``/``target``/``tests``.

Las rutas ``target``/``tests`` del contrato se interpretan relativas al
``repo_root`` (convencion KDD: la raiz del repo). ``repo_root`` es explicito
via ``--repo-root`` (default ``'.'`` = cwd de invocacion), resuelto a ruta
absoluta; cuando se pasa explicito, el resultado es INDEPENDIENTE del cwd
desde el que se invoque (la convencion queda fijada, no implicita en getcwd).

Uso:
    python scripts/export_gate_contract.py <contrato.md> [--out-dir DIR]
            [--repo-root DIR]
Exit: 0 ok · 1 I/O · 2 contrato invalido.
"""

import argparse
import os
import sys
import unicodedata


# ---------------------------------------------------------------------------
# Tabla explicita de mapeos tipograficos -> ASCII
# ---------------------------------------------------------------------------
# Aplicada ANTES de la normalizacion NFKD. Cualquier caracter no-ASCII que no
# este aqui cae en: NFKD + strip de marcas combinantes, y si aun queda no-ASCII
# se elimina. La tabla cubre los tipograficos comunes del espanol.

_EXPLICIT_MAP = {
    # rayas / guiones
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
    # flechas
    "→": "->",  # rightwards arrow
    # comparadores
    "≤": "<=",  # <=
    "≥": ">=",  # >=
    # comillas tipograficas -> rectas
    "‘": "'",  # left single
    "’": "'",  # right single
    "‚": "'",  # single low-9
    "‛": "'",  # single reversed
    "“": '"',  # left double
    "”": '"',  # right double
    "„": '"',  # double low-9
    "‟": '"',  # double reversed
    "«": '"',  # guillemet izquierdo (comilla latina)
    "»": '"',  # guillemet derecho
    # bullets / punto medio
    "•": "-",  # bullet
    "‣": "-",  # triangular bullet
    "⁃": "-",  # hyphen bullet
    "◦": "-",  # white bullet
    "·": "-",  # middle dot
}


def _ascii_normalize(text: str) -> str:
    """Normaliza ``text`` a ASCII 100% (< 128) segun la tabla + NFKD.

    Pasos: (a) mapeos explicitos; (b) NFKD + eliminacion de marcas
    combinantes (acentos); (c) eliminacion de cualquier byte restante >= 128.
    """
    mapped = ''.join(_EXPLICIT_MAP.get(ch, ch) for ch in text)
    decomposed = unicodedata.normalize("NFKD", mapped)
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c if ord(c) < 128 else "" for c in no_marks)


# ---------------------------------------------------------------------------
# Frontmatter: split y extraccion de escalares (preservando el texto crudo)
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str):
    """Devuelve (fm_lines, body) o (None, None) si no hay frontmatter valido.

    El frontmatter empieza en la primera linea ``---`` y cierra en la
    siguiente linea ``---``. Se trabaja sobre lineas (separador '\n') para
    preservar el texto crudo y el orden de claves.
    """
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            start = i
            break
    if start is None:
        return None, None
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        return None, None
    fm_lines = lines[start + 1:end]
    body = "\n".join(lines[end + 1:])
    return fm_lines, body


def _scalar_value(fm_lines, key: str):
    """Devuelve (value, quote) para la primera linea ``key:`` encontrada.

    ``quote`` es "'" | '"' | None segun delimitacion del valor. Si la clave
    no esta, devuelve (None, None).
    """
    prefix = key + ":"
    for ln in fm_lines:
        s = ln.strip()
        if s.startswith(prefix):
            value = s[len(prefix):].strip()
            if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                return value[1:-1], value[0]
            return value, None
    return None, None


def _key_line_index(fm_lines, key: str) -> int:
    """Indice de la linea del frontmatter que define ``key``, o -1."""
    prefix = key + ":"
    for i, ln in enumerate(fm_lines):
        if ln.strip().startswith(prefix):
            return i
    return -1


def _replace_scalar_line(line: str, new_value: str) -> str:
    """Reconstruye una linea ``key: value`` preservando indent y quote.

    Sustituye el valor por ``new_value`` mantenido el ``key:`` original y el
    estilo de comillas (si lo habia).
    """
    colon = line.index(":")
    head = line[:colon + 1]            # "key:"
    rest = line[colon + 1:]            # " value" | " 'value'"
    stripped = rest.strip()
    quote = ""
    if stripped and stripped[0] in ("'", '"'):
        quote = stripped[0]
    return head + " " + quote + new_value + quote


# ---------------------------------------------------------------------------
# Reescritura de rutas target/tests relativas al export
# ---------------------------------------------------------------------------

def _rewrite_path(orig_value: str, out_dir_abs: str, repo_root: str) -> str:
    """Reescribe ``orig_value`` (relativo a ``repo_root``) relativo al
    archivo de export, que vive directamente bajo ``out_dir_abs``. Devuelve
    una ruta POSIX (separador '/').

    Los contratos KDD declaran ``target``/``tests`` relativos a la raiz del
    repo; el gate los resuelve relativos al ``.md`` del export. ``repo_root``
    es la raiz del repo (convencion KDD), pasada explicita (``--repo-root``)
    o ``'.'`` por defecto, y resuelta a absoluta por el llamador. Cuando
    ``out_dir_abs`` == ``repo_root`` (el default real), la salida coincide
    con la ruta original sin ``..`` — unico caso que el gate real acepta.
    """
    target_abs = os.path.normpath(os.path.join(repo_root, orig_value))
    rel = os.path.relpath(target_abs, out_dir_abs)
    return rel.replace(os.sep, "/")


def _rewrite_test_command(tests_rw: str, target_rw: str) -> str:
    """Reescribe ``test_command`` a ``python <rel>`` donde ``<rel>`` es la
    ruta relativa (POSIX) desde el directorio del ``target`` hasta el
    archivo de ``tests``.

    El gate CCDD ejecuta ``test_command`` con ``cwd`` = directorio del
    ``target`` (no la raiz del repo, ni el dir del ``.md``). Por eso el
    comando debe apuntar al archivo de tests con una ruta relativa al dir
    del target, y el archivo de tests debe ser auto-ejecutable
    (``unittest.main()`` bajo ``if __name__ == "__main__"``): se invoca como
    ``python <rel>`` (no ``python -m unittest ...``), que ademas inserta
    ``src/`` al ``sys.path`` por convencion del repo. ``tests_rw`` y
    ``target_rw`` ya son POSIX relativas al export; la relativa entre ellas
    es invariante al prefijo comun, asi que el resultado no depende de
    ``out_dir``.
    """
    target_dir = os.path.dirname(target_rw)
    rel = os.path.relpath(tests_rw, target_dir).replace(os.sep, "/")
    return "python " + rel


# ---------------------------------------------------------------------------
# Funcion principal del contrato
# ---------------------------------------------------------------------------

def export_gate_contract(contract_path: str, out_dir: str,
                          repo_root: str = ".") -> str:
    """Lee el contrato KDD (UTF-8), emite ``<out_dir>/<task>.gate.md``
    gate-nativo y devuelve la ruta escrita.

    Transformaciones: (1) normalizacion ASCII de TODO el texto; (2) ``target``
    y ``tests`` del frontmatter reescritos relativos al archivo de export
    (vive bajo ``out_dir``, separador '/'); ``test_command`` reescrito a
    ``python <rel>`` relativo al directorio del ``target`` (el gate ejecuta
    ``test_command`` con ``cwd`` = dir del ``target``; el archivo de tests
    debe ser auto-ejecutable con ``unittest.main()``); (3) resto verbatim.
    Determinista: mismo input -> bytes identicos.

    ``repo_root`` es la raiz del repo (convencion KDD): las rutas
    ``target``/``tests`` del contrato se interpretan relativas a el.
    Default ``'.'`` = cwd de invocacion, resuelto a absoluto. Pasado
    explicito, el resultado es INDEPENDIENTE del cwd desde el que se invoque
    (fija la convencion en vez de depender implicitamente de ``getcwd()``).

    El gate CCDD real exige rutas ``target``/``tests`` SIN ``..`` (el lint
    rechaza ``tc-tests-frozen`` si escapan del dir del contrato). El default
    correcto es ``out_dir`` = raiz del repo: ahi las rutas quedan iguales a
    las originales (``src/users.py``, ``tests/test_users.py``) y
    ``test_command`` queda ``python ../tests/test_users.py``.

    Raises ``ValueError`` si falta frontmatter o las claves ``task``/``target``
    /``tests``.
    """
    with open(contract_path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    fm_lines, body = _split_frontmatter(raw)
    if fm_lines is None:
        raise ValueError(
            "frontmatter no encontrado o no delimitado por '---': {}".format(
                contract_path))

    task, _ = _scalar_value(fm_lines, "task")
    target, _ = _scalar_value(fm_lines, "target")
    tests, _ = _scalar_value(fm_lines, "tests")
    missing = [k for k, v in (("task", task), ("target", target), ("tests", tests))
               if v is None or v == ""]
    if missing:
        raise ValueError(
            "clave(s) requerida(s) ausente(s) en el frontmatter: {}".format(
                ", ".join(missing)))

    repo_root_abs = os.path.abspath(repo_root)
    out_dir_abs = os.path.abspath(out_dir)
    target_rw = _rewrite_path(target, out_dir_abs, repo_root_abs)
    tests_rw = _rewrite_path(tests, out_dir_abs, repo_root_abs)
    test_command_rw = _rewrite_test_command(tests_rw, target_rw)

    # Reemplazar las lineas de target, tests y test_command en el frontmatter
    # crudo. test_command solo se reescribe si la clave existe; el resto del
    # frontmatter va verbatim.
    new_fm = list(fm_lines)
    for key, new_val in (("target", target_rw), ("tests", tests_rw),
                         ("test_command", test_command_rw)):
        idx = _key_line_index(new_fm, key)
        if idx >= 0:
            new_fm[idx] = _replace_scalar_line(new_fm[idx], new_val)

    text = "\n".join(["---"] + new_fm + ["---"]) + "\n" + body
    normalized = _ascii_normalize(text)

    task_ascii = _ascii_normalize(task)
    if not task_ascii:
        raise ValueError("la clave 'task' normaliza a vacio: {}".format(task))

    os.makedirs(out_dir_abs, exist_ok=True)
    out_path = os.path.join(out_dir_abs, task_ascii + ".gate.md")
    with open(out_path, "w", encoding="ascii", newline="") as fh:
        fh.write(normalized)
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv) -> int:
    parser = argparse.ArgumentParser(
        description="Exporta un task contract KDD a su variante gate-nativa "
                    "(ASCII + rutas relativas al export).")
    parser.add_argument("contract", help="ruta al contrato .md")
    parser.add_argument("--out-dir", default=".",
                        help="directorio de salida (default: '.' = raiz del "
                             "repo, que emite <task>.gate.md con rutas "
                             "target/tests SIN '..' como exige el gate real)")
    parser.add_argument("--repo-root", default=".",
                        help="raiz del repo (convencion KDD): las rutas "
                             "target/tests del contrato se interpretan "
                             "relativas a este dir. Default '.' = cwd de "
                             "invocacion. Resuelto a absoluto; con valor "
                             "explicito el export es independiente del cwd.")
    args = parser.parse_args(argv[1:])

    try:
        out_path = export_gate_contract(
            args.contract, args.out_dir, args.repo_root)
    except ValueError as e:
        print("ERROR (contrato invalido): {}".format(e), file=sys.stderr)
        return 2
    except OSError as e:
        print("ERROR (I/O): {}".format(e), file=sys.stderr)
        return 1

    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))