"""Tree-sitter adapters for the opt-in Git change auditor."""

import json
import re
import tomllib

from tree_sitter import Language, Parser
import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_rust
import tree_sitter_typescript


GRAMMARS = {
    '.js': tree_sitter_javascript.language,
    '.jsx': tree_sitter_javascript.language,
    '.ts': tree_sitter_typescript.language_typescript,
    '.tsx': tree_sitter_typescript.language_tsx,
    '.go': tree_sitter_go.language,
    '.rs': tree_sitter_rust.language,
}
JS = {'.js', '.jsx', '.ts', '.tsx'}
FUNCTIONS = {'function_declaration', 'function_expression',
             'generator_function_declaration', 'arrow_function',
             'method_definition', 'function_item', 'method_declaration'}
BRANCHES = {'if_statement', 'if_expression', 'for_statement', 'for_in_statement',
            'while_statement', 'do_statement', 'switch_case', 'case_clause',
            'catch_clause', 'ternary_expression', 'match_arm'}
RUST_LOCAL = {'std', 'core', 'alloc', 'crate', 'self', 'super'}


def _finding(rule, path, msg):
    return {'rule': rule, 'path': path, 'msg': msg}


def _walk(node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node, source):
    return source[node.start_byte:node.end_byte].decode('utf-8')


def _ext(target):
    return '.' + target.rsplit('.', 1)[-1] if '.' in target else ''


def _parse(target, source):
    tree = Parser(Language(GRAMMARS[_ext(target)]())).parse(source)
    if tree.root_node.has_error:
        raise ValueError('source contains syntax errors')
    return tree.root_node


def _json_manifest(source):
    data = json.loads(source)
    if not isinstance(data, dict):
        raise ValueError('package.json must be an object')
    deps = set()
    for field in ('dependencies', 'devDependencies', 'peerDependencies',
                  'optionalDependencies'):
        value = data.get(field, {})
        if not isinstance(value, dict):
            raise ValueError(field + ' must be an object')
        deps.update(value)
    return deps, None


def _cargo_manifest(source):
    data = tomllib.loads(source)
    targets = data.get('target', {})
    package = data.get('package', {})
    if not isinstance(targets, dict) or not isinstance(package, dict):
        raise ValueError('invalid Cargo target or package table')
    deps = set()
    for table in [data] + list(targets.values()):
        if not isinstance(table, dict):
            raise ValueError('invalid Cargo target table')
        for field in ('dependencies', 'dev-dependencies', 'build-dependencies'):
            entries = table.get(field, {})
            if not isinstance(entries, dict):
                raise ValueError('invalid Cargo dependency table')
            for name, value in entries.items():
                if isinstance(value, dict) and value.get('workspace'):
                    raise ValueError('Cargo workspace dependency requires unsupported resolution')
                deps.add(name)
    if data.get('patch') or data.get('replace'):
        raise ValueError('Cargo patch or replace requires unsupported resolution')
    return deps, package.get('name')


def _go_require_entry(line, single=False):
    parts = line.split()
    if len(parts) < (3 if single else 2):
        raise ValueError('invalid go.mod require entry')
    return parts[1] if single else parts[0]


def _go_directive(line, deps):
    if line.startswith('module '):
        return line.split(None, 1)[1], False
    if line == 'require (':
        return None, True
    if line.startswith('require '):
        deps.add(_go_require_entry(line, single=True))
        return None, False
    if line.startswith(('go ', 'toolchain ', 'exclude ',
                        'retract ', 'godebug ')):
        return None, False
    raise ValueError('unsupported go.mod directive: ' + line)


def _go_manifest(source):
    module, deps, require = None, set(), False
    for raw in source.splitlines():
        line = raw.split('//', 1)[0].strip()
        if not line:
            continue
        if line == ')' and require:
            require = False
            continue
        if require:
            deps.add(_go_require_entry(line))
        else:
            declared, require = _go_directive(line, deps)
            module = declared or module
    if not module or require:
        raise ValueError('go.mod module or require block is incomplete')
    return deps, module


def _manifest(target, source):
    if source is None:
        raise ValueError('required dependency manifest is missing')
    if _ext(target) in JS:
        return _json_manifest(source)
    if _ext(target) == '.rs':
        return _cargo_manifest(source)
    return _go_manifest(source)


def _js_imports(root, source):
    names, unsupported = set(), []
    for node in _walk(root):
        if node.type in ('import_statement', 'export_statement'):
            value = node.child_by_field_name('source')
            if value is None:
                continue
            literal = _text(value, source)
            if len(literal) < 2 or literal[0] not in ('"', "'") or literal[-1] != literal[0]:
                unsupported.append('nonliteral import/export')
                continue
            name = literal[1:-1]
            if name.startswith(('.', '/', 'node:')):
                continue
            parts = name.split('/')
            names.add('/'.join(parts[:2]) if name.startswith('@') else parts[0])
        elif node.type == 'call_expression':
            function = node.child_by_field_name('function')
            if function and _text(function, source) in ('require', 'import'):
                unsupported.append('dynamic import or require')
    return names, unsupported


def _go_imports(root, source):
    names = set()
    for node in _walk(root):
        if node.type == 'import_spec':
            value = node.child_by_field_name('path')
            if value is None:
                raise ValueError('Go import lacks path')
            names.add(_text(value, source).strip('"' + chr(96)))
    return names, []


def _rust_imports(root, source):
    names, unsupported = set(), []
    for node in _walk(root):
        if node.type == 'use_declaration':
            value = node.child_by_field_name('argument')
            if value:
                match = re.match(r'(?:::)?([A-Za-z_][A-Za-z_0-9]*)',
                                 _text(value, source))
                if match:
                    names.add(match.group(1))
                else:
                    unsupported.append('Rust use tree root cannot be resolved')
        elif node.type == 'extern_crate_declaration':
            value = node.child_by_field_name('name')
            if value:
                names.add(_text(value, source))
    return names - RUST_LOCAL, unsupported


def _imports(target, root, source):
    if _ext(target) in JS:
        return _js_imports(root, source)
    if _ext(target) == '.go':
        return _go_imports(root, source)
    return _rust_imports(root, source)


def _external(target, name, module):
    if _ext(target) == '.go':
        return not (name == module or name.startswith((module or '') + '/')) and '.' in name.split('/')[0]
    return name != module


def _declared(target, name, deps):
    if _ext(target) == '.go':
        return any(name == dep or name.startswith(dep + '/') for dep in deps)
    return name in deps


def _parameters(node):
    params = node.child_by_field_name('parameters')
    if params is None:
        return 0
    if params.type == 'identifier':
        return 1
    count = 0
    for child in params.named_children:
        if child.type in ('required_parameter', 'optional_parameter', 'parameter',
                          'variadic_parameter_declaration', 'self_parameter', 'identifier',
                          'assignment_pattern', 'rest_pattern', 'object_pattern',
                          'array_pattern'):
            count += 1
        elif child.type == 'parameter_declaration':
            count += max(1, sum(item.type == 'identifier' for item in child.named_children))
    return count


def _metrics(function, source):
    complexity, nesting, opaque = 1, 0, False
    def visit(node, depth):
        nonlocal complexity, nesting, opaque
        for child in node.named_children:
            if child.type in FUNCTIONS:
                continue
            complexity += int(child.type in BRANCHES)
            if child.type == 'binary_expression':
                expression = _text(child, source)
                complexity += int('&&' in expression or '||' in expression)
            opaque |= child.type == 'macro_invocation'
            next_depth = depth + int(child.type in BRANCHES and
                                     child.type != 'ternary_expression')
            nesting = max(nesting, next_depth)
            visit(child, next_depth)
    visit(function, 0)
    return {'cyclomatic_max': complexity, 'nesting_max': nesting,
            'lines_max': function.end_point.row - function.start_point.row + 1,
            'params_max': _parameters(function)}, opaque


def _budgets(target, root, source, budget):
    findings = []
    for node in _walk(root):
        if node.type not in FUNCTIONS:
            continue
        metrics, opaque = _metrics(node, source)
        label = 'function at line ' + str(node.start_point.row + 1)
        if opaque:
            findings.append(_finding('BUDGET_UNSUPPORTED', target,
                                     label + ' contains an opaque macro'))
            continue
        for field, measured in metrics.items():
            limit = budget.get(field)
            if limit is None:
                continue
            if isinstance(limit, str) and limit.isdecimal():
                limit = int(limit)
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                findings.append(_finding('BUDGET_POLICY', target, 'invalid ' + field))
            elif measured > limit:
                findings.append(_finding('BUDGET_' + field.split('_')[0].upper(),
                                         target, '{}: {}={} exceeds {}'.format(
                                             label, field, measured, limit)))
    return findings


def audit_source(target, before, after, policy, manifests) -> list:
    """Audit changed source bytes against an approved policy and manifests."""
    if _ext(target) not in GRAMMARS:
        return [_finding('CHECK_UNSUPPORTED', target, 'language has no adapter')]
    try:
        old_root = _parse(target, before) if before else None
        new_root = _parse(target, after)
    except (UnicodeError, ValueError) as exc:
        return [_finding('CHECK_PARSE', target, str(exc))]
    try:
        old_deps, _ = _manifest(target, manifests.get('before')) if manifests.get('before') else (set(), None)
        new_deps, module = _manifest(target, manifests.get('after'))
    except (ValueError, TypeError) as exc:
        return [_finding('MANIFEST_PARSE', target, str(exc))]
    allowed = set(policy.get('deps_allowed', []))
    findings = [_finding('DEP_UNDECLARED', target,
                         'new manifest dependency not approved: ' + name)
                for name in sorted(new_deps - old_deps) if name not in allowed]
    try:
        old_imports, _ = _imports(target, old_root, before) if old_root else (set(), [])
        new_imports, unsupported = _imports(target, new_root, after)
    except (UnicodeError, ValueError) as exc:
        return findings + [_finding('CHECK_PARSE', target, str(exc))]
    findings.extend(_finding('DEP_UNSUPPORTED', target, reason)
                    for reason in unsupported)
    for name in sorted(new_imports - old_imports):
        approved = (any(name == dep or name.startswith(dep + '/')
                        for dep in allowed) if _ext(target) == '.go'
                    else name in allowed)
        if _external(target, name, module) and (
                not _declared(target, name, new_deps) or not approved):
            findings.append(_finding('DEP_UNDECLARED', target,
                                     'new external import not declared and approved: ' + name))
    findings.extend(_budgets(target, new_root, after, policy.get('budget', {})))
    return sorted(findings, key=lambda item: (item['path'], item['rule'], item['msg']))
