#!/usr/bin/env python3
"""Validador determinista de contratos de tarea KDD (OKF + CCDD).

Sin LLM, sin red. Solo stdlib. Recibe un directorio (default:
knowledge/contracts) y valida cada *.md:

  (a) frontmatter YAML parseable delimitado por '---'
  (b) claves requeridas: task, intent, target, signature, test_command,
      budget, tests, deps_allowed, touch_only (type se valida aparte: debe
      ser 'Task Contract'); tests_sha256 es obligatoria (congela el oraculo de
      tests -> error FM_TESTS_FROZEN si falta, esta vacia o no coincide).
  (c) forbids presente y no vacio (WARNING si falta o vacio)
  (d) cuerpo con secciones obligatorias: ## Intent, ## Interface,
      ## Invariants, ## Examples (con >=2 items de lista), ## Do / Don't,
      ## Tests, ## Constraints (debe contener 'PARAR y reportar si')
  (e) exit 0 si no hay errores (los warnings no bloquean), 1 si hay >=1 error

Uso:
    python scripts/validate_contracts.py [directorio]
"""

import os
import sys
import hashlib
import re
import fnmatch


# ---------------------------------------------------------------------------
# Parser YAML minimal (subset usado por la plantilla KDD)
# ---------------------------------------------------------------------------
# Soporta: escalares (con o sin comillas), listas inline ['a','b'] y dicts
# anidados por indentacion. No es un parser YAML general; es suficiente para
# el frontmatter de los contratos.

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
            # linea sobre-indentada sin padre: la saltamos
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
            # buscar hijos indentados
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
        # permitir leading blank lines
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines) or lines[idx].strip() != '---':
            return None, text
        start = idx
    else:
        start = 0
    # encontrar el closing '---'
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
# Validacion
# ---------------------------------------------------------------------------

REQUIRED_KEYS = [
    'task', 'intent', 'target', 'signature',
    'test_command', 'budget', 'tests', 'deps_allowed', 'touch_only',
]

REQUIRED_SECTIONS = [
    'Intent', 'Interface', 'Invariants',
    'Examples', 'Do / Don\'t', 'Tests', 'Constraints',
]


class Finding:
    def __init__(self, file, rule, message, level='ERROR'):
        self.file = file
        self.rule = rule
        self.message = message
        self.level = level

    def __str__(self):
        return "{} [{}] {}: {}".format(self.level, self.rule, self.file, self.message)


def _is_non_empty(value):
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def _normalize_newlines(data):
    """Normaliza newlines a LF: \\r\\n -> \\n y \\r suelto -> \\n."""
    return data.replace('\r\n', '\n').replace('\r', '\n')


def _calculate_tests_hash(tests_path):
    """Calcula SHA256 del archivo tests con newlines normalizados a LF.

    Devuelve el hash hex (64 chars) o None si no se puede leer el archivo.
    """
    try:
        with open(tests_path, 'r', encoding='utf-8') as f:
            content = f.read()
        normalized = _normalize_newlines(content)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    except OSError:
        return None


def _is_valid_hex_hash(value):
    """Verifica si el valor es un hash hex válido (64 chars, lowercase)."""
    if not isinstance(value, str):
        return False
    return len(value) == 64 and re.match(r'^[0-9a-f]{64}$', value) is not None


def _extract_sections(body):
    """Devuelve dict nombre_seccion -> texto_de_la_seccion (sin header)."""
    sections = {}
    current = None
    buf = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith('## '):
            if current is not None:
                sections[current] = '\n'.join(buf)
            current = s[3:].strip()
            buf = []
        else:
            if current is not None:
                buf.append(line)
    if current is not None:
        sections[current] = '\n'.join(buf)
    return sections


def validate_file(path, repo_root=None):
    findings = []
    rel = path
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError as e:
        findings.append(Finding(rel, 'FM_PARSE', 'no se pudo leer: {}'.format(e)))
        return findings

    data, body = parse_frontmatter(text)
    if data is None:
        findings.append(Finding(rel, 'FM_PARSE',
                                "frontmatter YAML no encontrado o no delimitado por '---'"))
        return findings

    # (b) claves requeridas
    if not isinstance(data, dict):
        findings.append(Finding(rel, 'FM_PARSE', 'el frontmatter no es un mapping'))
        return findings

    type_val = data.get('type')
    if type_val != 'Task Contract':
        findings.append(Finding(rel, 'FM_KEY_type',
                                "type debe ser 'Task Contract' (se encontro: {!r})"
                                .format(type_val)))

    for key in REQUIRED_KEYS:
        if key not in data:
            findings.append(Finding(rel, 'FM_KEY_{}'.format(key),
                                    "clave requerida ausente: {}".format(key)))
        elif data[key] == '' or data[key] is None:
            findings.append(Finding(rel, 'FM_KEY_{}'.format(key),
                                    "clave requerida vacia: {}".format(key)))

    # (c) forbids -> WARNING si falta o vacio
    if 'forbids' not in data:
        findings.append(Finding(rel, 'FM_KEY_forbids',
                                "clave 'forbids' ausente (recomendado no vacia)",
                                level='WARNING'))
    elif not _is_non_empty(data['forbids']):
        findings.append(Finding(rel, 'FM_KEY_forbids',
                                "clave 'forbids' vacia (recomendado no vacia)",
                                level='WARNING'))

    # Validar que target y tests resuelvan a archivos existentes
    if repo_root is None:
        repo_root = '.'
    repo_root = os.path.abspath(repo_root)

    # Validar target
    if 'target' in data and data['target']:
        target_rel = data['target']
        target_abs = os.path.abspath(os.path.join(repo_root, target_rel))
        if not os.path.isfile(target_abs):
            findings.append(Finding(rel, 'FM_PATH_target',
                                    "target no existe o no es archivo: {} (resuelto a {})"
                                    .format(target_rel, target_abs)))

    # Validar tests
    if 'tests' in data and data['tests']:
        tests_rel = data['tests']
        tests_abs = os.path.abspath(os.path.join(repo_root, tests_rel))
        if not os.path.isfile(tests_abs):
            findings.append(Finding(rel, 'FM_PATH_tests',
                                    "tests no existe o no es archivo: {} (resuelto a {})"
                                    .format(tests_rel, tests_abs)))

    # Validar tests_sha256 (REQUERIDA)
    tests_sha256 = data.get('tests_sha256')
    if not tests_sha256:
        # Ausente o vacía = ERROR
        findings.append(Finding(
            rel, 'FM_TESTS_FROZEN',
            "clave 'tests_sha256' requerida para congelar el oraculo. Sellar con: python scripts/validate_contracts.py --hash <tests_path>"))
    else:
        # Clave presente: validar formato
        if not _is_valid_hex_hash(tests_sha256):
            findings.append(Finding(
                rel, 'FM_TESTS_FROZEN',
                "tests_sha256 con formato invalido (debe ser 64 chars hex lowercase): {!r}"
                .format(tests_sha256)))
        # Si tests existe, validar que el hash coincida
        elif 'tests' in data and data['tests']:
            tests_rel = data['tests']
            tests_abs = os.path.abspath(os.path.join(repo_root, tests_rel))
            if os.path.isfile(tests_abs):
                actual_hash = _calculate_tests_hash(tests_abs)
                if actual_hash is None:
                    # No se pudo leer el archivo, pero FM_PATH_tests ya lo reportó
                    pass
                elif actual_hash != tests_sha256:
                    findings.append(Finding(
                        rel, 'FM_TESTS_FROZEN',
                        "archivo '{}': hash esperado {}, hash actual {}"
                        .format(tests_rel, tests_sha256, actual_hash)))

    # Contrato 28: validar touch_only (SOLO checks nuevos, no modificar anteriores)
    touch_only = data.get('touch_only')

    # FM_TOUCH_ONLY: validar forma (debe ser lista no vacia de strings no vacios)
    if touch_only is not None:
        is_valid_form = (isinstance(touch_only, list) and len(touch_only) > 0 and
                         all(isinstance(item, str) and len(item) > 0 for item in touch_only))
        if not is_valid_form:
            findings.append(Finding(rel, 'FM_TOUCH_ONLY',
                                    "touch_only debe ser lista no vacia de strings no vacios"))
        else:
            # FM_TOUCH_TARGET: el target debe estar cubierto por algún patrón
            if 'target' in data and data['target']:
                target_val = data['target']
                is_covered = any(fnmatch.fnmatch(target_val, p) for p in touch_only)
                if not is_covered:
                    findings.append(Finding(rel, 'FM_TOUCH_TARGET',
                                            "target '{}' no esta cubierto por ningun patron en touch_only".format(target_val)))

            # FM_TOUCH_TESTS: el archivo tests NO debe estar cubierto (salvo si tests == target)
            if 'tests' in data and data['tests']:
                tests_val = data['tests']
                target_val = data.get('target', '')
                if tests_val != target_val:
                    is_covered = any(fnmatch.fnmatch(tests_val, p) for p in touch_only)
                    if is_covered:
                        findings.append(Finding(rel, 'FM_TOUCH_TESTS',
                                                "archivo tests '{}' no debe estar cubierto por ningun patron en touch_only (oraculo protegido)".format(tests_val)))

    # (d) secciones del cuerpo
    sections = _extract_sections(body)
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            findings.append(Finding(rel, 'SEC_{}'.format(name),
                                    "seccion obligatoria ausente: ## {}".format(name)))

    # Examples con >=2 items de lista
    examples = sections.get('Examples')
    if examples is not None:
        count = 0
        for line in examples.splitlines():
            if line.strip().startswith('- '):
                count += 1
        if count < 2:
            findings.append(Finding(rel, 'SEC_Examples',
                                    "## Examples requiere >=2 items de lista (se encontro {})"
                                    .format(count)))

    # Constraints debe contener 'PARAR y reportar si'
    constraints = sections.get('Constraints')
    if constraints is not None:
        if 'PARAR y reportar si' not in constraints:
            findings.append(Finding(
                rel, 'SEC_Constraints',
                "## Constraints debe contener la frase 'PARAR y reportar si'"))

    return findings


def _collect_files(directory):
    if os.path.isdir(directory):
        return [os.path.join(directory, n)
                for n in sorted(os.listdir(directory))
                if n.lower().endswith('.md') and not n.startswith('TEMPLATE-')]
    if os.path.isfile(directory):
        return [directory]
    return None


def validate_directory(directory, repo_root=None):
    files = _collect_files(directory)
    if files is None:
        print("ERROR: no existe el directorio o archivo: {}".format(directory))
        return [Finding(directory, 'IO', 'directorio/archivo inexistente')]

    if not files:
        print("INFO: no se encontraron archivos *.md en {}".format(directory))
        return []

    if repo_root is None:
        repo_root = '.'

    all_findings = []
    for path in files:
        all_findings.extend(validate_file(path, repo_root=repo_root))
    return all_findings


def main(argv):
    # Parsear argumentos: [--hash RUTA] | [--repo-root DIR] [directorio]
    repo_root = None
    directory = 'knowledge/contracts'
    hash_mode = False
    hash_path = None

    i = 1
    while i < len(argv):
        if argv[i] == '--hash' and i + 1 < len(argv):
            hash_mode = True
            hash_path = argv[i + 1]
            i += 2
        elif argv[i] == '--repo-root' and i + 1 < len(argv):
            repo_root = argv[i + 1]
            i += 2
        elif not argv[i].startswith('-'):
            directory = argv[i]
            i += 1
        else:
            i += 1

    # Modo --hash: imprimir SHA256 y salir
    if hash_mode:
        if not hash_path:
            print("ERROR: --hash requiere una ruta de archivo")
            return 1
        hash_val = _calculate_tests_hash(hash_path)
        if hash_val is None:
            print("ERROR: no se pudo leer el archivo: {}".format(hash_path))
            return 1
        print(hash_val)
        return 0

    # Modo validación normal
    files = _collect_files(directory)
    if files is None:
        print("ERROR: no existe el directorio o archivo: {}".format(directory))
        return 1
    findings = validate_directory(directory, repo_root=repo_root)
    n_files = len(files)

    errors = [f for f in findings if f.level == 'ERROR']
    warnings = [f for f in findings if f.level == 'WARNING']

    if findings:
        for f in findings:
            print(f)
    else:
        print("OK: todos los contratos son validos")

    print("\nResumen: {} error(es), {} warning(s) en {} archivo(s)"
          .format(len(errors), len(warnings), n_files))

    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))