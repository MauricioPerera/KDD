#!/usr/bin/env python3
"""Validador determinista de conformidad OKF para toda la KB (OKF-SPEC §1-§5).

Sin LLM, sin red, sin subprocess. Solo stdlib. Recibe el directorio raiz de la
KB (default: knowledge) y valida cada *.md (recursivo) segun OKF-SPEC:

  §1-§2 Frontmatter: presente, YAML parseable (mismo dialecto que
       scripts/validate_contracts.py), claves type/title/description/tags
       presentes; tags lista no vacia y en minusculas.
  §3 Tipos: type exactamente uno de 'Task Contract' | 'Data Model' |
       'Architecture' | 'Concept'.
  §4 Enlaces: todo enlace markdown relativo que apunte dentro de knowledge/
       debe resolver a un archivo .md existente o a una carpeta existente;
       enlace roto = ERROR, y archivo existente con otra extension (p. ej. .txt)
       = ERROR nombrando archivo y extension. Enlaces externos (http(s),
       mailto, rutas fuera del bundle) se ignoran.
  §5 Huérfanos: todo nodo alcanzable desde knowledge/index.md — enlace directo
       al archivo o enlace a su carpeta (los .md de esa carpeta quedan
       alcanzables). index.md es la raiz y no requiere frontmatter.

  exit 0 si no hay errores, 1 si hay >=1 error.

Uso:
    python scripts/validate_okf.py [knowledge_dir]
"""

import os
import re
import sys


# ---------------------------------------------------------------------------
# Parser YAML minimal (mismo dialecto que scripts/validate_contracts.py)
# ---------------------------------------------------------------------------
# Soporta: escalares (con o sin comillas), listas inline ['a','b'] y dicts
# anidados por indentacion. No es un parser YAML general; es suficiente para
# el frontmatter OKF.

def _split_inline_list(inner):
    """Parte el contenido entre [ ] respetando comillas simples/dobles."""
    items = []
    buf = []
    quote = None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == ',':
            items.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    last = ''.join(buf).strip()
    if last:
        items.append(last)
    return items


def _parse_scalar(value):
    value = value.strip()
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item) for item in _split_inline_list(inner)]
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        return value[1:-1]
    return value


def _parse_block(lines, start, indent):
    """Parsea un bloque dict a partir de la linea `start` con indent `indent`.

    Devuelve (dict, indice_siguiente).
    """
    result = {}
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        cur_indent = len(line) - len(line.lstrip(' '))
        if cur_indent < indent:
            break
        if cur_indent > indent:
            i += 1
            continue
        stripped = line.strip()
        if ':' not in stripped:
            i += 1
            continue
        key, _, value = stripped.partition(':')
        key = key.strip()
        value = value.strip()
        if value == '':
            j = i + 1
            child_indent = None
            while j < n:
                l = lines[j]
                if not l.strip():
                    j += 1
                    continue
                ci = len(l) - len(l.lstrip(' '))
                if ci <= indent:
                    break
                child_indent = ci
                break
            if child_indent is not None:
                child, j = _parse_block(lines, i + 1, child_indent)
                result[key] = child
                i = j
            else:
                result[key] = ''
                i += 1
        else:
            result[key] = _parse_scalar(value)
            i += 1
    return result, i


def parse_frontmatter(text):
    """Devuelve (dict, body_str) o (None, body) si no hay frontmatter valido.

    El frontmatter comienza en la primera linea con '---' y termina en la
    siguiente linea con '---'.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines) or lines[idx].strip() != '---':
            return None, text
        start = idx
    else:
        start = 0
    end = None
    for k in range(start + 1, len(lines)):
        if lines[k].strip() == '---':
            end = k
            break
    if end is None:
        return None, text
    fm_lines = lines[start + 1:end]
    body_lines = lines[end + 1:]
    data, _ = _parse_block(fm_lines, 0, 0)
    return data, '\n'.join(body_lines)


# ---------------------------------------------------------------------------
# Constantes OKF (OKF-SPEC §2-§3)
# ---------------------------------------------------------------------------

REQUIRED_KEYS = ['type', 'title', 'description', 'tags']
VALID_TYPES = {'Task Contract', 'Data Model', 'Architecture', 'Concept'}

INDEX_NAME = 'index.md'


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(file, rule, msg, level='ERROR'):
    return {'file': file, 'level': level, 'rule': rule, 'msg': msg}


# ---------------------------------------------------------------------------
# Extraccion de enlaces markdown (ignorando codigo)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r'^`{3,}.*$', re.MULTILINE)
_INLINE_CODE_RE = re.compile(r'`[^`\n]*`')
_LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\n]*)\)')


def _strip_code(text):
    """Elimina bloques vallados (```...```) y code spans (`...`) del texto.

    Evita que enlaces escritos como ejemplos literales (p. ej. dentro de
    backticks) se interpreten como enlaces reales del nodo.
    """
    # Reemplazar bloques vallados por lineas vacias (conserva el conteo de
    # lineas para no alterar otros procesamientos).
    lines = text.splitlines()
    out = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
            out.append('')
            continue
        out.append('' if in_fence else line)
    text = '\n'.join(out)
    # Eliminar code spans inline.
    text = _INLINE_CODE_RE.sub('', text)
    return text


def _extract_links(text):
    """Devuelve lista de targets de enlaces markdown presentes en `text`."""
    clean = _strip_code(text)
    return [m.group(2) for m in _LINK_RE.finditer(clean)]


_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')


def _is_external(target):
    """True para enlaces externos (esquema http(s), mailto, etc.) o anclas."""
    t = target.strip()
    if t.startswith('#'):
        return True
    if t.lower().startswith('mailto:'):
        return True
    if _SCHEME_RE.match(t):
        return True
    return False


def _resolve_link(src_abs, target, kb_abs):
    """Resuelve un target relativo contra el directorio del archivo origen.

    Devuelve (resolved_abs, inside_bundle) o (None, False) si se ignora
    (externo, ancla o ruta absoluta fuera del bundle).
    """
    if _is_external(target):
        return None, False
    t = target.strip()
    # Quitar fragmento y titulo de enlace.
    t = t.split('#')[0].strip()
    t = t.split()[0] if t else ''
    if not t:
        return None, False
    # Rutas absolutas del filesystem: fuera del alcance del bundle.
    if t.startswith('/'):
        return None, False
    resolved = os.path.normpath(os.path.join(os.path.dirname(src_abs), t))
    try:
        inside = (os.path.commonpath([resolved, kb_abs]) == kb_abs)
    except ValueError:
        # commonpath lanza si las rutas no comparten base (p. ej. unidades
        # de Windows distintas): el destino queda fuera del bundle (§4).
        return resolved, False
    return resolved, inside


# ---------------------------------------------------------------------------
# Validacion por archivo
# ---------------------------------------------------------------------------

def _rel(path, base):
    """Ruta relativa a `base` con separadores '/' (estable/portable)."""
    return os.path.relpath(path, base).replace(os.sep, '/')


def _validate_frontmatter(file_rel, text):
    """§1-§3: frontmatter, claves, tags y type. Devuelve (findings, data)."""
    findings = []
    data, _ = parse_frontmatter(text)
    if data is None:
        findings.append(_finding(
            file_rel, 'FM',
            "frontmatter YAML no encontrado o no delimitado por '---'"))
        return findings, None
    if not isinstance(data, dict):
        findings.append(_finding(file_rel, 'FM', 'el frontmatter no es un mapping'))
        return findings, None

    for key in REQUIRED_KEYS:
        if key not in data:
            findings.append(_finding(
                file_rel, 'FM_KEY', 'clave requerida ausente: {}'.format(key)))
        elif data[key] == '' or data[key] is None:
            findings.append(_finding(
                file_rel, 'FM_KEY', 'clave requerida vacia: {}'.format(key)))

    # §2 tags: lista no vacia, valores en minusculas.
    tags = data.get('tags')
    if tags is None or tags == '':
        # ya reportado por FM_KEY si ausente/vacia; nada extra
        pass
    elif not isinstance(tags, list):
        findings.append(_finding(
            file_rel, 'TAGS', 'tags debe ser una lista (se encontro: {!r})'.format(tags)))
    elif len(tags) == 0:
        findings.append(_finding(file_rel, 'TAGS', 'tags debe ser una lista no vacia'))
    else:
        for tag in tags:
            if not isinstance(tag, str) or tag == '':
                findings.append(_finding(
                    file_rel, 'TAGS', 'tag vacio o no string en tags: {!r}'.format(tag)))
            elif tag != tag.lower():
                findings.append(_finding(
                    file_rel, 'TAGS', "tag en mayusculas (debe ser minuscula): {!r}".format(tag)))

    # §3 type reconocido.
    type_val = data.get('type')
    if type_val not in VALID_TYPES:
        findings.append(_finding(
            file_rel, 'TYPE',
            "type debe ser uno de {} (se encontro: {!r})".format(
                sorted(VALID_TYPES), type_val)))

    return findings, data


def _validate_links(file_rel, src_abs, text, kb_abs):
    """§4: enlaces relativos internos deben resolver, dentro de knowledge/, a un
    archivo .md existente o a una carpeta existente.

    - Enlace roto (no existe) -> ERROR.
    - Carpeta existente -> valido (index.md enlaza carpetas a proposito; §5
      alcanza los .md hijos via ese enlace).
    - Archivo existente con extension distinta de .md -> ERROR nombrando el
      archivo y la extension.
    """
    findings = []
    for target in _extract_links(text):
        resolved, inside = _resolve_link(src_abs, target, kb_abs)
        if resolved is None:
            continue  # externo / ancla / fuera
        if not inside:
            continue  # apunta fuera del bundle: se ignora (spec §4)
        if not os.path.exists(resolved):
            findings.append(_finding(
                file_rel, 'LINK',
                "enlace roto: [{}]({}) -> no existe".format(
                    os.path.basename(resolved), target)))
            continue
        if os.path.isdir(resolved):
            continue  # carpeta existente: valido (§5 alcanza via carpeta)
        ext = os.path.splitext(resolved)[1].lower()
        if ext != '.md':
            findings.append(_finding(
                file_rel, 'LINK',
                "enlace a archivo no-.md: [{}]({}) -> existe pero es '{}' "
                "(debe ser .md o carpeta)".format(
                    os.path.basename(resolved), target, ext)))
    return findings


def _collect_md_files(kb_abs):
    """Lista de rutas absolutas de *.md bajo kb_abs, orden alfabetico estable."""
    out = []
    for dirpath, _dirs, files in os.walk(kb_abs):
        for name in files:
            if name.lower().endswith('.md'):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def _reachable_from_index(kb_abs):
    """§5: conjunto de rutas absolutas alcanzables desde index.md.

    Un nodo es alcanzable si index.md lo enlaza directamente, o enlaza a su
    carpeta (los .md hijos directos de esa carpeta quedan alcanzables).
    index.md mismo es la raiz y se considera alcanzable.
    Devuelve (reachable_set, index_abs, index_findings).
    """
    reachable = set()
    index_abs = os.path.join(kb_abs, INDEX_NAME)
    findings = []
    if not os.path.isfile(index_abs):
        findings.append(_finding(INDEX_NAME, 'INDEX',
                                 'index.md (raiz de alcanzabilidad) no existe'))
        return reachable, index_abs, findings
    reachable.add(index_abs)
    try:
        with open(index_abs, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError as e:
        findings.append(_finding(INDEX_NAME, 'INDEX', 'no se pudo leer index.md: {}'.format(e)))
        return reachable, index_abs, findings
    for target in _extract_links(text):
        resolved, inside = _resolve_link(index_abs, target, kb_abs)
        if resolved is None or not inside:
            continue
        if os.path.isfile(resolved):
            reachable.add(resolved)
        elif os.path.isdir(resolved):
            for name in sorted(os.listdir(resolved)):
                if name.lower().endswith('.md'):
                    reachable.add(os.path.join(resolved, name))
    return reachable, index_abs, findings


def validate_okf(knowledge_dir):
    """Valida todos los nodos .md bajo knowledge_dir segun OKF-SPEC §1-§5.

    Devuelve lista de findings [{'file','level','rule','msg'}], ordenados por
    archivo y luego regla. Vacia si la KB es conforme. No lanza ante KB
    invalida (reporta).
    """
    kb_abs = os.path.abspath(knowledge_dir)
    findings = []

    if not os.path.isdir(kb_abs):
        findings.append(_finding(knowledge_dir, 'IO', 'directorio inexistente: {}'.format(knowledge_dir)))
        return findings

    files = _collect_md_files(kb_abs)
    reachable, _index_abs, idx_findings = _reachable_from_index(kb_abs)
    findings.extend(idx_findings)

    for path in files:
        file_rel = _rel(path, kb_abs)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
        except OSError as e:
            findings.append(_finding(file_rel, 'IO', 'no se pudo leer: {}'.format(e)))
            continue

        is_index = (os.path.basename(path) == INDEX_NAME)

        # §1-§3 solo para nodos (index.md es catalogo, no nodo).
        if not is_index:
            fm_findings, _data = _validate_frontmatter(file_rel, text)
            findings.extend(fm_findings)

        # §4 enlaces: aplica a todos (incluido index.md).
        findings.extend(_validate_links(file_rel, path, text, kb_abs))

        # §5 huerfanos: solo nodos; index.md es la raiz.
        if not is_index and path not in reachable:
            findings.append(_finding(
                file_rel, 'ORPHAN',
                'nodo no alcanzable desde index.md (ni directo ni via su carpeta)'))

    findings.sort(key=lambda f: (f['file'], f['rule'], f.get('level', '')))
    return findings


# ---------------------------------------------------------------------------
# CLI (espejo del estilo de scripts/validate_contracts.py)
# ---------------------------------------------------------------------------

def main(argv):
    knowledge_dir = argv[1] if len(argv) > 1 else 'knowledge'
    if not os.path.isdir(knowledge_dir):
        print("ERROR: no existe el directorio: {}".format(knowledge_dir))
        return 1

    files = _collect_md_files(os.path.abspath(knowledge_dir))
    findings = validate_okf(knowledge_dir)

    errors = [f for f in findings if f['level'] == 'ERROR']
    warnings = [f for f in findings if f['level'] == 'WARNING']

    if findings:
        for f in findings:
            print("{} [{}] {}: {}".format(f['level'], f['rule'], f['file'], f['msg']))
    else:
        print("OK: todos los nodos OKF son conformes")

    print("\nResumen: {} error(es), {} warning(s) en {} archivo(s)"
          .format(len(errors), len(warnings), len(files)))

    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))