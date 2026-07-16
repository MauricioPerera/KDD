#!/usr/bin/env python3
"""Gate de perimetro (Contrato 28).

Validador determinista: dado un task contract (clave `touch_only`) y la lista
de archivos cambiados, falla si algo cayo fuera del perimetro. Parser mini-YAML
copiado identico de validate_contracts.py para garantizar coherencia.

Sin red, sin subprocess. Solo stdlib.
"""

import fnmatch
import sys


# ---------------------------------------------------------------------------
# Parser YAML minimal (identico a validate_contracts.py)
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
    """Devuelve (dict, body_str) o (None, body) si no hay frontmatter valido."""
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
# Validacion del perimetro
# ---------------------------------------------------------------------------

def _normalize_path(p):
    """Normaliza ruta: backslashes a '/', quita './' al inicio, limpia lineas."""
    p = p.strip()
    if not p:
        return None
    p = p.replace('\\', '/')
    if p.startswith('./'):
        p = p[2:]
    return p if p else None


def _normalize_changed_files(changed_files):
    """Normaliza lista de cambiados: elimina vacios, duplicados, ordena."""
    normalized = []
    for cf in changed_files:
        norm = _normalize_path(cf)
        if norm:
            normalized.append(norm)
    return sorted(list(set(normalized)))


def _is_valid_touch_only(touch_only):
    """Verifica si touch_only es lista no vacia de strings no vacios."""
    if not isinstance(touch_only, list):
        return False
    if len(touch_only) == 0:
        return False
    for item in touch_only:
        if not isinstance(item, str) or len(item) == 0:
            return False
    return True


def _matches_any_pattern(path, patterns):
    """Devuelve True si path matchea alguno de los patrones (fnmatch posix)."""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def validate_perimeter(contract_path, changed_files):
    """Valida que los archivos cambiados estan dentro del perimetro touch_only.

    Args:
        contract_path: ruta al archivo .md del contrato
        changed_files: lista de rutas (normalizadas o no) que cambiaron

    Returns:
        lista de findings {'file','level','rule','msg'} ordenados por
        (file, rule, msg). 'file' es la ruta posix del contrato (relativa,
        tal como se la pasa).
    """
    findings = []
    file_rel = contract_path.replace('\\', '/')

    # Leer contrato
    try:
        with open(contract_path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        findings.append({
            'file': file_rel,
            'level': 'ERROR',
            'rule': 'FM_PARSE',
            'msg': 'contrato inexistente o no legible'
        })
        return findings

    # Parsear frontmatter
    data, _body = parse_frontmatter(text)
    if data is None:
        findings.append({
            'file': file_rel,
            'level': 'ERROR',
            'rule': 'FM_PARSE',
            'msg': "frontmatter YAML no encontrado o no delimitado por '---'"
        })
        return findings

    # Validar touch_only
    touch_only = data.get('touch_only')
    if not _is_valid_touch_only(touch_only):
        findings.append({
            'file': file_rel,
            'level': 'ERROR',
            'rule': 'TOUCH_ONLY_MISSING',
            'msg': 'touch_only ausente, no-lista, vacia o con items no-string/vacios'
        })
        return findings

    # Normalizar cambiados
    normalized = _normalize_changed_files(changed_files)
    if not normalized:
        return findings

    # Obtener tests y target del contrato (para checks especiales)
    tests_path = data.get('tests', '')
    target_path = data.get('target', '')

    # Validar cada archivo cambiado
    for changed in normalized:
        # Regla: TESTS_TOUCHED
        if changed == tests_path and tests_path != target_path:
            findings.append({
                'file': file_rel,
                'level': 'ERROR',
                'rule': 'TESTS_TOUCHED',
                'msg': 'el archivo {} (oraculo congelado) no debe cambiar (tests != target)'.format(changed)
            })
            continue  # No emitir OUT_OF_PERIMETER para este archivo

        # Regla: OUT_OF_PERIMETER
        if not _matches_any_pattern(changed, touch_only):
            findings.append({
                'file': file_rel,
                'level': 'ERROR',
                'rule': 'OUT_OF_PERIMETER',
                'msg': 'archivo {} fuera del perimetro touch_only'.format(changed)
            })

    # Ordenar por (file, rule, msg)
    findings.sort(key=lambda f: (f['file'], f['rule'], f['msg']))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv):
    """CLI: python scripts/validate_perimeter.py <contract.md> [--changed f1 f2 ...]

    Sin --changed, lee los paths de stdin (uno por linea).
    Imprime findings y resumen. Exit 0 sin ERRORs, 1 con >=1.
    """
    if len(argv) < 1:
        print("Uso: python scripts/validate_perimeter.py <contract.md> [--changed f1 f2 ...]")
        return 1

    contract_path = argv[0]
    changed_files = []

    # Parsear argumentos
    if len(argv) > 1 and argv[1] == '--changed':
        changed_files = argv[2:]
    else:
        # Leer de stdin
        try:
            for line in sys.stdin:
                changed_files.append(line.rstrip('\n\r'))
        except EOFError:
            pass

    # Validar
    findings = validate_perimeter(contract_path, changed_files)

    # Imprimir findings
    errors = [f for f in findings if f['level'] == 'ERROR']
    for f in findings:
        print("{} [{}] {}: {}".format(f['level'], f['rule'], f['file'], f['msg']))

    # Imprimir resumen
    normalized_changed = _normalize_changed_files(changed_files)
    n_changed = len(normalized_changed)
    n_errors = len(errors)
    print("Resumen: {} error(es), {} archivo(s) cambiados".format(n_errors, n_changed))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
