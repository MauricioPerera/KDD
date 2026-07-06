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
        ``out_dir``. ``test_command`` se reescribe preservando el RUNNER
        declarado en el contrato fuente (``python -m unittest``,
        ``node --test``, etc. — NO se hardcodea ``python``): se toma el
        valor ORIGINAL de ``test_command`` y se reemplaza dentro de el la
        aparicion literal del valor ORIGINAL de ``tests`` (relativo a
        ``repo_root``, antes de reescribirse) por la nueva ruta relativa al
        directorio del ``target`` (POSIX). Caso especial documentado: si
        el ``test_command`` original es EXACTAMENTE ``python -m unittest
        <archivo>.py`` (4 tokens), se reescribe a ``python <archivo>.py``
        (invocacion directa, SIN ``-m unittest``): los archivos de test
        Python de este repo son auto-ejecutables por convencion y ``-m
        unittest`` no acepta rutas con ``..`` (que el gate produce al
        correr con ``cwd`` = dir del ``target``). Si el contrato no declara
        ``test_command``, no se agrega la clave. Si el ``test_command``
        original no cae en el caso especial y no contiene la ruta original
        de ``tests`` como substring, se preserva tal cual (no se adivina).
        El gate ejecuta ``test_command`` con ``cwd`` = directorio del
        ``target``. El resto del frontmatter va verbatim.
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
import ntpath
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
# Chequeo cross-drive (Windows): fallo honesto de I/O antes de reescribir rutas
# ---------------------------------------------------------------------------

def cross_drive_io_error(repo_root_abs: str, out_dir_abs: str):
    """Devuelve un mensaje de error de I/O si ``repo_root_abs`` y
    ``out_dir_abs`` residen en unidades de Windows distintas, o ``None`` si
    comparten unidad (o en POSIX, donde ``splitdrive`` da ``''`` para ambos y
    el chequeo es no-op).

    Recibe los dos paths YA resueltos a absolutos y SOLO decide (funcion pura:
    sin I/O, sin entorno). Usa ``ntpath.splitdrive`` explicitamente para que el
    caso cross-drive sea detectable con paths literales estilo Windows
    (``C:\\foo`` vs ``D:\\bar``) aun corriendo en el CI Linux — donde
    ``ntpath.splitdrive`` de paths POSIX devuelve ``''`` y el chequeo no dispara.

    El export reescribe ``target``/``tests`` con ``os.path.relpath`` entre
    ``repo_root`` y ``out_dir``; un relpath entre ``C:`` y ``D:`` no existe en
    Windows (``ValueError: path is on mount ...``). Soportarlo exigiria rutas
    absolutas en el export, que el gate real rechaza. Decision de diseño: no se
    soporta; se falla claro como I/O (no como contrato invalido).
    """
    repo_drive = ntpath.splitdrive(repo_root_abs)[0]
    out_drive = ntpath.splitdrive(out_dir_abs)[0]
    if repo_drive and out_drive and repo_drive.lower() != out_drive.lower():
        return ("las rutas del export no pueden cruzar unidades de Windows: "
                "repo-root esta en la unidad {!r} y out-dir en la unidad {!r}. "
                "Use un --out-dir dentro de la unidad del --repo-root."
                .format(repo_drive, out_drive))
    return None


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


def _is_python_unittest_single_file(test_command_orig) -> bool:
    """True si ``test_command_orig`` es EXACTAMENTE el patron del propio
    repo ``python -m unittest <ruta-a-un-.py>``: 4 tokens, ``["python",
    "-m", "unittest", X]`` con ``X`` terminando en ``.py`` (ruta de archivo
    real, no nombre de modulo dotted — un modulo dotted no termina en
    ``.py``). Caso especial documentado en el contrato, no heuristica
    generica: los archivos de test Python de este repo son auto-ejecutables
    (``unittest.main()`` bajo ``if __name__ == "__main__":``) y ``-m
    unittest`` no acepta rutas con ``..`` (las trata como nombre de modulo
    y falla con ``ValueError: Empty module name``), y el gate ejecuta con
    ``cwd`` = dir del ``target`` (que produce rutas con ``..``).
    """
    if not test_command_orig:
        return False
    tokens = test_command_orig.split()
    if len(tokens) != 4:
        return False
    return (tokens[0] == "python" and tokens[1] == "-m"
            and tokens[2] == "unittest"
            and tokens[3].endswith(".py"))


def _rewrite_test_command(test_command_orig, tests_orig: str,
                          tests_rw: str, target_rw: str):
    """Reescribe ``test_command`` preservando el RUNNER declarado en el
    contrato fuente y reescribiendo SOLO la parte de ruta del archivo de
    tests. NO se hardcodea ``python``.

    Toma el valor ORIGINAL de ``test_command`` (tal como viene en el
    frontmatter) y reemplaza dentro de el la aparicion literal del valor
    ORIGINAL de ``tests`` (tal como viene en el frontmatter, relativo a
    ``repo_root``, ANTES de reescribirse) por la nueva ruta reescrita
    relativa al directorio del ``target`` (POSIX). El runner
    (``python -m unittest``, ``node --test``, etc.) se preserva intacto:
    solo cambia la ruta del archivo de tests.

    - Si ``test_command_orig`` es None o vacio (la clave no existe en el
      frontmatter), devuelve None: el llamador NO agrega la clave
      (comportamiento invariante respecto a contratos sin ``test_command``).
    - Caso especial (documentado, no heuristica generica): si
      ``test_command_orig`` es EXACTAMENTE ``python -m unittest
      <archivo>.py`` (4 tokens; ver ``_is_python_unittest_single_file``),
      el export final es ``"python " + <ruta reescrita>`` SIN ``-m
      unittest`` — invocacion directa del archivo. Motivo: los archivos de
      test Python de este repo son auto-ejecutables por convencion, y
      ``-m unittest`` no acepta rutas con ``..`` (que el gate produce al
      correr con ``cwd`` = dir del ``target``).
    - Si ``test_command_orig`` NO cae en el caso especial y NO contiene
      ``tests_orig`` como substring (caso raro: el comando usa una
      convencion distinta y no menciona la ruta literal de ``tests``), se
      preserva ``test_command_orig`` TAL CUAL: no se adivina. Decision
      documentada para evitar heuristicas no pedidas.

    El gate CCDD ejecuta ``test_command`` con ``cwd`` = directorio del
    ``target``; por eso la ruta reescrita apunta al archivo de tests
    relativa a ese dir. ``tests_rw`` y ``target_rw`` ya son POSIX relativas
    al export; la relativa entre ellas es invariante al prefijo comun, asi
    que el resultado no depende de ``out_dir``.
    """
    if not test_command_orig:
        return None
    target_dir = os.path.dirname(target_rw)
    rel = os.path.relpath(tests_rw, target_dir).replace(os.sep, "/")
    # Caso especial documentado: python -m unittest <archivo>.py -> python
    # <archivo>.py (auto-ejecutable; -m unittest no acepta rutas con ..).
    if _is_python_unittest_single_file(test_command_orig):
        return "python " + rel
    if tests_orig and tests_orig in test_command_orig:
        return test_command_orig.replace(tests_orig, rel)
    # El comando no menciona la ruta literal de tests: preservalo tal cual
    # (no se adivina una sustitucion).
    return test_command_orig


# ---------------------------------------------------------------------------
# Funcion principal del contrato
# ---------------------------------------------------------------------------

def export_gate_contract(contract_path: str, out_dir: str,
                          repo_root: str = ".") -> str:
    """Lee el contrato KDD (UTF-8), emite ``<out_dir>/<task>.gate.md``
    gate-nativo y devuelve la ruta escrita.

    Transformaciones: (1) normalizacion ASCII de TODO el texto; (2) ``target``
    y ``tests`` del frontmatter reescritos relativos al archivo de export
    (vive bajo ``out_dir``, separador '/'); ``test_command`` reescrito
    preservando el RUNNER del contrato fuente (no se hardcodea ``python``):
    se reemplaza la ruta original de ``tests`` dentro del ``test_command``
    original por la nueva ruta relativa al directorio del ``target`` (el
    gate ejecuta ``test_command`` con ``cwd`` = dir del ``target``); si el
    contrato no declara ``test_command`` no se agrega la clave, y si el
    ``test_command`` original no menciona la ruta de ``tests`` se preserva
    tal cual; (3) resto verbatim. Determinista: mismo input -> bytes identicos.

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
    /``tests``. Raises ``OSError`` si ``repo_root`` y ``out_dir`` estan en
    unidades de Windows distintas (las rutas del export no pueden cruzar
    unidades: un ``relpath`` entre ``C:`` y ``D:`` no existe); el CLI lo mapea
    a exit 1 (I/O), no a contrato invalido.
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
    test_command_orig, _ = _scalar_value(fm_lines, "test_command")
    missing = [k for k, v in (("task", task), ("target", target), ("tests", tests))
               if v is None or v == ""]
    if missing:
        raise ValueError(
            "clave(s) requerida(s) ausente(s) en el frontmatter: {}".format(
                ", ".join(missing)))

    repo_root_abs = os.path.abspath(repo_root)
    out_dir_abs = os.path.abspath(out_dir)
    # Antes de reescribir rutas: si repo_root y out_dir estan en unidades de
    # Windows distintas, os.path.relpath entre ellas no existe (ValueError).
    # Se falla como I/O (no contrato invalido): el chequeo es de I/O de rutas,
    # no de validez del contrato. Funcion pura testeable con paths literales.
    xd = cross_drive_io_error(repo_root_abs, out_dir_abs)
    if xd:
        raise OSError(xd)
    target_rw = _rewrite_path(target, out_dir_abs, repo_root_abs)
    tests_rw = _rewrite_path(tests, out_dir_abs, repo_root_abs)
    test_command_rw = _rewrite_test_command(test_command_orig, tests,
                                             tests_rw, target_rw)

    # Reemplazar las lineas de target, tests y test_command en el frontmatter
    # crudo. test_command solo se reescribe si la clave existe; el resto del
    # frontmatter va verbatim.
    new_fm = list(fm_lines)
    for key, new_val in (("target", target_rw), ("tests", tests_rw),
                         ("test_command", test_command_rw)):
        if new_val is None:
            continue
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