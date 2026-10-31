#!/usr/bin/env python3
"""Run small deterministic Python mutants against one frozen test command."""

import argparse
import ast
import copy
import hashlib
import os
from pathlib import Path
import re
import shutil
import shlex
import stat
import subprocess
import sys
import tempfile
from typing import NamedTuple

from validate_contracts import parse_frontmatter, relative_artifact, validate_file
from process_tree import run as run_process


class _FirstMutation(ast.NodeTransformer):
    def __init__(self, operator):
        self.operator = operator
        self.changed = False

    def visit_Constant(self, node):
        if self.operator == "invert-bool" and not self.changed and isinstance(node.value, bool):
            self.changed = True
            return ast.copy_location(ast.Constant(value=not node.value), node)
        return self.generic_visit(node)

    def visit_Compare(self, node):
        if self.operator == "flip-comparison" and not self.changed and node.ops:
            flips = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
                     ast.Lt: ast.GtE, ast.GtE: ast.Lt,
                     ast.Gt: ast.LtE, ast.LtE: ast.Gt}
            operator_type = type(node.ops[0])
            if operator_type in flips:
                node = copy.deepcopy(node)
                node.ops[0] = flips[operator_type]()
                self.changed = True
                return node
        return self.generic_visit(node)

    def visit_If(self, node):
        if self.operator == "negate-branch" and not self.changed:
            node = copy.deepcopy(node)
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            self.changed = True
            return node
        return self.generic_visit(node)


def mutation_sources(source):
    results = []
    tree = ast.parse(source)
    for operator in ("invert-bool", "flip-comparison", "negate-branch"):
        mutant = _FirstMutation(operator)
        mutated_tree = mutant.visit(copy.deepcopy(tree))
        if mutant.changed:
            results.append({"operator": operator,
                            "source": ast.unparse(ast.fix_missing_locations(mutated_tree)) + "\n"})
    return results


def _command(value):
    try:
        tokens = shlex.split(value, posix=os.name != "nt")
        if os.name == 'nt':
            tokens = [t[1:-1] if len(t) > 1 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
        return tokens
    except ValueError as exc:
        raise ValueError("test_command invalido: {}".format(exc)) from exc


def _copy_inputs(root, destination):
    agents = os.path.abspath(os.path.join(root, '.agents'))
    def ignore(directory, names):
        excluded = {name for name in names if name in ('.git', '__pycache__')
                    or name.endswith(('.pyc', '.pyo'))}
        if os.path.abspath(directory) == agents:
            excluded.add('logs')
        return excluded
    shutil.copytree(root, destination, ignore=ignore)


class _Experiment(NamedTuple):
    root: Path
    temporary: Path
    metadata: dict
    command: list
    timeout: float
    identity: dict


def _source_digest(content):
    raw = content.encode('utf-8') if isinstance(content, str) else content
    return hashlib.sha256(raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


def _text(value):
    return value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''


def _asserted_failures(stderr):
    headers = list(re.finditer(r'^(FAIL|ERROR): ([^\n(]+) \(([^)\n]+)\)', stderr, re.MULTILINE))
    identifiers, asserted = [], 0
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(stderr)
        block = stderr[header.end():end]
        exceptions = re.findall(r'^([A-Za-z_][\w.]*)(?::[^\n]*|)$', block, re.MULTILINE)
        if header[1] == 'FAIL' and exceptions and exceptions[-1] == 'AssertionError':
            method, identifier = header[2].strip(), header[3]
            identifiers.append(identifier if identifier.endswith('.' + method) else identifier + '.' + method)
            asserted += 1
    return sorted(set(identifiers)), asserted


def _unittest_observation(stderr):
    text = stderr.replace('\r\n', '\n').replace('\r', '\n')
    match = re.search(r'Ran (\d+) tests? in [^\n]+\n\n(OK|FAILED)(?: \(([^\n)]*)\))?\s*\Z', text)
    counts = {'tests_run': 0, 'passed_tests': 0, 'failures': 0, 'errors': 0,
              'asserted_failures': 0, 'failed_tests': [], 'healthy': False,
              'unexpected_successes': 0}
    if not match:
        return counts
    details = {name: int(value) for name, value in re.findall(
        r'(failures|errors|skipped|expected failures|unexpected successes)=(\d+)', match[3] or '')}
    counts.update(tests_run=int(match[1]), failures=details.get('failures', 0), errors=details.get('errors', 0))
    counts['unexpected_successes'] = details.get('unexpected successes', 0)
    counts['passed_tests'] = max(0, int(match[1]) - sum(details.values()))
    counts['failed_tests'], counts['asserted_failures'] = _asserted_failures(text)
    counts['healthy'] = match[2] == 'OK' and not counts['failures'] and not counts['errors']
    return counts


def _execute(command, directory, timeout):
    try:
        completed = run_process(command, cwd=directory, capture_output=True, timeout=timeout,
                                text=True, encoding='utf-8', errors='replace',
                                env=dict(os.environ, PYTHONUTF8='1', PYTHON_COLORS='0'))
        result = {'exit_code': completed.returncode, 'timeout': False,
                  'stdout': _text(completed.stdout), 'stderr': _text(completed.stderr)}
    except subprocess.TimeoutExpired as error:
        result = {'exit_code': None, 'timeout': True,
                  'stdout': _text(error.stdout), 'stderr': _text(error.stderr)}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result = {'exit_code': None, 'timeout': False, 'error': str(error), 'stdout': '', 'stderr': ''}
    return dict(result, **_unittest_observation(result['stderr']))


def _input_hashes(root, metadata):
    target = _target_path(root, metadata['target']).read_bytes()
    oracle = _target_path(root, metadata['tests']).read_bytes()
    return {'target_sha256': _source_digest(target), 'oracle_sha256': _source_digest(oracle),
            'target_raw_sha256': hashlib.sha256(target).hexdigest(),
            'oracle_raw_sha256': hashlib.sha256(oracle).hexdigest()}


def _changed_inputs(context, directory, expected):
    try:
        return _input_hashes(Path(directory), context.metadata) != expected
    except (OSError, ValueError):
        return True


def _control(context, stage):
    destination = context.temporary / stage
    try:
        _copy_inputs(context.root, destination)
        if _changed_inputs(context, destination, context.identity):
            raise ValueError('control copy does not preserve target and oracle')
        result = _execute(context.command, destination, context.timeout)
        result['input_changed'] = (_changed_inputs(context, destination, context.identity)
                                   or _changed_inputs(context, context.root, context.identity))
    except (OSError, ValueError) as error:
        result = {'exit_code': None, 'timeout': False, 'error': str(error),
                  'stdout': '', 'stderr': '', 'healthy': False, 'passed_tests': 0}
    passed = result['exit_code'] == 0 and result['healthy'] and result['passed_tests'] > 0
    return dict(result, stage=stage,
                status='PASS' if passed and not result.get('input_changed') else 'INCONCLUSIVE')


def _target_path(root, relative):
    if relative_artifact(str(root), relative) is None:
        raise ValueError('MUTATION_PATH: exact relative target inside the project required')
    path = root
    for part in relative.split('/'):
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            if not relative.lower().endswith('.py'):
                return root / relative
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('MUTATION_PATH: target aliases and reparse points are unsupported')
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('MUTATION_PATH: target must be a regular file with one link')
    return path


def _reject(reason):
    return dict(status='REJECT', reason=reason, detected=0, survived=0,
                inconclusive=0, mutants=[], controls=[])


def _classification(result, expected):
    if result['exit_code'] is None or result.get('input_changed') or not result['tests_run']:
        return 'INCONCLUSIVE'
    if result['exit_code'] == 0:
        return 'SURVIVED' if result['healthy'] and result['passed_tests'] > 0 else 'INCONCLUSIVE'
    asserted = result['failures'] > 0 and result['asserted_failures'] == result['failures']
    if not asserted or result['errors'] or result['unexpected_successes']:
        return 'INCONCLUSIVE'
    if expected is not None and set(result['failed_tests']) != set(expected):
        return 'INCONCLUSIVE'
    return 'DETECTED'


def _mutant(context, item, expected):
    index, mutant = item
    directory, source = context.temporary / ('mutant-' + str(index)), None
    try:
        _copy_inputs(context.root, directory)
        if _changed_inputs(context, directory, context.identity):
            raise ValueError('mutant copy does not preserve original inputs')
        destination = _target_path(directory, context.metadata['target'])
        destination.write_text(mutant['source'], encoding='utf-8', newline='\n')
        source = destination.read_text(encoding='utf-8')
        identity = dict(context.identity, target_sha256=_source_digest(source),
                        target_raw_sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
        result = _execute(context.command, directory, context.timeout)
        result['input_changed'] = (_changed_inputs(context, directory, identity)
                                   or _changed_inputs(context, context.root, context.identity))
    except (OSError, ValueError) as error:
        result = dict(_unittest_observation(''), exit_code=None, timeout=False,
                      stdout='', stderr='', error=str(error))
    expected_tests = mutant.get('expected_tests', expected)
    return dict(result, **context.identity, operator=mutant.get('operator') or mutant.get('id'),
                id=mutant.get('id'), source=source,
                mutant_sha256=_source_digest(source) if source is not None else None,
                command=context.metadata['test_command'], argv=list(context.command),
                source_hash_normalization='lf',
                output_sha256=hashlib.sha256((result['stdout'] + result['stderr']).encode('utf-8')).hexdigest(),
                status=_classification(result, expected_tests))


def _outcomes(mutants, controls):
    counts = {status: sum(row['status'] == status for row in mutants)
              for status in ('DETECTED', 'SURVIVED', 'INCONCLUSIVE')}
    controls_pass = len(controls) == 2 and all(row['status'] == 'PASS' for row in controls)
    ok = controls_pass and bool(mutants) and counts['DETECTED'] == len(mutants)
    reason = ('ORACLE_CONTROL' if not controls_pass else
              'ORACLE_INCONCLUSIVE' if counts['INCONCLUSIVE'] else
              'ORACLE_SURVIVED' if counts['SURVIVED'] else '')
    return dict(status='PASS' if ok else 'FAIL', reason=reason,
                detected=counts['DETECTED'], survived=counts['SURVIVED'],
                inconclusive=counts['INCONCLUSIVE'], mutants=mutants, controls=controls)


def _experiment(root, metadata, settings):
    identity = _input_hashes(root, metadata)
    outcomes, controls = [], []
    with tempfile.TemporaryDirectory(prefix='kdd-mutant-') as temporary:
        if Path(temporary).resolve().is_relative_to(root):
            return _reject('MUTATION_PATH: mutation copies must be outside the project')
        context = _Experiment(root, Path(temporary), metadata, _command(metadata['test_command']),
                              settings['timeout'], identity)
        for stage in ('original', 'copy'):
            controls.append(_control(context, stage))
            if controls[-1]['status'] != 'PASS':
                return dict(_outcomes([], controls), **identity)
        for index, mutant in enumerate(settings['mutants']):
            outcomes.append(_mutant(context, (index, mutant), settings.get('expected_tests')))
    return dict(_outcomes(outcomes, controls), **identity)


def audit_contract(contract_path, repo_root, timeout=120):
    with open(contract_path, "r", encoding="utf-8") as fh:
        data, _body = parse_frontmatter(fh.read())
    if not isinstance(data, dict):
        return _reject('MUTATION_INPUT: task contract metadata required')
    target_rel = data.get("target", "")
    try:
        root = Path(repo_root).resolve(strict=True)
        target = _target_path(root, target_rel)
    except (OSError, ValueError) as error:
        return _reject(str(error))
    if not target_rel.lower().endswith(".py"):
        return {"status": "SKIP", "reason": "target no Python", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    with open(target, "r", encoding="utf-8") as fh:
        source = fh.read()
    mutants = mutation_sources(source)
    if not mutants:
        return {"status": "SKIP", "reason": "sin operador aplicable", "detected": 0,
                "survived": 0, "inconclusive": 0, "mutants": []}
    return _experiment(root, data, {'mutants': mutants, 'timeout': timeout})


def _review_strings(values):
    return isinstance(values, list) and bool(values) and all(
        isinstance(value, str) and value.strip() and '\0' not in value for value in values)


def _review_mutants(mutants):
    if not isinstance(mutants, list) or not mutants:
        raise ValueError('ORACLE_POLICY: reviewed counterexamples are required')
    identifiers = set()
    for item in mutants:
        if not isinstance(item, dict) or set(item) != {'id', 'source', 'expected_tests'}:
            raise ValueError('ORACLE_POLICY: invalid counterexample schema')
        if not _review_strings([item['id'], item['source']]) or not _review_strings(item['expected_tests']):
            raise ValueError('ORACLE_POLICY: counterexample identity, source and expected tests are required')
        if item['id'] in identifiers:
            raise ValueError('ORACLE_POLICY: duplicate counterexample identity')
        identifiers.add(item['id'])


def _review_schema(review):
    fields = {'contract', 'risk', 'structural', 'timeout', 'mutants'}
    if not isinstance(review, dict) or set(review) != fields:
        raise ValueError('ORACLE_POLICY: invalid oracle review schema')
    if not _review_strings([review['contract'], review['risk'], review['structural']]):
        raise ValueError('ORACLE_POLICY: contract, risk and structure are required')
    if type(review['timeout']) is not int or not 0 < review['timeout'] <= 3600:
        raise ValueError('ORACLE_POLICY: timeout must be an integer in 1..3600')
    _review_mutants(review['mutants'])


def _review_command(metadata):
    command = _command(metadata['test_command'])
    expected = {metadata['tests'], metadata['tests'].removesuffix('.py').replace('/', '.')}
    if (len(command) != 4 or not re.fullmatch(r'python(?:3(?:\.\d+)?)?', command[0])
            or command[1:3] != ['-m', 'unittest'] or command[3] not in expected):
        raise ValueError('ORACLE_UNSUPPORTED: use unittest with the exact sealed Python oracle')
    return command


def _review_definition(contract_path, root, review):
    import audit_seals
    _review_schema(review)
    path = Path(contract_path)
    path = path if path.is_absolute() else root / path
    relative = path.relative_to(root).as_posix()
    if relative != review['contract']:
        raise ValueError('ORACLE_POLICY: review contract identity differs')
    path = _target_path(root, relative)
    data, _ = parse_frontmatter(path.read_text(encoding='utf-8'))
    if any(f.level == 'ERROR' for f in validate_file(str(path), repo_root=str(root))):
        raise ValueError('ORACLE_CONTRACT: a complete valid sealed contract is required')
    if (review['structural'] != 'python-ast' or not data['target'].lower().endswith('.py')
            or not data['tests'].lower().endswith('.py') or data['target'] == data['tests']
            or str(data.get('language', 'python')).lower() != 'python'):
        raise ValueError('ORACLE_UNSUPPORTED: distinct Python target and oracle with python-ast required')
    _target_path(root, data['target'])
    _target_path(root, data['tests'])
    _review_command(data)
    findings = audit_seals.audit_contract(str(path), str(root))
    if findings:
        raise ValueError('ORACLE_STRUCTURE: ' + '; '.join(row['rule'] for row in findings))
    for item in review['mutants']:
        _target_path(root, item['source'])
    return data


def review_contract(contract_path, repo_root, review):
    try:
        root = Path(repo_root).resolve(strict=True)
        data = _review_definition(contract_path, root, review)
        mutants = [dict(item, source=_target_path(root, item['source']).read_text(encoding='utf-8'))
                   for item in review['mutants']]
        result = _experiment(root, data, {'mutants': mutants, 'timeout': review['timeout']})
        return dict(result, target=data['target'],
                    structural={'method': 'python-ast', 'findings': []})
    except (OSError, ValueError, KeyError) as error:
        reason = str(error)
        if not reason.startswith('ORACLE_'):
            reason = 'ORACLE_CONTRACT: ' + reason
        return dict(_reject(reason), status='FAIL')


def _review_sources(root, names):
    return {name: hashlib.sha256(_target_path(root, name).read_bytes()).hexdigest()
            for name in names}


def _review_policy(repo_root, policy):
    root, reviews = Path(repo_root).resolve(strict=True), policy['oracle_reviews']
    rows, targets, entry = [], {}, reviews[0]
    try:
        for entry in reviews:
            data = _review_definition(str(root / entry['contract']), root, entry)
            if data['tests'] not in policy['protected']:
                raise ValueError('ORACLE_POLICY: sealed oracle must be protected')
            targets.update(_review_sources(root, [data['target']]))
        names = sorted(set(policy['protected']) | set(targets))
        original = _review_sources(root, names)
        for entry in reviews:
            row = review_contract(str(root / entry['contract']), str(root), entry)
            if _review_sources(root, names) != original:
                row.update(status='FAIL', reason='ORACLE_INCONCLUSIVE: review inputs changed during execution')
            rows.append(dict(row, contract=entry['contract'], risk=entry['risk']))
            if row['status'] != 'PASS':
                break
    except (OSError, ValueError, KeyError) as error:
        reason = str(error)
        if not reason.startswith('ORACLE_'):
            reason = 'ORACLE_CONTRACT: ' + reason
        rows.append({'status': 'FAIL', 'reason': reason, 'contract': entry['contract'], 'risk': entry['risk']})
    return {'reviews': rows, 'targets': targets,
            'ok': len(rows) == len(reviews) and all(row['status'] == 'PASS' for row in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = audit_contract(args.contract, args.repo_root)
    except (OSError, ValueError, KeyError) as error:
        result = _reject(str(error))
    if result['status'] == 'REJECT':
        print('REJECT mutation: ' + result.get('reason', 'invalid contract'))
        return 2
    for control in result.get('controls', []):
        print('control {}: {} exit={} timeout={}'.format(
            control['stage'], control['status'], control['exit_code'], control['timeout']))
    for mutant in result.get("mutants", []):
        print("{}: {}".format(mutant["operator"], mutant["status"]))
    print("mutation-audit: {} detected, {} survived, {} inconclusive".format(
        result["detected"], result["survived"], result["inconclusive"]))
    return 1 if args.strict and result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
