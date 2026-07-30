"""Auditor de `forbids` declarado vs realmente impedido (Contrato: forbids-audit).

Herramienta ADVISORY: el campo ``forbids`` de un task contract enumera
capacidades prohibidas al implementador (``network``, ``subprocess``, ``llm``,
``unsafe``), pero hasta ahora NADIE verificaba su contenido -- ``tc_lint`` solo
avisa si la lista esta vacia. Un contrato podia declarar ``forbids:
['unsafe']`` sobre un proyecto Rust que permite ``unsafe`` sin que ningun gate
lo notara: la prohibicion era decorativa.

Este auditor cierra la mitad mecanica de ese hueco. Para cada capacidad
declarada busca un verificador (capacidad, lenguaje); si no lo hay, lo dice
con ``FORBID_UNVERIFIED`` en vez de callar -- asi queda explicito QUE parte de
tu ``forbids`` es garantia y que parte sigue siendo intencion.

Hoy hay dos verificadores, ambos para ``unsafe``, en Rust y Go -- y son
deliberadamente distintos. En Rust la prohibicion es comprobable de verdad:
el compilador la impone sobre el crate entero (``#![forbid(unsafe_code)]`` o
``unsafe_code = "deny"`` en los lints del manifiesto), no solo sobre un
archivo; el verificador Rust comprueba esa denegacion y calla si existe. En
Go NO existe mecanismo de compilador equivalente (no hay flag de build, ni
lint estandar del toolchain, ni convencion en ``go.mod`` que prohiba el
paquete ``unsafe`` a nivel proyecto): el verificador Go solo verifica
PRESENCIA del import, nunca enforcement, y ``go_denies_unsafe`` devuelve
``False`` siempre -- la honestidad de que hoy no hay denegacion mecanica es el
valor de la funcion, no un defecto a disimular. ``network`` / ``subprocess``
/ ``llm`` quedan sin verificador: decidir si una llamada abre red exige mas
que un scan textual y se reportan como no verificados, no como sanos.

Advisory por diseno, misma frontera que ``audit_seals``: detectar la AUSENCIA
de una denegacion es mecanico; decidir que eso es inaceptable es del equipo
(``--strict``). NO es un gate de Nivel 1, NO corre en CI, y deliberadamente NO
esta en ``mcp_gate_dispatch.GATE_SPECS`` -- eso haria crecer ``LEVEL1_GATES``
y rompería el oraculo congelado del preflight (13 gates exactos); promoverlo
seria su propio contrato con ambos oraculos re-sellados.

Solo LEE archivos. Sin subprocess, sin red, sin LLM. ASCII puro (lo audita
``lint_ascii``). Ver ``knowledge/contracts/forbids-audit.md``.

API (congelada por ``tests/test_audit_forbids.py``):
  Reglas (constantes str): FORBID_UNVERIFIED, FORBID_UNSAFE_PRESENT,
    FORBID_UNSAFE_UNENFORCED.
  ``strip_noise(src) -> str`` -- quita comentarios de linea/bloque y literales
    string de fuente Rust, para que ``unsafe`` en un comentario o en un texto
    no cuente como uso.
  ``has_unsafe(src) -> bool`` -- True si el fuente USA ``unsafe`` (tras
    ``strip_noise``).
  ``crate_denies_unsafe(target_path, repo_root) -> bool`` -- True si el crate
    del target deniega ``unsafe`` a nivel compilador (atributo en la raiz del
    crate, o lints del ``Cargo.toml`` propio o heredados del workspace).
  ``go_strip_noise(src) -> str`` -- fuente Go sin comentarios de linea/bloque
    ni literales string RAW (backtick). A diferencia de ``strip_noise`` de
    Rust, NO quita los literales string con comillas dobles: la ruta de un
    import Go es un literal con comillas dobles (``import "unsafe"``), y
    quitarlo destruiria justo lo que ``go_has_unsafe_import`` detecta. Los
    unicos falsos import posibles vienen de comentarios y raw strings (que SI
    pueden contener una linea que empiece con ``import``); los strings con
    comillas dobles no pueden spansar lineas en Go, asi que no pueden fingir
    un import. Los comentarios de Python en este archivo pueden llevar tildes;
    los literales string son ASCII puro (lo audita ``lint_ascii``).
  ``go_has_unsafe_import(src) -> bool`` -- True si el fuente importa el
    paquete ``"unsafe"`` (linea unica o bloque agrupado, con o sin alias).
  ``go_denies_unsafe(target_path, repo_root) -> bool`` -- SIEMPRE False: Go no
    tiene mecanismo de compilador para prohibir el paquete ``unsafe`` a nivel
    proyecto. Punto de extension explicito para un futuro analizador estatico.
  ``audit_contract(contract_path, repo_root) -> list[dict]`` -- findings
    ``{'contract','rule','msg'}`` de UN contrato (lista vacia = sano).
  ``audit_forbids(contracts_dir='knowledge/contracts', repo_root='.') ->
    {'findings': [...], 'checked': int}`` -- recorre ``*.md`` (salta
    ``TEMPLATE-*``), findings ordenados por (contract, rule, msg).
  ``main(argv) -> int`` -- argv estilo ``sys.argv``; posicional opcional
    contracts_dir, flags ``--repo-root DIR`` y ``--strict``. Sin ``--strict``
    SIEMPRE 0 (advisory); con ``--strict`` 1 si hay ERRORs.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate_contracts import parse_frontmatter  # noqa: E402

FORBID_UNVERIFIED = 'FORBID_UNVERIFIED'
FORBID_UNSAFE_PRESENT = 'FORBID_UNSAFE_PRESENT'
FORBID_UNSAFE_UNENFORCED = 'FORBID_UNSAFE_UNENFORCED'

# Reglas que representan un incumplimiento real (no una limitacion del auditor).
_HARD_RULES = (FORBID_UNSAFE_PRESENT,)

_LINE_COMMENT = re.compile(r'//[^\n]*')
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.S)
# Literal string de Rust: "..." con escapes. Los raw strings (r"...", r#"..."#)
# se cubren parcialmente: el cuerpo del r"..." simple entra por este patron.
_STRING_LIT = re.compile(r'"(?:\\.|[^"\\])*"', re.S)
_UNSAFE = re.compile(r'\bunsafe\b')

# Atributo a nivel de crate. `unsafe_code` NO matchea \bunsafe\b (el guion bajo
# es caracter de palabra), asi que buscar el atributo es independiente del scan.
_CRATE_ATTR = re.compile(r'#!\s*\[\s*(?:forbid|deny)\s*\(\s*unsafe_code\s*\)\s*\]')
_LINT_VALUE = re.compile(r'unsafe_code\s*=\s*(?:"(deny|forbid)"|\{[^}]*'
                         r'level\s*=\s*"(deny|forbid)"[^}]*\})')
_WORKSPACE_INHERIT = re.compile(r'workspace\s*=\s*true')
_SECTION = re.compile(r'^\s*\[([^\]]+)\]\s*$')


def strip_noise(src):
    """Fuente sin comentarios ni literales string (para no contar falsos usos).

    Orden deliberado: comentarios de bloque, luego de linea, luego strings. Un
    ``//`` DENTRO de un string se pierde como comentario -- limitacion aceptada
    (el objetivo es no reportar ``unsafe`` que no se ejecuta, no parsear Rust).
    """
    out = _BLOCK_COMMENT.sub(' ', src)
    out = _LINE_COMMENT.sub(' ', out)
    return _STRING_LIT.sub(' ', out)


def has_unsafe(src):
    """True si `src` usa la keyword ``unsafe`` fuera de comentarios/strings."""
    return _UNSAFE.search(strip_noise(src)) is not None


def _read(path):
    """Contenido de `path`, o None si no se puede leer."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return None


def _sections(text):
    """{nombre_de_seccion: cuerpo} de un TOML plano.

    Parser minimo deliberado (mismo criterio que el mini-YAML de
    ``validate_contracts``): solo necesita localizar ``[lints.rust]`` y
    ``[lints]``, no interpretar TOML completo. Evita fijar un piso de Python
    3.11 por ``tomllib`` en una plantilla que se distribuye a terceros.
    """
    out = {}
    current = ''
    out[current] = []
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            current = m.group(1).strip()
            out.setdefault(current, [])
        else:
            out[current].append(line)
    return {k: '\n'.join(v) for k, v in out.items()}


def _manifest_denies(manifest_text, workspace_prefix=False):
    """True si el manifiesto deniega unsafe_code en sus lints.

    Con `workspace_prefix`, mira ``[workspace.lints.rust]`` (raiz de workspace);
    sin el, ``[lints.rust]`` (crate propio).
    """
    key = 'workspace.lints.rust' if workspace_prefix else 'lints.rust'
    body = _sections(manifest_text).get(key, '')
    return _LINT_VALUE.search(body) is not None


def _inherits_workspace_lints(manifest_text):
    """True si el crate hereda los lints del workspace (``[lints] workspace = true``)."""
    body = _sections(manifest_text).get('lints', '')
    return _WORKSPACE_INHERIT.search(body) is not None


def _find_up(start_dir, filename, repo_root):
    """Ruta del primer `filename` hallado subiendo desde `start_dir` sin pasar
    `repo_root`, o None."""
    cur = os.path.abspath(start_dir)
    stop = os.path.abspath(repo_root)
    while True:
        candidate = os.path.join(cur, filename)
        if os.path.isfile(candidate):
            return candidate
        if cur == stop or os.path.dirname(cur) == cur:
            return None
        cur = os.path.dirname(cur)


def crate_denies_unsafe(target_path, repo_root):
    """True si el crate del `target_path` deniega ``unsafe`` a nivel compilador.

    Tres vias, cualquiera alcanza (son equivalentes para rustc):
      1. ``#![forbid(unsafe_code)]`` / ``#![deny(unsafe_code)]`` en la raiz del
         crate (``src/lib.rs`` o ``src/main.rs``) -- o en el propio target.
      2. ``unsafe_code = "deny"`` bajo ``[lints.rust]`` del ``Cargo.toml`` del crate.
      3. El crate hereda del workspace (``[lints] workspace = true``) y la raiz
         del workspace lo deniega en ``[workspace.lints.rust]``.
    """
    target_abs = os.path.join(repo_root, target_path)
    manifest = _find_up(os.path.dirname(target_abs), 'Cargo.toml', repo_root)
    if manifest is None:
        return False

    crate_dir = os.path.dirname(manifest)
    # (1) atributo en la raiz del crate o en el target mismo
    roots = [os.path.join(crate_dir, 'src', 'lib.rs'),
             os.path.join(crate_dir, 'src', 'main.rs'),
             target_abs]
    for root in roots:
        text = _read(root)
        if text is not None and _CRATE_ATTR.search(text):
            return True

    manifest_text = _read(manifest)
    if manifest_text is None:
        return False
    # (2) lints del crate
    if _manifest_denies(manifest_text):
        return True
    # (3) heredados del workspace
    if _inherits_workspace_lints(manifest_text):
        parent = os.path.dirname(crate_dir)
        ws = _find_up(parent, 'Cargo.toml', repo_root) if parent else None
        ws_text = _read(ws) if ws else None
        if ws_text is not None and _manifest_denies(ws_text, workspace_prefix=True):
            return True
    return False


def _audit_unsafe_rust(target, repo_root):
    """Findings (rule, msg) de ``forbids: unsafe`` sobre un target Rust."""
    if crate_denies_unsafe(target, repo_root):
        return []  # el compilador lo impone sobre el crate: garantia real
    src = _read(os.path.join(repo_root, target))
    if src is not None and has_unsafe(src):
        return [(FORBID_UNSAFE_PRESENT,
                 "declara forbids: unsafe pero %s USA unsafe" % target)]
    return [(FORBID_UNSAFE_UNENFORCED,
             "declara forbids: unsafe pero el crate no lo deniega a nivel "
             "compilador; agrega unsafe_code = \"deny\" en [lints.rust] del "
             "Cargo.toml (o #![forbid(unsafe_code)] en la raiz del crate). "
             "Solo se verifico que %s no lo use hoy" % target)]


# --- Go -------------------------------------------------------------------
#
# Go es un lenguaje distinto de Rust en un punto importante que NO se oculta:
# Go NO tiene ningun mecanismo de compilador para prohibir el paquete `unsafe`
# a nivel de proyecto. No existe una flag de build, un lint estandar del
# toolchain, ni una convencion equivalente en `go.mod` (Rust tiene
# `unsafe_code = "deny"` / `#![forbid(unsafe_code)]`). Por eso el verificador Go
# solo verifica PRESENCIA del import, nunca enforcement: `go_denies_unsafe`
# devuelve False siempre, y la honestidad de esa ausencia es el valor.

_GO_LINE_COMMENT = re.compile(r'//[^\n]*')
_GO_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.S)
# Raw string de Go: `...` SIN procesamiento de escapes; un backtick no puede
# contener otro backtick, asi que el cierre es el primer backtick siguiente.
_GO_RAW_STRING = re.compile(r'`[^`]*`', re.S)


def go_strip_noise(src):
    """Fuente Go sin comentarios ni literales string RAW (backtick).

    A diferencia de ``strip_noise`` de Rust, NO quita los literales string con
    comillas dobles. La razon es especifica de Go: la ruta de un import Go es un
    literal con comillas dobles (``import "unsafe"``), y quitarlo dejaria
    ``import `` sin el nombre del paquete -- justo lo que
    ``go_has_unsafe_import`` necesita ver. Los unicos falsos import posibles
    vienen de comentarios y raw strings (que SI pueden contener una linea que
    empiece con ``import``); los strings con comillas dobles no pueden spansar
    lineas en Go, asi que no pueden fingir una linea ``import ...``. La
    deteccion posterior se ancla al inicio de linea (``^import``), que un
    string con comillas dobles cualquiera no puede cumplir.
    """
    out = _GO_BLOCK_COMMENT.sub(' ', src)
    out = _GO_LINE_COMMENT.sub(' ', out)
    return _GO_RAW_STRING.sub(' ', out)


# Deteccion del import del paquete "unsafe", anclada al import (no a cualquier
# aparicion de la palabra): un `\bunsafe\b` sobre todo el archivo daria falsos
# positivos con identificadores como `isUnsafe` o `unsafePool`.
# Alias valido en Go: un identificador (`u`, `unsafeAlias`), `_` (blank import)
# o `.` (dot import). Import path siempre con comillas dobles.
_GO_IMPORT_ALIAS = r'(?:[A-Za-z_]\w*|\.)\s+'
_GO_SINGLE_IMPORT = re.compile(
    r'^\s*import\s+(?:%s)?"unsafe"\s*$' % _GO_IMPORT_ALIAS, re.M)
_GO_GROUPED_IMPORT = re.compile(r'^\s*import\s*\((.*?)\)', re.S | re.M)
_GO_GROUPED_LINE = re.compile(
    r'^\s*(?:%s)?"unsafe"\s*$' % _GO_IMPORT_ALIAS, re.M)


def go_has_unsafe_import(src):
    """True si `src` importa el paquete ``"unsafe"`` fuera de comentarios/raw.

    Detecta tanto la forma de linea unica (``import "unsafe"``, con o sin
    alias: ``import u "unsafe"``, ``import _ "unsafe"``, ``import . "unsafe"``)
    como el ``"unsafe"`` (solo o con alias) dentro de un bloque de import
    agrupado::

        import (
            "fmt"
            "unsafe"
        )

    No usa un ``\\bunsafe\\b`` sobre todo el archivo: daria falsos positivos con
    identificadores como ``isUnsafe`` o ``unsafePool`` que NO son el import.
    La deteccion se ancla al import, no a cualquier aparicion de la palabra.
    """
    cleaned = go_strip_noise(src)
    if _GO_SINGLE_IMPORT.search(cleaned) is not None:
        return True
    for m in _GO_GROUPED_IMPORT.finditer(cleaned):
        if _GO_GROUPED_LINE.search(m.group(1)) is not None:
            return True
    return False


def go_denies_unsafe(target_path, repo_root):
    """True si el modulo Go del `target_path` deniega ``unsafe`` a nivel
    compilador.

    SIEMPRE devuelve False. Go NO tiene ningun mecanismo de compilador para
    prohibir el paquete ``unsafe`` a nivel de proyecto: no existe una flag de
    build, un lint estandar del toolchain, ni una convencion equivalente en
    ``go.mod`` (a diferencia de Rust, que tiene ``unsafe_code = "deny"`` /
    ``#![forbid(unsafe_code)]``). Por lo tanto no hay nada que checkear aqui,
    y no se inventa un mecanismo falso ni se simula con un check debil (ej.
    buscar un comentario magico) -- la honestidad de que HOY no hay
    enforcement es el valor de la funcion, no un defecto a disimular.

    Se deja como punto de extension explicito: si algun dia se integra un
    analizador estatico custom (via ``go/analysis`` o un linter externo) que SI
    verifique la denegacion a nivel proyecto, esta funcion es donde anzadirlo.
    Mientras tanto, el verificador Go solo reporta PRESENCIA del import.
    """
    return False


def _audit_unsafe_go(target, repo_root):
    """Findings (rule, msg) de ``forbids: unsafe`` sobre un target Go."""
    if go_denies_unsafe(target, repo_root):
        return []  # hoy inalcanzable (go_denies_unsafe es siempre False), pero
        # se llama igual que en Rust por consistencia y por si algun dia deja
        # de ser siempre False al integrar un analizador estatico.
    src = _read(os.path.join(repo_root, target))
    if src is not None and go_has_unsafe_import(src):
        return [(FORBID_UNSAFE_PRESENT,
                 "declara forbids: unsafe pero %s importa el paquete unsafe"
                 % target)]
    return [(FORBID_UNSAFE_UNENFORCED,
             "declara forbids: unsafe pero %s no esta impedido a nivel "
             "compilador: Go no tiene mecanismo de compilador para prohibir el "
             "paquete unsafe (no hay flag de build, ni lint estandar del "
             "toolchain, ni convencion en go.mod), a diferencia de Rust "
             "(unsafe_code = \"deny\"). Solo se verifico que %s no importa el "
             "paquete unsafe hoy" % (target, target))]


# (capacidad, lenguaje) -> verificador. Ausente = no verificable aun.
_VERIFIERS = {
    ('unsafe', 'rust'): _audit_unsafe_rust,
    ('unsafe', 'go'): _audit_unsafe_go,
}


def audit_contract(contract_path, repo_root):
    """Findings ``{'contract','rule','msg'}`` de UN contrato (vacio = sano)."""
    rel = os.path.basename(contract_path)
    text = _read(contract_path)
    if text is None:
        return []
    data, _ = parse_frontmatter(text)
    if not isinstance(data, dict):
        return []
    forbids = data.get('forbids')
    if not isinstance(forbids, list):
        return []
    target = data.get('target')
    if not isinstance(target, str) or not target:
        return []
    language = data.get('language') or 'python'
    if not isinstance(language, str):
        return []
    language = language.strip().lower()

    findings = []
    for cap in forbids:
        if not isinstance(cap, str) or not cap.strip():
            continue
        cap = cap.strip().lower()
        verifier = _VERIFIERS.get((cap, language))
        if verifier is None:
            findings.append({
                'contract': rel, 'rule': FORBID_UNVERIFIED,
                'msg': "forbids: %s no es verificable mecanicamente para "
                       "language=%s -- sigue siendo declarativo" % (cap, language)})
            continue
        for rule, msg in verifier(target, repo_root):
            findings.append({'contract': rel, 'rule': rule, 'msg': msg})
    findings.sort(key=lambda f: (f['contract'], f['rule'], f['msg']))
    return findings


def _collect(contracts_dir):
    """``*.md`` de `contracts_dir` salvo ``TEMPLATE-*`` (no son contratos reales)."""
    if not os.path.isdir(contracts_dir):
        return []
    return sorted(
        os.path.join(contracts_dir, n) for n in os.listdir(contracts_dir)
        if n.endswith('.md') and not n.startswith('TEMPLATE-'))


def audit_forbids(contracts_dir='knowledge/contracts', repo_root='.'):
    """``{'findings': [...], 'checked': int}`` sobre todos los contratos."""
    paths = _collect(contracts_dir)
    findings = []
    for p in paths:
        findings.extend(audit_contract(p, repo_root))
    findings.sort(key=lambda f: (f['contract'], f['rule'], f['msg']))
    return {'findings': findings, 'checked': len(paths)}


def main(argv):
    """CLI. Posicional opcional contracts_dir; flags --repo-root, --strict.

    Sin ``--strict`` SIEMPRE devuelve 0 (advisory). Con ``--strict`` devuelve 1
    si hay findings de regla dura (una prohibicion realmente incumplida); las
    limitaciones del auditor (``FORBID_UNVERIFIED``) nunca cambian el exit code.
    """
    contracts_dir = 'knowledge/contracts'
    repo_root = '.'
    strict = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--strict':
            strict = True
            i += 1
        elif a == '--repo-root':
            if i + 1 < len(argv):
                repo_root = argv[i + 1]
            i += 2
        elif a.startswith('--repo-root='):
            repo_root = a.split('=', 1)[1]
            i += 1
        elif not a.startswith('-'):
            contracts_dir = a
            i += 1
        else:
            i += 1
    result = audit_forbids(contracts_dir=contracts_dir, repo_root=repo_root)
    findings = result['findings']
    for f in findings:
        level = 'ERROR' if f['rule'] in _HARD_RULES else (
            'WARNING' if f['rule'] == FORBID_UNSAFE_UNENFORCED else 'INFO')
        print('%s [%s] %s: %s' % (level, f['rule'], f['contract'], f['msg']))
    hard = [f for f in findings if f['rule'] in _HARD_RULES]
    print('forbids-audit: %d checked, %d findings (%d duras)%s' % (
        result['checked'], len(findings), len(hard),
        ' [strict]' if strict else ''))
    return 1 if (strict and hard) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
