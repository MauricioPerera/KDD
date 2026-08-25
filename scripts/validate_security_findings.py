#!/usr/bin/env python3
"""validate_security_findings.py -- Capa 3 (Seguridad) de KDD, capa OPCIONAL.

Valida un `findings.json` YA SELLADO (por
scripts/vendor/codex-security/finalize_scan_contract.py) contra la politica
declarativa de examples/rules/security-findings.rules.json, via el mismo
rule_engine.evaluate que gobierna los demas dominios de reglas de este repo.

NO revalida el JSON Schema de codex-security (eso ya lo hizo el finalizer al
sellar). Este script solo aplana el findings.json sellado a la forma
{findings: [...]} que consume el rule-set y corre el motor. Sin LLM, sin red,
solo stdlib.

Capa opcional (mismo patron que validate_diagrams.py/validate_ux_page.py):
si <scan_dir>/findings.json no existe, se reporta INFO y exit 0 -- un fork sin
capa de seguridad configurada queda verde sin editar nada.

Uso:
    python scripts/validate_security_findings.py [scan_dir]

[scan_dir] default: 'security/scan'. exit 0 sin violaciones (o capa ausente),
1 con >=1 violacion, 2 solo si el archivo existe pero esta corrupto/no sellado
(error real de datos, no ausencia).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rule_engine

_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "examples", "rules", "security-findings.rules.json",
)
_DEFAULT_SCAN_DIR = "security/scan"


def flatten(findings_doc: dict) -> dict:
    """Aplana un findings.json sellado a la forma {findings: [...]} del rule-set.

    Cada finding se reduce a los campos que la politica audita: identidad,
    severidad, confianza, cantidad de CWE y longitud de la remediacion. No se
    reinterpreta el contenido -- valores ausentes se aplanan a 0/None y el
    rule engine los trata como violaciones de 'required'/'bounds' segun
    corresponda."""
    flat = []
    for finding in findings_doc.get("findings", []) or []:
        cwe = ((finding.get("taxonomy") or {}).get("cwe")) or []
        remediation = finding.get("remediation") or ""
        flat.append({
            "findingId": finding.get("findingId"),
            "severityLevel": (finding.get("severity") or {}).get("level"),
            "confidenceLevel": (finding.get("confidence") or {}).get("level"),
            "cweCount": len(cwe) if isinstance(cwe, list) else 0,
            "remediationLength": len(remediation) if isinstance(remediation, str) else 0,
        })
    return {"findings": flat}


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if len(args) > 1:
        print("Uso: validate_security_findings.py [scan_dir]", file=sys.stderr)
        return 2
    scan_dir = args[0] if args else _DEFAULT_SCAN_DIR

    findings_path = os.path.join(scan_dir, "findings.json")
    if not os.path.isfile(findings_path):
        print(f"INFO [PATH_MISSING] {findings_path}: no existe (capa opcional, sin findings que auditar)")
        return 0

    try:
        with open(findings_path, "r", encoding="utf-8") as fh:
            findings_doc = json.load(fh)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR [PARSE_ERROR] {findings_path}: JSON invalido/corrupto -- "
            f"no se pudo parsear el artefacto sellado ({exc})",
            file=sys.stderr,
        )
        return 2
    if findings_doc.get("documentType") != "codex-security.findings":
        print(
            f"ERROR [DOCUMENT_TYPE] {findings_path}: documentType inesperado -- "
            "no parece un artefacto sellado por finalize_scan_contract.py",
            file=sys.stderr,
        )
        return 2

    if not os.path.isfile(_RULES_PATH):
        print(f"ERROR [RULES_MISSING] rule-set no encontrado: {_RULES_PATH}", file=sys.stderr)
        return 2
    with open(_RULES_PATH, "r", encoding="utf-8") as fh:
        ruleset = json.load(fh)

    record = flatten(findings_doc)
    violations = rule_engine.evaluate(ruleset, record, refs={})

    if violations:
        print(f"FAIL: {len(violations)} violacion(es) de politica de seguridad")
        for violation in violations:
            print(" -", violation)
        return 1

    print(
        f"OK: {findings_path} conforme a la politica de seguridad "
        f"({len(record['findings'])} finding(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
