#!/usr/bin/env python3
"""Validador determinista de contratos de ejecucion (specs/CONTRACT-*.md).

Sin LLM, sin red, sin subprocess. Solo stdlib. Recibe el directorio de specs
(default: specs) y valida cada CONTRACT-*.md con estas reglas deterministas:

  CERRADO vs ABIERTO: un contrato esta CERRADO si existe
       docs/reports/CONTRACT-NN-REPORT.md (junto al padre del directorio de specs)
       con su mismo prefijo CONTRACT-NN; si no, esta ABIERTO.
       TEMPLATE-*.md se ignora (no es un contrato).

  Reglas para TODO contrato (abierto o cerrado):
  - Seccion `## Criterios de aceptacion` presente, con al menos una linea
    checkbox (`- [ ]` o `- [x]`) que contenga un comando entre backticks.
  - Seccion `## Restricciones` presente.

  Reglas SOLO para contratos ABIERTOS:
  - `Tocar SOLO` presente (como texto) dentro de la seccion Restricciones.
  - Bullet `ABORTAR SI` presente: una linea que empieza con `- ABORTAR SI`.
    Su texto (incluidas sus lineas de continuation indentadas hasta el
    siguiente bullet o seccion) NO debe contener los caracteres `<` ni `>`
    (placeholders del template).

  exit 0 si no hay errores, 1 si hay >=1 error.

Uso:
    python scripts/validate_specs.py [specs_dir]
"""

import os
import re
import sys


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CRITERIOS_SECTION = 'Criterios de aceptación'
RESTRICCIONES_SECTION = 'Restricciones'

# CONTRACT-NN -> prefix = 'CONTRACT-NN'
_PREFIX_RE = re.compile(r'^(CONTRACT-\d+)')
# Archivos de contrato: CONTRACT-*.md (TEMPLATE-*.md queda fuera por el
# prefijo).
_CONTRACT_FILE_RE = re.compile(r'^CONTRACT-\d+.*\.md$')
# Checkbox con un comando entre backticks (`...` con contenido no vacio).
_CHECKBOX_CMD_RE = re.compile(r'^\s*-\s*\[[ xX]\]\s.*`[^`\n]+`')
# Bullet ABORTAR SI.
_ABORTAR_RE = re.compile(r'^(\s*)-\s+ABORTAR SI\b')
# Cualquier bullet.
_BULLET_RE = re.compile(r'^\s*-\s+')
# Cualquier header markdown.
_HEADER_RE = re.compile(r'^#{1,6}\s')


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(file, rule, msg, level='ERROR'):
    return {'file': file, 'level': level, 'rule': rule, 'msg': msg}


# ---------------------------------------------------------------------------
# Helpers de parseo
# ---------------------------------------------------------------------------

def _extract_sections(text):
    """Devuelve dict nombre_seccion -> texto_de_la_seccion (sin header)."""
    sections = {}
    current = None
    buf = []
    for line in text.splitlines():
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


def _prefix_of(filename):
    """Extrae el prefijo CONTRACT-NN de un nombre de archivo, o None."""
    m = _PREFIX_RE.match(filename)
    return m.group(1) if m else None


def _abortar_text(lines, idx):
    """Texto del bullet ABORTAR SI en `lines[idx]` + sus continuation lines.

    Continua recogiendo hasta el siguiente bullet (cualquier indent) o
    seccion (header markdown) o fin de la seccion.
    """
    collected = [lines[idx]]
    j = idx + 1
    while j < len(lines):
        ln = lines[j]
        if _HEADER_RE.match(ln):
            break
        if _BULLET_RE.match(ln):
            break
        collected.append(ln)
        j += 1
    return '\n'.join(collected)


# ---------------------------------------------------------------------------
# Validacion por archivo
# ---------------------------------------------------------------------------

def _rel(path, base):
    """Ruta relativa a `base` con separadores '/' (estable/portable)."""
    return os.path.relpath(path, base).replace(os.sep, '/')


def _reports_dir(specs_abs):
    """Directorio de reportes: <padre de specs>/docs/reports."""
    return os.path.join(os.path.dirname(specs_abs), 'docs', 'reports')


def validate_file(file_rel, text, is_closed):
    """Devuelve lista de findings para un contrato.

    `is_closed` True si el contrato esta cerrado (tiene reporte).
    """
    findings = []
    sections = _extract_sections(text)

    # Regla comun: Criterios de aceptacion presente con checkbox+backtick.
    crit = sections.get(CRITERIOS_SECTION)
    if crit is None:
        findings.append(_finding(
            file_rel, 'SEC_CRITERIOS',
            "seccion obligatoria ausente: ## {}".format(CRITERIOS_SECTION)))
    else:
        has_cmd = False
        for line in crit.splitlines():
            if _CHECKBOX_CMD_RE.match(line):
                has_cmd = True
                break
        if not has_cmd:
            findings.append(_finding(
                file_rel, 'SEC_CRITERIOS',
                "## {} requiere >=1 checkbox con un comando entre backticks"
                .format(CRITERIOS_SECTION)))

    # Regla comun: Restricciones presente.
    restr = sections.get(RESTRICCIONES_SECTION)
    if restr is None:
        findings.append(_finding(
            file_rel, 'SEC_RESTRICCIONES',
            "seccion obligatoria ausente: ## {}".format(RESTRICCIONES_SECTION)))

    # Reglas solo para abiertos.
    if not is_closed:
        if restr is not None:
            if 'Tocar SOLO' not in restr:
                findings.append(_finding(
                    file_rel, 'TOCAR_SOLO',
                    "contrato abierto sin 'Tocar SOLO' en Restricciones"))
            restr_lines = restr.splitlines()
            abortar_idx = None
            for i, ln in enumerate(restr_lines):
                if _ABORTAR_RE.match(ln):
                    abortar_idx = i
                    break
            if abortar_idx is None:
                findings.append(_finding(
                    file_rel, 'ABORTAR',
                    "contrato abierto sin bullet 'ABORTAR SI' en Restricciones"))
            else:
                abortar_text = _abortar_text(restr_lines, abortar_idx)
                if '<' in abortar_text or '>' in abortar_text:
                    findings.append(_finding(
                        file_rel, 'ABORTAR',
                        "el bullet 'ABORTAR SI' contiene placeholders con "
                        "caracteres de angulo ('<' o '>')"))

    return findings


def validate_specs(specs_dir):
    """Valida todos los CONTRACT-*.md bajo specs_dir.

    Devuelve lista de findings [{'file','level','rule','msg'}], ordenados por
    archivo y luego regla. Vacia si todos los contratos son conformes.
    """
    specs_abs = os.path.abspath(specs_dir)
    findings = []

    if not os.path.isdir(specs_abs):
        findings.append(_finding(specs_dir, 'IO',
                                'directorio inexistente: {}'.format(specs_dir)))
        return findings

    reports_dir = _reports_dir(specs_abs)
    repo_root = os.path.dirname(specs_abs)

    files = []
    for name in sorted(os.listdir(specs_abs)):
        if _CONTRACT_FILE_RE.match(name):
            files.append(os.path.join(specs_abs, name))

    for path in files:
        file_rel = _rel(path, repo_root)
        prefix = _prefix_of(os.path.basename(path))
        is_closed = (prefix is not None
                     and os.path.isfile(os.path.join(reports_dir,
                                                     prefix + '-REPORT.md')))
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
        except OSError as e:
            findings.append(_finding(file_rel, 'IO',
                                    'no se pudo leer: {}'.format(e)))
            continue
        findings.extend(validate_file(file_rel, text, is_closed))

    findings.sort(key=lambda f: (f['file'], f['rule'], f.get('level', '')))
    return findings


# ---------------------------------------------------------------------------
# CLI (espejo del estilo de scripts/validate_okf.py)
# ---------------------------------------------------------------------------

def main(argv):
    specs_dir = argv[1] if len(argv) > 1 else 'specs'
    specs_abs = os.path.abspath(specs_dir)
    if not os.path.isdir(specs_abs):
        print("ERROR: no existe el directorio: {}".format(specs_dir))
        return 1

    files = [n for n in sorted(os.listdir(specs_abs))
             if _CONTRACT_FILE_RE.match(n)]
    findings = validate_specs(specs_dir)

    errors = [f for f in findings if f['level'] == 'ERROR']

    if findings:
        for f in findings:
            print("{} [{}] {}: {}".format(
                f['level'], f['rule'], f['file'], f['msg']))
    else:
        print("OK: todos los contratos de specs son validos")

    print("\nResumen: {} error(es) en {} archivo(s)"
          .format(len(errors), len(files)))

    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))