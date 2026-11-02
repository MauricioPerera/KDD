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
from pathlib import Path
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

def _tokens(text, chars_per_token=4):
    """1 token ≈ chars_per_token chars (ceil). Default 4."""
    return math.ceil(len(text) / chars_per_token)


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


def _integer(value, minimum=None):
    return (isinstance(value, int) and not isinstance(value, bool)
            and (minimum is None or value >= minimum))


def _validate_budget(budget):
    if not isinstance(budget, dict):
        raise ValueError("budget ausente o no es objeto")
    if not _integer(budget.get('max_tokens'), 1):
        raise ValueError("budget.max_tokens debe ser entero positivo")
    if not _integer(budget.get('output_reserve'), 0):
        raise ValueError("budget.output_reserve debe ser entero >= 0")
    if budget['max_tokens'] - budget['output_reserve'] <= 0:
        raise ValueError("budget: max_tokens - output_reserve debe ser > 0")
    if 'chars_per_token' in budget and not _integer(budget['chars_per_token'], 1):
        raise ValueError("budget.chars_per_token debe ser entero >= 1")


def _validate_slot_core(slot):
    if not isinstance(slot, dict):
        raise ValueError("slot debe ser objeto")
    if 'id' not in slot or not slot['id']:
        raise ValueError("slot sin id (o id vacio)")
    if 'source' not in slot:
        raise ValueError("slot {} sin source".format(slot['id']))
    if not _integer(slot.get('priority')):
        raise ValueError("slot {} requiere priority entera".format(slot['id']))
    if slot.get('compaction', 'none') not in _COMPACTIONS:
        raise ValueError("slot {} compaction invalida: {!r}".format(
            slot['id'], slot['compaction']))


def _validate_slot_source(slot):
    if slot['source'] not in _SOURCES:
        raise ValueError("slot {} source invalido: {!r}".format(slot['id'], slot['source']))
    if slot['source'] == 'static':
        if not slot.get('path'):
            raise ValueError("slot static {} requiere path".format(slot['id']))
        if not isinstance(slot['path'], (str, os.PathLike)):
            raise ValueError("slot static path debe ser texto o PathLike")
    if slot['source'] == 'dynamic' and slot.get('provider') not in _PROVIDERS:
        raise ValueError("slot dynamic {} provider invalido: {!r}".format(
            slot['id'], slot.get('provider')))


def _validate_slot_limits(slot):
    for key in ('max_tokens', 'min_tokens'):
        if key in slot and not _integer(slot[key], 0):
            raise ValueError("slot {} {} debe ser entero >= 0".format(slot['id'], key))
    if 'required' in slot and type(slot['required']) is not bool:
        raise ValueError('slot required debe ser booleano')
    if 'expected_sha256' in slot:
        value = slot['expected_sha256']
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('expected_sha256 requiere SHA256 completo canonico')
        if slot['source'] != 'static':
            raise ValueError('expected_sha256 solo soporta fuentes static')


def _validate_contract(contract):
    """Validate all inputs before reading context sources."""
    if not isinstance(contract, dict):
        raise ValueError("contract debe ser un objeto (dict)")
    _validate_budget(contract.get('budget'))
    slots = contract.get('slots')
    if not isinstance(slots, list) or not slots:
        raise ValueError("slots debe ser lista no vacia")
    seen = set()
    for slot in slots:
        _validate_slot_core(slot)
        if slot['id'] in seen:
            raise ValueError("id de slot duplicado: {}".format(slot['id']))
        seen.add(slot['id'])
        _validate_slot_source(slot)
        _validate_slot_limits(slot)


# ---------------------------------------------------------------------------
# Compaction (determinista, sin LLM)
# ---------------------------------------------------------------------------

_TRUNC_MARKER = " [...truncated]"
_SUMM_MARKER = " [...summarized]"


def _compact(content, cap, mode, chars_per_token=4):
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
    max_chars = cap * chars_per_token
    if len(content) <= max_chars:
        return content  # cabe sin recortar
    room = max_chars - len(marker)
    if room <= 0:
        # cap tan chico que solo entra el marcador (o ni eso)
        return marker[:max_chars]
    return content[:room] + marker


def _lf_digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


def _text_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _source_record(path, text, raw, native=None):
    return {'path': path, 'git_commit': None,
            'source_sha256': _lf_digest(text.encode('utf-8')),
            'source_hash_method': 'sha256-utf8-lf',
            'raw_sha256': hashlib.sha256(raw).hexdigest() if raw is not None else None,
            'source_stable': True, '_text': text, '_native_path': native, '_span': None}


def _current_raw(path):
    try:
        return path.read_bytes()
    except OSError:
        return None


def _raw_matches(raw, digest):
    return raw is not None and _lf_digest(raw) == digest


def _file_source(base_dir, relative):
    path = Path(os.path.join(base_dir, relative))
    before = path.read_bytes()
    text = _read_file(base_dir, relative)
    after = _current_raw(path)
    digest = _lf_digest(text.encode('utf-8'))
    paired = before if _raw_matches(before, digest) else after if _raw_matches(after, digest) else None
    source = _source_record(os.fspath(relative).replace(os.sep, '/'), text, paired, path)
    source['source_stable'] = before == after and paired is not None
    return source


def _missing_source(base_dir, relative, error):
    path = Path(os.path.join(base_dir, relative)) if relative is not None else None
    name = os.fspath(relative).replace(os.sep, '/') if relative is not None else None
    source = _source_record(name, '', None, path)
    source.update(source_sha256=None, source_stable=False, error=str(error))
    return source


def _node_content(base_dir, relative, catalog):
    if catalog is None:
        return _read_file(base_dir, relative)
    try:
        source = _file_source(base_dir, relative)
        catalog[relative] = source
        return source['_text']
    except (OSError, UnicodeError) as error:
        catalog[relative] = _missing_source(base_dir, relative, error)
        error.context_source = catalog[relative]
        raise


def _fit_content(text, cap, mode, chars_per_token):
    if _tokens(text, chars_per_token) <= cap:
        return text
    if cap > 0 and mode != 'none':
        return _compact(text, cap, mode, chars_per_token)
    return None


def _node_id(source):
    return os.path.splitext(os.path.basename(source['path']))[0]


def _pack_nodes(sources, options):
    parts, used, length, cut, omitted, stopped = [], 0, 0, None, [], False
    for source in sources:
        separator = _tokens('\n\n', options['chars_per_token']) if parts else 0
        remaining = options['cap'] - used - separator
        content = None if stopped else _fit_content(source['_text'], remaining,
            options['compaction'], options['chars_per_token'])
        if content is None:
            omitted.append(_node_id(source))
            stopped = True
            continue
        start = length + (2 if parts else 0)
        source['_span'] = [start, start + len(content)]
        length = start + len(content)
        parts.append(content)
        used += separator + _tokens(content, options['chars_per_token'])
        if content != source['_text']:
            cut, stopped = _node_id(source), True
    return {'raw': '\n\n'.join(parts), 'sources': sources, 'cut': cut,
            'omitted_nodes': omitted if omitted else None}


# ---------------------------------------------------------------------------
# Helpers: per-node cutting para okf_nodes
# ---------------------------------------------------------------------------

def _assemble_okf_nodes(base_dir, task, cap, comp, chars_per_token):
    """Ensambla okf_nodes con ranking y corte por nodo.

    El corte por nodo aplica SIEMPRE (tambien en el fallback sin matches):
    cuando todo cabe, el resultado es la misma concatenacion separada por
    linea en blanco que el comportamiento previo (byte-identico); cuando no
    cabe, el primero que no entra se compacta (marcador incluido) y el resto
    se omite.

    Retorna dict con:
      - raw: contenido concatenado incluido (ya <= cap)
      - selected: lista alfabetica de TODOS los ids recuperados por el
        retriever (compat con el reporte previo, redundante a proposito);
        cut/omitted_nodes declaran aparte que le paso a cada parte
      - cut: id compactado (o None)
      - omitted_nodes: lista de ids omitidos (o None)
    """
    catalog = {}
    scored_rels, ids = _retrieve_okf_nodes(base_dir, task, catalog)
    sources = [catalog[relative] for _, _, relative in scored_rels]
    result = _pack_nodes(sources, {'cap': cap, 'compaction': comp, 'chars_per_token': chars_per_token})
    result['selected'] = sorted(ids)
    result['read_errors'] = [source for source in catalog.values() if 'error' in source]
    return result


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


def _retrieve_okf_nodes(base_dir, task, catalog=None):
    """Retriever con ranking determinista.

    Calcula score por nodo: mencionar el nombre de archivo (sin .md) en la
    tarea cuenta 2 puntos; cada tag del frontmatter que matchea como palabra
    en la tarea cuenta 1. Ordena por score descendente, empate por nombre
    alfabetico. Sin matches -> todos con score 0 (fallback, orden alfabetico).
    Retorna (scored_rels, ids) donde scored_rels es lista de (score, name, rel).
    """
    task_lower = task.lower()
    nodes = _list_okf_nodes(base_dir)
    scored_nodes = []  # (score, name, rel)

    for rel in nodes:
        name = os.path.splitext(os.path.basename(rel))[0]
        try:
            content = _node_content(base_dir, rel, catalog)
        except OSError:
            continue
        tags = _parse_tags(content)
        score = 0

        # File name mention: 2 points
        if name and name.lower() in task_lower:
            score += 2

        # Each matching tag: 1 point
        for tag in tags:
            if tag and re.search(r"\b" + re.escape(tag) + r"\b",
                                task, re.IGNORECASE):
                score += 1

        # Record: (score, name, rel)
        scored_nodes.append((score, name, rel))

    # Classify: matched (score > 0) vs fallback (score == 0)
    matched = [n for n in scored_nodes if n[0] > 0]
    fallback = [n for n in scored_nodes if n[0] == 0]

    # Sort matched by score desc, then by name asc
    matched.sort(key=lambda n: (-n[0], n[1]))
    # Sort fallback alphabetically
    fallback.sort(key=lambda n: n[1])

    # Si hay matches, devuelve solo matched (compat con viejo behavior)
    # Si no hay matches, devuelve todos (fallback, alfabetico)
    if matched:
        selected = matched
    else:
        selected = fallback

    return selected, [os.path.splitext(os.path.basename(r))[0]
                      for _, _, r in selected]


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

def _single_source(source):
    source['_span'] = [0, len(source['_text'])]
    return {'raw': source['_text'], 'sources': [source]}


def _provider(state, slot, cap):
    if slot['source'] == 'runtime':
        return _single_source(_source_record(None, state['task'], None))
    if slot['source'] == 'static':
        return _single_source(_file_source(state['base_dir'], slot['path']))
    if slot['provider'] == 'okf_index':
        return _single_source(_file_source(state['base_dir'], 'knowledge/index.md'))
    return _assemble_okf_nodes(state['base_dir'], state['task'], cap,
                              slot.get('compaction', 'none'), state['chars_per_token'])


def _source_for_slot(state, slot, cap):
    try:
        return _provider(state, slot, cap)
    except (OSError, UnicodeError) as error:
        if not slot.get('required') and 'expected_sha256' not in slot:
            if isinstance(error, OSError):
                raise OSError('slot {} no se pudo leer: {}'.format(slot['id'], error)) from error
            raise
        relative = slot.get('path') if slot['source'] == 'static' else 'knowledge/index.md'
        source = getattr(error, 'context_source', None)
        if source is None:
            source = _missing_source(state['base_dir'], relative, error)
        return {'raw': '', 'sources': [source], 'unreadable': True}


def _slot_report(slot, data):
    report = {'id': slot['id'], 'priority': slot['priority'], 'status': 'omitted',
              'tokens': 0, 'compaction': slot.get('compaction', 'none')}
    for key in ('selected', 'cut', 'omitted_nodes'):
        if key in data and data[key] is not None:
            report[key] = data[key]
    return report


def _slot_content(state, slot, data, cap):
    if cap <= 0 or cap < slot.get('min_tokens', 0) or data.get('unreadable'):
        return None
    return _fit_content(data['raw'], cap, slot.get('compaction', 'none'), state['chars_per_token'])


def _include_slot(state, slot, report, content):
    if content is None:
        return None
    header = '### slot: {}\n'.format(slot['id'])
    start = state['context_length'] + (2 if state['sections'] else 0) + len(header)
    state['context_length'] = start + len(content)
    state['sections'].append(header + content)
    report.update(status='included', tokens=_tokens(content, state['chars_per_token']))
    if slot.get('sign'):
        report['sign'] = _sha12(content)
    state['used'] += report['tokens']
    return start


def _delivered_span(local, content, start):
    if local is None or start is None:
        return None
    left, right = local
    if left >= len(content) and right > left:
        return None
    return [start + min(left, len(content)), start + min(right, len(content))]


def _source_view(source, slot, start, content):
    row = dict(source)
    row.update(slot=slot['id'], origin=slot['source'],
               _required=slot.get('required', False), _expected=slot.get('expected_sha256'),
               delivered_span=_delivered_span(source['_span'], content, start))
    return row


def _finding(state, message, abort):
    state['findings'].append(message)
    if abort:
        state['aborts'].append(message)


def _consume_slot(state, slot):
    cap = min(slot.get('max_tokens', state['available']), state['available'] - state['used'])
    data = _source_for_slot(state, slot, cap)
    report = _slot_report(slot, data)
    content = _slot_content(state, slot, data, cap)
    start = _include_slot(state, slot, report, content)
    sources = data['sources'] + (data.get('read_errors', []) if slot.get('required') else [])
    state['sources'].extend(_source_view(source, slot, start, content) for source in sources)
    if slot.get('required') and not sources:
        _finding(state, 'CONTEXT_REQUIRED: slot {} sin fuentes seleccionadas'.format(slot['id']), True)
    state['reports'].append(report)


def _finish_delivery(context, source):
    span = source['delivered_span']
    source['status'], source['delivered_sha256'] = 'omitted', None
    if span is not None:
        fragment = context[span[0]:span[1]]
        source['status'] = 'full' if fragment == source['_text'] else 'truncated'
        source['delivered_sha256'] = _text_digest(fragment)


def _refresh_source(source):
    path = source['_native_path']
    if path is not None:
        current = _current_raw(path)
        digest = hashlib.sha256(current).hexdigest() if current is not None else None
        source['source_stable'] = source['source_stable'] and digest == source['raw_sha256']


def _unstable_paths(sources):
    versions, unstable = {}, set()
    for source in sources:
        if source['_native_path'] is None:
            continue
        path = os.path.normcase(os.path.abspath(source['_native_path']))
        if not source['source_stable'] or (path in versions and versions[path] != source['raw_sha256']):
            unstable.add(path)
        versions[path] = source['raw_sha256']
    return unstable


def _source_requirement(state, source):
    label = '{} ({})'.format(source['slot'], source['path'])
    if source['_required'] and source['status'] != 'full':
        _finding(state, 'CONTEXT_REQUIRED: entrega incompleta de ' + label, True)
    if source['_expected'] is not None and source['source_sha256'] != source['_expected']:
        _finding(state, 'CONTEXT_REQUIRED: version distinta de ' + label, True)
    if not source['source_stable']:
        required = source['_required'] or source['_expected'] is not None
        rule = 'CONTEXT_REQUIRED' if required else 'CONTEXT_CHANGED'
        _finding(state, rule + ': fuente no estable ' + label, required)


def _finish_sources(state):
    state['context'] = '\n\n'.join(state['sections'])
    for source in state['sources']:
        _finish_delivery(state['context'], source)
        _refresh_source(source)
    unstable = _unstable_paths(state['sources'])
    for source in state['sources']:
        if source['_native_path'] is not None:
            path = os.path.normcase(os.path.abspath(source['_native_path']))
            source['source_stable'] = source['source_stable'] and path not in unstable
        _source_requirement(state, source)


def _apply_regex(state, config):
    patterns = config.get('patterns', [])
    hit = _regex_deny(state['context'], patterns) if patterns else None
    if hit is not None:
        _finding(state, 'regex_deny: patron matcheado: {!r}'.format(hit),
                 config.get('on_fail', 'abort') == 'abort')


def _apply_guardrails(state, config):
    state['configured'] = [name for name in ('regex_deny', 'reference_check')
                           if config.get(name) is not None]
    if config.get('reference_check') is not None:
        for finding in _reference_check(state['base_dir'], state['task']):
            _finding(state, 'reference_check: ' + finding, False)
    if config.get('regex_deny') is not None:
        _apply_regex(state, config['regex_deny'])


def _build_result(state):
    sources = [{key: value for key, value in row.items() if not key.startswith('_')}
               for row in state['sources']]
    return {'slots': state['reports'], 'context': state['context'], 'used': state['used'],
            'available': state['available'], 'max_tokens': state['budget']['max_tokens'],
            'output_reserve': state['budget']['output_reserve'],
            'guardrails': {'ok': not state['findings'] and not state['aborts'],
                          'findings': state['findings'], 'abort': bool(state['aborts']),
                          'configured': state['configured']},
            'manifest': {'schema_version': 1, 'context_sha256': _text_digest(state['context']),
                         'sources': sources}}


def assemble(contract, task, base_dir):
    """Return budgeted context, source identities and actual delivered character spans.

    Required inputs fail closed with a partial receipt. Filesystem identities
    describe observed reads; they do not attest a Git commit or model comprehension.
    """
    _validate_contract(contract)
    budget = contract['budget']
    state = {'task': task, 'base_dir': base_dir, 'budget': budget,
             'available': budget['max_tokens'] - budget['output_reserve'],
             'chars_per_token': budget.get('chars_per_token', 4), 'used': 0,
             'reports': [], 'sections': [], 'context_length': 0, 'sources': [],
             'findings': [], 'aborts': [], 'configured': []}
    slots = sorted(enumerate(contract['slots']), key=lambda item: (item[1]['priority'], item[0]))
    for _, slot in slots:
        _consume_slot(state, slot)
    _finish_sources(state)
    _apply_guardrails(state, contract.get('guardrails', {}) or {})
    result = _build_result(state)
    if state['aborts']:
        raise GuardrailAbort(result, state['aborts'][0])
    return result


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
    if "cut" in s:
        line += "  cut=" + s["cut"]
    if "omitted_nodes" in s:
        line += "  omitted=[" + ",".join(s["omitted_nodes"]) + "]"
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
    lines.append('CONTEXT_MANIFEST ' + json.dumps(result['manifest'], ensure_ascii=True, sort_keys=True))
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
