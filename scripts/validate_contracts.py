#!/usr/bin/env python3
"""Validador determinista de contratos de tarea KDD (OKF + CCDD).

Sin LLM, sin red. Solo stdlib. Recibe un directorio (default:
knowledge/contracts) y valida cada *.md:

  (a) frontmatter YAML parseable delimitado por '---'
  (b) claves requeridas: type == 'Task Contract', task, intent, target,
      signature, test_command, budget, tests, deps_allowed
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
    'test_command', 'budget', 'tests', 'deps_allowed',
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


def validate_file(path):
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
                if n.lower().endswith('.md')]
    if os.path.isfile(directory):
        return [directory]
    return None


def validate_directory(directory):
    files = _collect_files(directory)
    if files is None:
        print("ERROR: no existe el directorio o archivo: {}".format(directory))
        return [Finding(directory, 'IO', 'directorio/archivo inexistente')]

    if not files:
        print("INFO: no se encontraron archivos *.md en {}".format(directory))
        return []

    all_findings = []
    for path in files:
        all_findings.extend(validate_file(path))
    return all_findings


def main(argv):
    directory = argv[1] if len(argv) > 1 else 'knowledge/contracts'
    files = _collect_files(directory)
    if files is None:
        print("ERROR: no existe el directorio o archivo: {}".format(directory))
        return 1
    findings = validate_directory(directory)
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