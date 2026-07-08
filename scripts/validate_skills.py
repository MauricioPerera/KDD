#!/usr/bin/env python3
"""Validador determinista de skills de agente (Contrato 24).

Valida skills bajo directorios especificados: estructura, frontmatter,
cuerpo, enlaces y unicidad de nombres. Sin LLM, sin red, sin subprocess.

Usa el MISMO dialecto YAML minimal que validate_okf.py y validate_contracts.py
(mismos 4 simbolos exportados: _split_inline_list, _parse_scalar, _parse_block,
parse_frontmatter).

Usage:
    python scripts/validate_skills.py [dir ...]
"""

import os
import re
import sys


# ---------------------------------------------------------------------------
# Parser YAML minimal (COPIA identica de validate_okf.py)
# ---------------------------------------------------------------------------

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
# Helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r'^`{3,}.*$', re.MULTILINE)
_INLINE_CODE_RE = re.compile(r'`[^`\n]*`')
_LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\n]*)\)')


def _strip_code(text):
    """Elimina bloques vallados (```...```) y code spans (`...`) del texto.

    Evita que enlaces escritos como ejemplos literales se interpreten como
    enlaces reales.
    """
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


def _resolve_link(src_abs, target, skill_dir_abs):
    """Resuelve un target relativo contra el directorio del archivo origen.

    Devuelve (resolved_abs, inside_repo) o (None, False) si se ignora.
    """
    if _is_external(target):
        return None, False
    t = target.strip()
    # Quitar fragmento.
    t = t.split('#')[0].strip()
    t = t.split()[0] if t else ''
    if not t:
        return None, False
    # Rutas absolutas: fuera del alcance.
    if t.startswith('/'):
        return None, False
    resolved = os.path.normpath(os.path.join(os.path.dirname(src_abs), t))
    # Revisar si existe (no si esta dentro de un dir especifico; verifica existencia).
    return resolved, True


def _rel(path, base):
    """Ruta relativa a `base` con separadores '/' (estable/portable)."""
    return os.path.relpath(path, base).replace(os.sep, '/')


def _finding(file, rule, msg, level='ERROR'):
    return {'file': file, 'level': level, 'rule': rule, 'msg': msg}


# ---------------------------------------------------------------------------
# Validacion de skills
# ---------------------------------------------------------------------------

def validate_skills(skill_dirs):
    """Valida skills bajo los directorios especificados.

    Devuelve lista de findings [{'file','level','rule','msg'}] ordenados por
    (file, rule), con rutas en estilo posix ('/'). Vacia si todo es conforme.

    Capa opcional: dir inexistente -> finding INFO rule DIR_MISSING (no error).
    """
    findings = []
    name_to_files = {}  # Para detectar duplicados globalmente

    # Procesar cada directorio de skills
    for skill_dir in skill_dirs:
        skill_dir_abs = os.path.abspath(skill_dir)
        skill_dir_name = os.path.basename(skill_dir_abs)

        # Dir inexistente: INFO, no error
        if not os.path.isdir(skill_dir_abs):
            findings.append(_finding(skill_dir, 'DIR_MISSING',
                                     'directorio no existe', level='INFO'))
            continue

        # Listar subdirectorios inmediatos
        try:
            entries = os.listdir(skill_dir_abs)
        except OSError:
            continue

        for entry in entries:
            entry_path = os.path.join(skill_dir_abs, entry)
            if not os.path.isdir(entry_path):
                # Archivos sueltos en el dir se ignoran
                continue

            skill_name = entry
            skill_md = os.path.join(entry_path, 'SKILL.md')
            # File path en formato posix: "skill_dir_name/skill_name" o similar
            file_rel_prefix = skill_dir_name + '/' + skill_name
            file_rel_full = file_rel_prefix + '/SKILL.md'

            # SKILL_MISSING
            if not os.path.isfile(skill_md):
                findings.append(_finding(file_rel_prefix, 'SKILL_MISSING',
                                        'SKILL.md no encontrado'))
                continue

            # Leer SKILL.md
            try:
                with open(skill_md, 'r', encoding='utf-8') as fh:
                    text = fh.read()
            except OSError:
                findings.append(_finding(file_rel_full, 'IO',
                                        'no se pudo leer SKILL.md'))
                continue

            # FM_PARSE
            fm_data, body = parse_frontmatter(text)
            if fm_data is None:
                findings.append(_finding(file_rel_full, 'FM_PARSE',
                                        "frontmatter YAML no encontrado o no delimitado por '---'"))
                continue

            # FM_NAME: presente, string, no vacio
            name = fm_data.get('name')
            if not name or not isinstance(name, str) or name == '':
                findings.append(_finding(file_rel_full, 'FM_NAME',
                                        'name ausente, no-string o vacio'))
                # Seguir checks si es posible
            else:
                # FM_NAME_KEBAB
                if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
                    findings.append(_finding(file_rel_full, 'FM_NAME_KEBAB',
                                            'name no es kebab-case'))

                # FM_NAME_DIR: name == skill_dir_name
                if name != skill_name:
                    findings.append(_finding(file_rel_full, 'FM_NAME_DIR',
                                            'name ({}) no coincide con directorio ({})'.format(
                                                name, skill_name)))

                # NAME_DUP: registrar para deteccion global
                if name not in name_to_files:
                    name_to_files[name] = []
                name_to_files[name].append((file_rel_full, entry_path))

            # FM_DESC: presente, string, no vacio
            desc = fm_data.get('description')
            if not desc or not isinstance(desc, str) or desc == '':
                findings.append(_finding(file_rel_full, 'FM_DESC',
                                        'description ausente, no-string o vacia'))
            else:
                # FM_DESC_LEN: [50, 1024]
                desc_len = len(desc)
                if desc_len < 50 or desc_len > 1024:
                    findings.append(_finding(file_rel_full, 'FM_DESC_LEN',
                                            'description largo {} fuera de [50, 1024]'.format(
                                                desc_len)))

            # BODY_EMPTY
            if not body.strip():
                findings.append(_finding(file_rel_full, 'BODY_EMPTY',
                                        'cuerpo vacio'))

            # LINK_BROKEN: enlaces relativos que no resuelven
            for target in _extract_links(body):
                resolved, _inside = _resolve_link(skill_md, target, skill_dir_abs)
                if resolved is None:
                    continue  # Externo, ancla, etc.
                if not os.path.exists(resolved):
                    findings.append(_finding(file_rel_full, 'LINK_BROKEN',
                                            'enlace roto: {}'.format(target)))

    # NAME_DUP: detectar duplicados globales
    for name, files in name_to_files.items():
        if len(files) > 1:
            # Un finding por ocurrencia extra, anclado en el archivo
            # lexicograficamente posterior
            files_sorted = sorted(files, key=lambda x: x[0])
            for i in range(1, len(files_sorted)):
                file_rel, _entry_path = files_sorted[i]
                findings.append(_finding(file_rel, 'NAME_DUP',
                                        'name {} repetido entre skills'.format(name)))

    # Ordenar findings por (file, rule)
    findings.sort(key=lambda f: (f['file'], f['rule']))
    return findings


def _count_scanned_skills(skill_dirs):
    """Cuenta los subdirectorios inmediatos escaneados como skills.

    Misma regla que validate_skills: cada subdirectorio inmediato de cada
    dir existente es una skill escaneada (archivos sueltos no cuentan).
    """
    count = 0
    for skill_dir in skill_dirs:
        skill_dir_abs = os.path.abspath(skill_dir)
        if not os.path.isdir(skill_dir_abs):
            continue
        try:
            entries = os.listdir(skill_dir_abs)
        except OSError:
            continue
        for entry in entries:
            if os.path.isdir(os.path.join(skill_dir_abs, entry)):
                count += 1
    return count


def main(argv):
    """CLI: imprime findings y resumen; exit 0 sin ERRORs, 1 con >=1 ERROR."""
    skill_dirs = argv if argv else ['skills', '.agents/skills']

    findings = validate_skills(skill_dirs)

    errors = [f for f in findings if f['level'] == 'ERROR']

    if findings:
        for f in findings:
            print("{} [{}] {}: {}".format(f['level'], f['rule'],
                                         f['file'], f['msg']))

    # M = skills ESCANEADAS: subdirectorios inmediatos examinados (misma
    # regla que validate_skills: os.path.isdir), tengan findings o no.
    scanned = _count_scanned_skills(skill_dirs)

    print()
    print("Resumen: {} error(es) en {} skill(s)".format(
        len(errors), scanned))

    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
