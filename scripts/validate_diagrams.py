#!/usr/bin/env python3
"""Gate deterministico de diagramas Mermaid (Contrato: diagram-gate).

Parsers minimos en Python puro (regex) para 4 tipos de diagrama Mermaid:
flowchart/graph, gantt, pie, journey. NO usa el parser real de mermaid: eso
exigiria Node.js via subprocess, prohibido por 'forbids' en los gates Nivel 1
de este repo (ver knowledge/contracts/ux-page-gate.md). Cobertura
deliberadamente parcial — ver knowledge/diagram-contract-spec.md para el
subconjunto exacto soportado por tipo y la comparacion con el proyecto
hermano mermaid-gate (Node, parser real de mermaid, 20 tipos de diagrama,
sin la restriccion de dependencias de este repo).
"""

import datetime
import json
import os
import re
import sys


SUPPORTED_TYPES = ('flowchart', 'gantt', 'pie', 'journey')


_SHAPE = r'(\[[^\]]*\]|\{[^{}]*\}|\([^()]*\))?'
NODE_DEF = re.compile(r'^\s*(\w+)\s*' + _SHAPE + r'\s*$')
EDGE_LINE = re.compile(
    r'(\w+)\s*' + _SHAPE +
    r'\s*(?:-{1,3}|-\.-?)>?\s*(?:\|([^|]*)\|\s*)?' +
    r'(\w+)\s*' + _SHAPE
)


def _strip_shape(token):
    """Extrae el label de '[label]'/'{label}'/'(label)'; None si no hay shape."""
    if not token:
        return None
    return token[1:-1].strip()


def get_diagram_type(text):
    """Primer token no vacio/no-comentario del texto ('flowchart' o 'graph')."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('%%'):
            continue
        return stripped.split()[0]
    return None


def parse_flowchart(text):
    """Devuelve {'nodes': [{'id','label'}], 'edges': [{'from','to','label'}]}.

    Heuristica linea por linea: cada linea (salvo el header) se prueba primero
    como edge, despues como definicion de nodo suelta. No maneja subgraphs,
    estilos, ni edges multi-linea — ver knowledge/diagram-contract-spec.md.
    """
    nodes = {}
    edges = []

    def register(node_id, shape_token):
        label = _strip_shape(shape_token)
        if label is not None:
            nodes[node_id] = label
        elif node_id not in nodes:
            nodes[node_id] = node_id

    lines = text.splitlines()
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line or line.startswith('%%'):
            continue

        edge_match = EDGE_LINE.search(line)
        if edge_match:
            from_id, from_shape, label, to_id, to_shape = edge_match.groups()
            register(from_id, from_shape)
            register(to_id, to_shape)
            edges.append({
                'from': from_id,
                'to': to_id,
                'label': label.strip() if label else None,
            })
            continue

        node_match = NODE_DEF.match(line)
        if node_match:
            node_id, shape = node_match.groups()
            register(node_id, shape)

    return {
        'nodes': [{'id': nid, 'label': label} for nid, label in nodes.items()],
        'edges': edges,
    }


GANTT_TASK = re.compile(r'^([^:]+):\s*(.+)$')
GANTT_DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})$')
GANTT_DURATION = re.compile(r'^(\d+)d$')
GANTT_META_PREFIXES = ('title', 'dateformat', 'axisformat', 'excludes', 'todaymarker')


def parse_gantt(text):
    """Devuelve {'tasks': [{'id','label','section','start','end'}], 'sections': [...]}.

    Heuristica de pasada unica en orden de aparicion: 'after <id>' solo
    resuelve si <id> ya fue visto ANTES en el texto (igual que mermaid
    escribe gantt en la practica). 'start'/'end' quedan None si no se
    pueden derivar (fecha literal YYYY-MM-DD + duracion 'Nd'). No maneja
    tags de estado (active/done/crit) antes del id.
    """
    section = None
    tasks = []
    tasks_by_id = {}

    for raw_line in text.splitlines()[1:]:
        line = raw_line.strip()
        if not line or line.startswith('%%'):
            continue
        lowered = line.lower()
        if any(lowered.startswith(p) for p in GANTT_META_PREFIXES):
            continue
        if line.startswith('section '):
            section = line[len('section '):].strip()
            continue

        m = GANTT_TASK.match(line)
        if not m:
            continue
        label = m.group(1).strip()
        fields = [f.strip() for f in m.group(2).split(',')]
        if len(fields) < 3:
            continue
        task_id, start_token, duration_token = fields[-3], fields[-2], fields[-1]

        start = None
        date_match = GANTT_DATE.match(start_token)
        if date_match:
            start = date_match.group(1)
        elif start_token.startswith('after '):
            ref = tasks_by_id.get(start_token[len('after '):].strip())
            if ref and ref.get('end'):
                start = ref['end']

        end = None
        dur_match = GANTT_DURATION.match(duration_token)
        if start and dur_match:
            start_date = datetime.date.fromisoformat(start)
            end = (start_date + datetime.timedelta(days=int(dur_match.group(1)))).isoformat()

        task = {'id': task_id, 'label': label, 'section': section, 'start': start, 'end': end}
        tasks.append(task)
        tasks_by_id[task_id] = task

    sections = []
    for t in tasks:
        if t['section'] and t['section'] not in sections:
            sections.append(t['section'])

    return {'tasks': tasks, 'sections': sections}


PIE_SLICE = re.compile(r'^"([^"]+)"\s*:\s*([\d.]+)\s*$')


def parse_pie(text):
    """Devuelve {'slices': [{'label','value'}]}. Ignora 'title ...' y comentarios."""
    slices = []
    for raw_line in text.splitlines()[1:]:
        line = raw_line.strip()
        if not line or line.startswith('%%') or line.lower().startswith('title'):
            continue
        m = PIE_SLICE.match(line)
        if not m:
            continue
        value = float(m.group(2))
        if value.is_integer():
            value = int(value)
        slices.append({'label': m.group(1), 'value': value})
    return {'slices': slices}


JOURNEY_TASK = re.compile(r'^(.+?):\s*(\d+)\s*:\s*(.+)$')


def parse_journey(text):
    """Devuelve {'tasks': [{'section','task','score','people'}], 'sections': [...], 'actors': [...]}."""
    section = None
    tasks = []
    sections = []
    actors = []

    for raw_line in text.splitlines()[1:]:
        line = raw_line.strip()
        if not line or line.startswith('%%') or line.lower().startswith('title'):
            continue
        if line.startswith('section '):
            section = line[len('section '):].strip()
            if section not in sections:
                sections.append(section)
            continue

        m = JOURNEY_TASK.match(line)
        if not m:
            continue
        task_label = m.group(1).strip()
        score = int(m.group(2))
        people = [p.strip() for p in m.group(3).split(',')]
        for p in people:
            if p not in actors:
                actors.append(p)
        tasks.append({'section': section, 'task': task_label, 'score': score, 'people': people})

    return {'tasks': tasks, 'sections': sections, 'actors': actors}


def _validate_flowchart(text, contract, file_label):
    findings = []
    parsed = parse_flowchart(text)
    nodes_by_id = {n['id']: n for n in parsed['nodes']}

    min_nodes = contract.get('min_nodes')
    if isinstance(min_nodes, int) and len(parsed['nodes']) < min_nodes:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MIN_NODES',
            'msg': 'min_nodes {}, encontrado {}'.format(min_nodes, len(parsed['nodes'])),
        })

    max_nodes = contract.get('max_nodes')
    if isinstance(max_nodes, int) and len(parsed['nodes']) > max_nodes:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MAX_NODES',
            'msg': 'max_nodes {}, encontrado {}'.format(max_nodes, len(parsed['nodes'])),
        })

    for req in contract.get('required_nodes', []):
        found = nodes_by_id.get(req.get('id'))
        if not found:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_NODE',
                'msg': "falta nodo requerido '{}'".format(req.get('id')),
            })
            continue
        if req.get('label') and found.get('label') != req.get('label'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'NODE_LABEL_MISMATCH',
                'msg': "nodo '{}' esperaba label '{}', encontrado '{}'".format(
                    req.get('id'), req.get('label'), found.get('label')),
            })

    for req in contract.get('required_edges', []):
        match = None
        for e in parsed['edges']:
            if e['from'] != req.get('from') or e['to'] != req.get('to'):
                continue
            if req.get('label') and e.get('label') != req.get('label'):
                continue
            match = e
            break
        if not match:
            label_part = " con label '{}'".format(req['label']) if req.get('label') else ''
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_EDGE',
                'msg': "falta edge requerido '{}' -> '{}'{}".format(
                    req.get('from'), req.get('to'), label_part),
            })

    return findings


def _validate_gantt(text, contract, file_label):
    findings = []
    parsed = parse_gantt(text)
    tasks_by_id = {t['id']: t for t in parsed['tasks']}

    min_tasks = contract.get('min_tasks')
    if isinstance(min_tasks, int) and len(parsed['tasks']) < min_tasks:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MIN_TASKS',
            'msg': 'min_tasks {}, encontrado {}'.format(min_tasks, len(parsed['tasks'])),
        })

    max_tasks = contract.get('max_tasks')
    if isinstance(max_tasks, int) and len(parsed['tasks']) > max_tasks:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MAX_TASKS',
            'msg': 'max_tasks {}, encontrado {}'.format(max_tasks, len(parsed['tasks'])),
        })

    for section in contract.get('required_sections', []):
        if section not in parsed['sections']:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_SECTION',
                'msg': "falta section requerida '{}'".format(section),
            })

    for req in contract.get('required_tasks', []):
        found = tasks_by_id.get(req.get('id'))
        if not found:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_TASK',
                'msg': "falta task requerida '{}'".format(req.get('id')),
            })
            continue
        if req.get('section') and found.get('section') != req.get('section'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'TASK_SECTION_MISMATCH',
                'msg': "task '{}' esperaba section '{}', encontrado '{}'".format(
                    req.get('id'), req.get('section'), found.get('section')),
            })
        if req.get('start') and found.get('start') != req.get('start'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'TASK_START_MISMATCH',
                'msg': "task '{}' esperaba start '{}', encontrado '{}'".format(
                    req.get('id'), req.get('start'), found.get('start')),
            })
        if req.get('end') and found.get('end') != req.get('end'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'TASK_END_MISMATCH',
                'msg': "task '{}' esperaba end '{}', encontrado '{}'".format(
                    req.get('id'), req.get('end'), found.get('end')),
            })

    return findings


def _validate_pie(text, contract, file_label):
    findings = []
    parsed = parse_pie(text)
    slices_by_label = {s['label']: s for s in parsed['slices']}

    min_slices = contract.get('min_slices')
    if isinstance(min_slices, int) and len(parsed['slices']) < min_slices:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MIN_SLICES',
            'msg': 'min_slices {}, encontrado {}'.format(min_slices, len(parsed['slices'])),
        })

    max_slices = contract.get('max_slices')
    if isinstance(max_slices, int) and len(parsed['slices']) > max_slices:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MAX_SLICES',
            'msg': 'max_slices {}, encontrado {}'.format(max_slices, len(parsed['slices'])),
        })

    for req in contract.get('required_slices', []):
        found = slices_by_label.get(req.get('label'))
        if not found:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_SLICE',
                'msg': "falta slice requerida '{}'".format(req.get('label')),
            })
            continue
        if 'value' in req and found.get('value') != req.get('value'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'SLICE_VALUE_MISMATCH',
                'msg': "slice '{}' esperaba value {}, encontrado {}".format(
                    req.get('label'), req.get('value'), found.get('value')),
            })

    return findings


def _validate_journey(text, contract, file_label):
    findings = []
    parsed = parse_journey(text)

    min_tasks = contract.get('min_tasks')
    if isinstance(min_tasks, int) and len(parsed['tasks']) < min_tasks:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MIN_TASKS',
            'msg': 'min_tasks {}, encontrado {}'.format(min_tasks, len(parsed['tasks'])),
        })

    max_tasks = contract.get('max_tasks')
    if isinstance(max_tasks, int) and len(parsed['tasks']) > max_tasks:
        findings.append({
            'file': file_label, 'level': 'ERROR', 'rule': 'MAX_TASKS',
            'msg': 'max_tasks {}, encontrado {}'.format(max_tasks, len(parsed['tasks'])),
        })

    for section in contract.get('required_sections', []):
        if section not in parsed['sections']:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_SECTION',
                'msg': "falta section requerida '{}'".format(section),
            })

    for actor in contract.get('required_actors', []):
        if actor not in parsed['actors']:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_ACTOR',
                'msg': "falta actor requerido '{}'".format(actor),
            })

    for req in contract.get('required_tasks', []):
        found = next((t for t in parsed['tasks'] if t['task'] == req.get('task')), None)
        if not found:
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'MISSING_TASK',
                'msg': "falta task requerida '{}'".format(req.get('task')),
            })
            continue
        if req.get('section') and found.get('section') != req.get('section'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'TASK_SECTION_MISMATCH',
                'msg': "task '{}' esperaba section '{}', encontrado '{}'".format(
                    req.get('task'), req.get('section'), found.get('section')),
            })
        if 'score' in req and found.get('score') != req.get('score'):
            findings.append({
                'file': file_label, 'level': 'ERROR', 'rule': 'TASK_SCORE_MISMATCH',
                'msg': "task '{}' esperaba score {}, encontrado {}".format(
                    req.get('task'), req.get('score'), found.get('score')),
            })
        for person in req.get('people', []):
            if person not in found.get('people', []):
                findings.append({
                    'file': file_label, 'level': 'ERROR', 'rule': 'TASK_MISSING_PERSON',
                    'msg': "task '{}' esperaba incluir a '{}', encontrado {}".format(
                        req.get('task'), person, found.get('people')),
                })

    return findings


_VALIDATORS = {
    'flowchart': _validate_flowchart,
    'gantt': _validate_gantt,
    'pie': _validate_pie,
    'journey': _validate_journey,
}


def validate_diagram(mmd_path, contract_path):
    """Valida un .mmd contra su .diagram-contract.json. Retorna lista de findings."""
    file_label = mmd_path.replace('\\', '/')

    try:
        with open(mmd_path, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except OSError as e:
        return [{'file': file_label, 'level': 'ERROR', 'rule': 'FILE_ERROR', 'msg': str(e)}]

    try:
        with open(contract_path, 'r', encoding='utf-8') as fh:
            contract = json.load(fh)
    except (OSError, ValueError) as e:
        return [{
            'file': contract_path.replace('\\', '/'),
            'level': 'ERROR',
            'rule': 'CONTRACT_INVALID',
            'msg': str(e),
        }]

    diagram_type = get_diagram_type(text)
    normalized = 'flowchart' if diagram_type in ('flowchart', 'graph') else diagram_type

    expected_type = contract.get('diagram_type')
    expected_normalized = 'flowchart' if expected_type == 'flowchart' else expected_type

    if expected_normalized and expected_normalized not in SUPPORTED_TYPES:
        return [{
            'file': file_label,
            'level': 'ERROR',
            'rule': 'DIAGRAM_TYPE_UNSUPPORTED',
            'msg': (
                "este gate pure-Python solo soporta diagram_type {} "
                "(para '{}' usar el proyecto hermano mermaid-gate)".format(SUPPORTED_TYPES, expected_type)
            ),
        }]

    if expected_normalized and normalized != expected_normalized:
        return [{
            'file': file_label,
            'level': 'ERROR',
            'rule': 'DIAGRAM_TYPE_MISMATCH',
            'msg': "diagram_type esperado '{}', encontrado '{}'".format(expected_type, diagram_type),
        }]

    if normalized not in SUPPORTED_TYPES:
        return [{
            'file': file_label,
            'level': 'ERROR',
            'rule': 'DIAGRAM_TYPE_UNSUPPORTED',
            'msg': (
                "este gate pure-Python solo soporta diagram_type {} "
                "(diagrama es '{}')".format(SUPPORTED_TYPES, diagram_type)
            ),
        }]

    findings = _VALIDATORS[normalized](text, contract, file_label)
    findings.sort(key=lambda f: (f['rule'], f['msg']))
    return findings


def main(argv):
    """Escanea paths por pares .mmd + .diagram-contract.json. Exit 1 si hay ERROR."""
    if not argv:
        argv = ['examples/diagrams']

    all_findings = []
    pairs_checked = 0
    paths_to_scan = []

    for path in argv:
        if not os.path.exists(path):
            all_findings.append({
                'file': path, 'level': 'INFO', 'rule': 'PATH_MISSING',
                'msg': 'path no existe: {}'.format(path),
            })
            continue

        if os.path.isdir(path):
            found_mmd = False
            for root, dirs, files in os.walk(path):
                for f in sorted(files):
                    if f.lower().endswith('.mmd'):
                        found_mmd = True
                        paths_to_scan.append(os.path.join(root, f))
            if not found_mmd:
                all_findings.append({
                    'file': path, 'level': 'INFO', 'rule': 'PATH_MISSING',
                    'msg': 'no hay archivos .mmd en: {}'.format(path),
                })
        else:
            paths_to_scan.append(path)

    for mmd_path in paths_to_scan:
        base, _ = os.path.splitext(mmd_path)
        contract_path = base + '.diagram-contract.json'
        if not os.path.exists(contract_path):
            all_findings.append({
                'file': mmd_path.replace('\\', '/'), 'level': 'WARNING', 'rule': 'CONTRACT_MISSING',
                'msg': 'falta el contrato: {}'.format(contract_path.replace('\\', '/')),
            })
            continue
        pairs_checked += 1
        all_findings.extend(validate_diagram(mmd_path, contract_path))

    for f in all_findings:
        print('{} [{}] {}: {}'.format(f['level'], f['rule'], f['file'], f['msg']))

    error_count = sum(1 for f in all_findings if f['level'] == 'ERROR')
    warning_count = sum(1 for f in all_findings if f['level'] == 'WARNING')

    print()
    print('Resumen: {} error(es), {} warning(s), {} diagrama(s) verificados'.format(
        error_count, warning_count, pairs_checked
    ))

    return 1 if error_count > 0 else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
