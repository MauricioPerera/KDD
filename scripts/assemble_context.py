#!/usr/bin/env python3
"""Ensamblador de contexto CCDD Nivel 2 (KDD).

Determinista, sin LLM, sin red, sin subprocess. Solo stdlib. Dado un contrato
JSON de slots y una tarea, produce contexto presupuestado, firmado y auditado
desde la KB OKF de ``knowledge/``.

Heuristica de tokens: 1 token ≈ 4 chars (``ceil(len/4)``), documentada en el
task contract ``knowledge/contracts/assemble-context.md``.

Uso:
    python scripts/assemble_context.py <contract.json> "<tarea>" [-v]

Exit codes: 0 ok · 2 contrato invalido o guardrail abort · 1 I/O.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class GuardrailAbort(Exception):
    """Guardrail con on_fail=abort. Lleva el result parcial para reportar."""

    def __init__(self, result, finding):
        super().__init__(finding)
        self.result = result
        self.finding = finding


# ---------------------------------------------------------------------------
# Helpers deterministicos
# ---------------------------------------------------------------------------

def _tokens(text):
    """1 token ≈ 4 chars (ceil)."""
    return math.ceil(len(text) / 4)


def _sha12(text):
    """sha256 del contenido, primeros 12 hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


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
        elif ch == ",":
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    last = "".join(buf).strip()
    if last:
        items.append(last)
    return items


def _strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        return value[1:-1]
    return value


def _frontmatter_block(text):
    """Devuelve el bloque de frontmatter (entre '---') como str, o ''."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for k in range(1, len(lines)):
        if lines[k].strip() == "---":
            return "\n".join(lines[1:k])
    return ""


_TAG_RE = re.compile(r"^tags:\s*\[(.*)\]\s*$", re.MULTILINE)


def _parse_tags(text):
    """Tags del frontmatter (lista, puede ser vacia)."""
    block = _frontmatter_block(text)
    if not block:
        return []
    m = _TAG_RE.search(block)
    if not m:
        return []
    inner = m.group(1).strip()
    if not inner:
        return []
    return [_strip_quotes(x) for x in _split_inline_list(inner)]


# ---------------------------------------------------------------------------
# Validacion del contrato
# ---------------------------------------------------------------------------

_SOURCES = ("static", "dynamic", "runtime")
_PROVIDERS = ("okf_index", "okf_nodes")
_COMPACTIONS = ("none", "truncate", "summarize")


def _validate_contract(contract):
    """Lanza ValueError con causa exacta ante contrato invalido."""
    if not isinstance(contract, dict):
        raise ValueError("contract debe ser un objeto (dict)")
    budget = contract.get("budget")
    if not isinstance(budget, dict):
        raise ValueError("budget ausente o no es objeto")
    max_tokens = budget.get("max_tokens")
    output_reserve = budget.get("output_reserve")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) \
            or max_tokens <= 0:
        raise ValueError("budget.max_tokens debe ser entero positivo")
    if not isinstance(output_reserve, int) or isinstance(output_reserve, bool) \
            or output_reserve < 0:
        raise ValueError("budget.output_reserve debe ser entero >= 0")
    if max_tokens - output_reserve <= 0:
        raise ValueError(
            "budget: max_tokens - output_reserve debe ser > 0")

    slots = contract.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("slots debe ser lista no vacia")
    seen_ids = set()
    for s in slots:
        if not isinstance(s, dict):
            raise ValueError("slot debe ser objeto")
        if "id" not in s or not s["id"]:
            raise ValueError("slot sin id (o id vacio)")
        sid = s["id"]
        if sid in seen_ids:
            raise ValueError("id de slot duplicado: {}".format(sid))
        seen_ids.add(sid)
        if "source" not in s:
            raise ValueError("slot {} sin source".format(sid))
        if s["source"] not in _SOURCES:
            raise ValueError(
                "slot {} source invalido: {!r}".format(sid, s["source"]))
        if "priority" not in s or not isinstance(s["priority"], int) \
                or isinstance(s["priority"], bool):
            raise ValueError(
                "slot {} requiere priority entera".format(sid))
        if s["source"] == "static" and not s.get("path"):
            raise ValueError("slot static {} requiere path".format(sid))
        if s["source"] == "dynamic":
            if s.get("provider") not in _PROVIDERS:
                raise ValueError(
                    "slot dynamic {} provider invalido: {!r}"
                    .format(sid, s.get("provider")))
        comp = s.get("compaction", "none")
        if comp not in _COMPACTIONS:
            raise ValueError(
                "slot {} compaction invalida: {!r}".format(sid, comp))
        if "max_tokens" in s and (not isinstance(s["max_tokens"], int)
                                  or isinstance(s["max_tokens"], bool)
                                  or s["max_tokens"] < 0):
            raise ValueError(
                "slot {} max_tokens debe ser entero >= 0".format(sid))
        if "min_tokens" in s and (not isinstance(s["min_tokens"], int)
                                  or isinstance(s["min_tokens"], bool)
                                  or s["min_tokens"] < 0):
            raise ValueError(
                "slot {} min_tokens debe ser entero >= 0".format(sid))


# ---------------------------------------------------------------------------
# Compaction (determinista, sin LLM)
# ---------------------------------------------------------------------------

_TRUNC_MARKER = " [...truncated]"
_SUMM_MARKER = " [...summarized]"


def _compact(content, cap, mode):
    """Recorta content a `cap` tokens dejando un marcador.

    IMPORTANTE: ambos modos (``truncate`` y ``summarize``) son corte por
    caracteres determinista (sin LLM, sin resumen semantico). Solo difieren el
    marcador que dejan al cortar (``[...truncated]`` vs ``[...summarized]``).
    El modo ``summarize`` se mantiene aceptado por compatibilidad con la
    plantilla publicada, pero no resume: corta exactamente igual que
    ``truncate``; el nombre es historico, no descriptivo.

    `cap` >= 1 garantizado por la caller. Reserva espacio para el marcador
    para no exceder el tope de tokens.
    """
    marker = _TRUNC_MARKER if mode == "truncate" else _SUMM_MARKER
    max_chars = cap * 4
    if len(content) <= max_chars:
        return content  # cabe sin recortar
    room = max_chars - len(marker)
    if room <= 0:
        # cap tan chico que solo entra el marcador (o ni eso)
        return marker[:max_chars]
    return content[:room] + marker


# ---------------------------------------------------------------------------
# Providers / retriever
# ---------------------------------------------------------------------------

def _read_file(base_dir, rel_path):
    path = os.path.join(base_dir, rel_path)
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _list_okf_nodes(base_dir):
    """Lista de rutas relativas knowledge/**.md, orden alfabetico estable."""
    root = os.path.join(base_dir, "knowledge")
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".md"):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, base_dir).replace(os.sep, "/")
                out.append(rel)
    return sorted(out)


def _retrieve_okf_nodes(base_dir, task):
    """Retriever determinista.

    Nodo relevante si su nombre de archivo (sin .md) aparece en la tarea
    (case-insensitive, substring) o algun valor de tags del frontmatter
    aparece como palabra en la tarea. Sin matches -> todos. Orden alfabetico.
    Devuelve (lista_rutas_relativas, lista_ids).
    """
    task_lower = task.lower()
    nodes = _list_okf_nodes(base_dir)
    selected = []
    for rel in nodes:
        name = os.path.splitext(os.path.basename(rel))[0]
        try:
            content = _read_file(base_dir, rel)
        except OSError:
            continue
        tags = _parse_tags(content)
        match = False
        if name and name.lower() in task_lower:
            match = True
        if not match:
            for tag in tags:
                if tag and re.search(r"\b" + re.escape(tag) + r"\b",
                                     task, re.IGNORECASE):
                    match = True
                    break
        if match:
            selected.append(rel)
    if not selected:
        selected = nodes
    return selected, [os.path.splitext(os.path.basename(r))[0]
                      for r in selected]


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

_REF_RE = re.compile(r"knowledge/[A-Za-z0-9_./\-]+\.md")


def _reference_check(base_dir, task):
    """Rutas knowledge/...md citadas en la tarea que no existen en disco."""
    findings = []
    for m in sorted(set(_REF_RE.findall(task))):
        target = os.path.join(base_dir, m.replace("/", os.sep))
        if not os.path.exists(target):
            findings.append("{} -> no existe en disco".format(m))
    return findings


def _regex_deny(context, patterns):
    """Devuelve el primer patron que matchea, o None.

    Cada patron se evalua con ``re.search`` (stdlib re, determinista): es un
    patron regex de verdad, no un substring literal. Un patron que no compile
    lanza ``ValueError`` nombrando el patron (no silencio, no fallback a
    matching literal).
    """
    for pat in patterns:
        try:
            if re.search(pat, context):
                return pat
        except re.error as e:
            raise ValueError(
                "regex_deny: patron invalido {!r}: {}".format(pat, e)
            ) from e
    return None


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

def assemble(contract, task, base_dir):
    """Ensambla el contexto.

    Devuelve dict con: slots (lista de reportes por slot: id, priority,
    status included|omitted, tokens, compaction, sign si hay, selected si
    hay), context (str), used, available, guardrails {ok, findings}.

    Lanza ``ValueError`` ante contrato invalido. Lanza ``GuardrailAbort``
    (lleva el result parcial) si un guardrail on_fail=abort se dispara
    (regex_deny). reference_check es on_fail=report: solo agrega hallazgos.
    """
    _validate_contract(contract)
    budget = contract["budget"]
    max_tokens = budget["max_tokens"]
    output_reserve = budget["output_reserve"]
    available = max_tokens - output_reserve

    # orden estable: por priority ascendente, luego indice original
    slots = sorted(enumerate(contract["slots"]),
                   key=lambda kv: (kv[1]["priority"], kv[0]))
    slots = [kv[1] for kv in slots]

    guardrails_cfg = contract.get("guardrails", {}) or {}
    regex_cfg = guardrails_cfg.get("regex_deny")
    ref_cfg = guardrails_cfg.get("reference_check")

    # guardrails configurados, en orden fijo (regex_deny, reference_check).
    # El reporte lista SOLO estos: un guardrail ausente del contrato no se
    # menciona en el reporte.
    configured = []
    if regex_cfg is not None:
        configured.append("regex_deny")
    if ref_cfg is not None:
        configured.append("reference_check")

    used = 0
    slot_reports = []
    sections = []

    for s in slots:
        sid = s["id"]
        comp = s.get("compaction", "none")
        slot_max = s.get("max_tokens")
        min_tokens = s.get("min_tokens", 0)
        do_sign = bool(s.get("sign"))
        report = {
            "id": sid,
            "priority": s["priority"],
            "status": "omitted",
            "tokens": 0,
            "compaction": comp,
        }

        # tope de tokens para este slot
        slot_cap = slot_max if isinstance(slot_max, int) else available
        remaining = available - used
        cap = min(slot_cap, remaining)

        # obtener contenido crudo segun source
        raw = ""
        selected = None
        try:
            if s["source"] == "static":
                raw = _read_file(base_dir, s["path"])
            elif s["source"] == "dynamic":
                if s["provider"] == "okf_index":
                    raw = _read_file(base_dir, "knowledge/index.md")
                elif s["provider"] == "okf_nodes":
                    rels, ids = _retrieve_okf_nodes(base_dir, task)
                    selected = sorted(ids)
                    parts = []
                    for rel in rels:
                        parts.append(_read_file(base_dir, rel))
                    raw = "\n\n".join(parts)
            elif s["source"] == "runtime":
                raw = task
        except OSError as e:
            raise OSError("slot {} no se pudo leer: {}".format(sid, e)) \
                from e

        if selected is not None:
            report["selected"] = selected

        # decidir inclusion
        if cap <= 0:
            pass  # omitido
        elif min_tokens and cap < min_tokens:
            pass  # por debajo del piso
        else:
            raw_tokens = _tokens(raw)
            if raw_tokens <= cap:
                content = raw
            else:
                if comp == "none":
                    content = None  # no se recorta -> no cabe
                else:
                    content = _compact(raw, cap, comp)
            if content is not None:
                report["status"] = "included"
                report["tokens"] = _tokens(content)
                if do_sign:
                    report["sign"] = _sha12(content)
                used += report["tokens"]
                sections.append("### slot: {}\n{}".format(sid, content))

        slot_reports.append(report)

    # contexto final
    context = "\n\n".join(sections)

    # guardrails
    findings = []
    # reference_check (report, no aborta)
    if ref_cfg is not None:
        for f in _reference_check(base_dir, task):
            findings.append("reference_check: " + f)

    # regex_deny sobre el contexto ensamblado
    if regex_cfg is not None:
        patterns = regex_cfg.get("patterns", [])
        on_fail = regex_cfg.get("on_fail", "abort")
        hit = _regex_deny(context, patterns) if patterns else None
        if hit is not None:
            finding = "regex_deny: patron matcheado: {!r}".format(hit)
            findings.append(finding)
            if on_fail == "abort":
                result = _build_result(slot_reports, context, used, available,
                                       max_tokens, output_reserve,
                                       findings, abort=True,
                                       configured=configured)
                raise GuardrailAbort(result, finding)
            # on_fail != abort: solo reporta (no aborta)

    return _build_result(slot_reports, context, used, available,
                         max_tokens, output_reserve, findings, abort=False,
                         configured=configured)


def _build_result(slot_reports, context, used, available, max_tokens,
                  output_reserve, findings, abort, configured):
    return {
        "slots": slot_reports,
        "context": context,
        "used": used,
        "available": available,
        "max_tokens": max_tokens,
        "output_reserve": output_reserve,
        "guardrails": {
            "ok": len(findings) == 0 and not abort,
            "findings": findings,
            "abort": abort,
            "configured": configured,
        },
    }


# ---------------------------------------------------------------------------
# Reporte (determinista: sin relojes, orden fijo)
# ---------------------------------------------------------------------------

def _slot_line(s):
    line = "  [prio {:>3}] {:<14} status={:<9} tokens={:<5} compaction={}" \
        .format(s["priority"], s["id"], s["status"], s["tokens"],
                s["compaction"])
    if "sign" in s:
        line += "  sign=" + s["sign"]
    if "selected" in s:
        line += "  selected=[" + ",".join(s["selected"]) + "]"
    return line


def format_report(result, contract_path, task, verbose=False):
    lines = []
    lines.append("=== assemble context ===")
    lines.append("contract: {}".format(contract_path))
    lines.append("task: {}".format(task))
    lines.append("budget: max_tokens={} output_reserve={} available={}".format(
        result["max_tokens"], result["output_reserve"], result["available"]))
    lines.append("")
    lines.append("slots:")
    for s in result["slots"]:
        lines.append(_slot_line(s))
    lines.append("")
    lines.append("totals: used={} available={} sobrante={}".format(
        result["used"], result["available"],
        result["available"] - result["used"]))
    lines.append("")
    gr = result["guardrails"]
    if gr["ok"]:
        lines.append("guardrails: ok")
    else:
        lines.append("guardrails: findings{}".format(
            " (abort)" if gr.get("abort") else ""))
    if gr["findings"]:
        for f in gr["findings"]:
            lines.append("  - " + f)
    else:
        # Lista SOLO los guardrails configurados en el contrato/config, cada
        # uno como "name: ok". Un guardrail ausente del contrato no aparece
        # en el reporte (p.ej. sin regex_deny configurado -> la palabra
        # regex_deny no se menciona).
        for name in gr.get("configured", []):
            lines.append("  - {}: ok".format(name))
    if verbose:
        lines.append("")
        lines.append("--- context ---")
        lines.append(result["context"])
        lines.append("--- /context ---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv):
    parser = argparse.ArgumentParser(
        prog="assemble_context.py",
        description="Ensambia contexto presupuestado y determinista.",
        usage="%(prog)s <contract.json> \"<tarea>\" [-v]",
    )
    parser.add_argument("contract")
    parser.add_argument("task")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv[1:])

    try:
        with open(args.contract, "r", encoding="utf-8") as fh:
            contract = json.load(fh)
    except OSError as e:
        print("ERROR I/O: no se pudo leer el contrato: {}".format(e),
              file=sys.stderr)
        return 1
    except ValueError as e:
        print("ERROR contrato invalido (JSON): {}".format(e),
              file=sys.stderr)
        return 2

    base_dir = "."
    try:
        result = assemble(contract, args.task, base_dir)
    except GuardrailAbort as e:
        print(format_report(e.result, args.contract, args.task, args.verbose))
        print("ABORT: {}".format(e.finding), file=sys.stderr)
        return 2
    except ValueError as e:
        print("ERROR contrato invalido: {}".format(e), file=sys.stderr)
        return 2
    except OSError as e:
        print("ERROR I/O: {}".format(e), file=sys.stderr)
        return 1

    print(format_report(result, args.contract, args.task, args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))