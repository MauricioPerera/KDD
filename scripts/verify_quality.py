"""Run reviewed quality checks, including opt-in canonical task evidence.

The reviewed runner and Git are trusted. Candidate checks are not sandboxed.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile


class Rejected(ValueError):
    """An approval condition was not satisfied."""


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise Rejected('Git operation failed: ' + result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def approved_commit(root, reference):
    """Accept only the native, canonical OID of an existing commit object."""
    if not isinstance(reference, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', reference):
        raise Rejected('approved_ref must be a canonical full commit OID, not an alias')
    fields = git(root, 'rev-parse', '--show-object-format', '--verify',
                 '--end-of-options', reference + '^{commit}').decode('ascii').splitlines()
    if (len(fields) != 2 or len(reference) != {'sha1': 40, 'sha256': 64}.get(fields[0])
            or fields[1] != reference):
        raise Rejected('approved_ref must identify the canonical commit object')
    return reference


def _object_header(output, offset, spec, allow_missing):
    end = output.find(b'\n', offset)
    if end < 0:
        raise Rejected('Truncated Git batch header')
    header = output[offset:end].split()
    offset = end + 1
    if header and header[-1] == b'missing' and allow_missing:
        return None, offset
    if (len(header) != 3 or header[1] != b'blob'
            or not re.fullmatch(rb'[0-9a-f]{40}|[0-9a-f]{64}', header[0])):
        raise Rejected('Missing or invalid Git blob: ' + spec)
    if not re.fullmatch(rb'[0-9]+', header[2]):
        raise Rejected('Missing or invalid Git blob: ' + spec)
    size = int(header[2])
    if output[offset + size:offset + size + 1] != b'\n':
        raise Rejected('Truncated Git batch body')
    return output[offset:offset + size], offset + size + 1


def _objects(root, specifications, allow_missing=False):
    specs = list(dict.fromkeys(specifications))
    if not specs:
        return {}
    if any(any(c in spec for c in '\r\n\0') for spec in specs):
        raise Rejected('Invalid Git object specification')
    result = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'],
                            input=('\n'.join(specs) + '\n').encode('utf-8'),
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise Rejected('Git batch could not complete')
    values, offset = {}, 0
    for spec in specs:
        values[spec], offset = _object_header(result.stdout, offset, spec, allow_missing)
    if offset != len(result.stdout):
        raise Rejected('Unexpected Git batch output')
    return values


def safe_path(root, value):
    if not isinstance(value, str) or not value or any(c in value for c in '\\\x00:*?[]\r\n'):
        raise Rejected('Invalid exact relative path: ' + repr(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise Rejected('Invalid relative path: ' + repr(value))
    local = root.joinpath(*path.parts)
    if not local.resolve().is_relative_to(root):
        raise Rejected('Path escapes repository: ' + value)
    return local


def strings(value, label, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value):
        raise Rejected('Expected list: ' + label)
    if any(not isinstance(item, str) or not item.strip() or '\x00' in item for item in value):
        raise Rejected('Expected nonempty strings: ' + label)
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected('Duplicate JSON key: ' + key)
        result[key] = value
    return result


TASK_MODULES = ('validate_tasks.py', 'task_git.py', 'task_model.py',
                'task_evidence.py', 'validate_contracts.py')
ORACLE_MODULES = ('mutation_audit.py', 'audit_seals.py', 'validate_contracts.py', 'process_tree.py')
CONTROL_MODULES = ('validate_budgets.py', 'validate_contracts.py')


def _generated_entry(entry, identifiers, protected):
    if not isinstance(entry, dict) or set(entry) != {'task_id', 'contract'}:
        raise Rejected('Invalid generated task evidence entry')
    identifier, contract = entry['task_id'], entry['contract']
    if not isinstance(identifier, str) or not re.fullmatch(r'TASK-[0-9]{3,}', identifier):
        raise Rejected('Invalid generated task ID')
    if identifier in identifiers:
        raise Rejected('Duplicate generated task ID')
    identifiers.add(identifier)
    if not isinstance(contract, str) or not re.fullmatch(r'knowledge/contracts/[\w.-]+\.md', contract):
        raise Rejected('Invalid generated task contract')
    if contract not in protected:
        raise Rejected('Generated task contract must be protected')


def _generated_policy(data):
    if 'generated_task_evidence' not in data:
        return
    entries = data['generated_task_evidence']
    if not isinstance(entries, list) or not entries:
        raise Rejected('generated_task_evidence must be a nonempty list')
    identifiers = set()
    for entry in entries:
        _generated_entry(entry, identifiers, data['protected'])
    required = {'scripts/' + name for name in TASK_MODULES}
    if not required.issubset(data['protected']):
        raise Rejected('All canonical task validators must be protected')


def _check_policy(check, names, kinds):
    if not isinstance(check, dict) or set(check) != {'name', 'kind', 'argv', 'timeout'}:
        raise Rejected('Invalid check schema')
    strings([check['name'], check['kind']], 'check name/kind', True)
    if check['name'] in names:
        raise Rejected('Duplicate check name: ' + check['name'])
    names.add(check['name'])
    kinds.add(check['kind'])
    strings(check['argv'], 'argv', True)
    if type(check['timeout']) is not int or not 0 < check['timeout'] <= 3600:
        raise Rejected('timeout must be an integer in 1..3600')


def _oracle_sources(mutants, protected):
    if not isinstance(mutants, list) or not mutants:
        raise Rejected('ORACLE_POLICY: reviewed counterexamples are required')
    for item in mutants:
        if not isinstance(item, dict) or not isinstance(item.get('source'), str):
            raise Rejected('ORACLE_POLICY: invalid counterexample source')
        if item['source'] not in protected:
            raise Rejected('ORACLE_POLICY: counterexample source must be protected')


def _oracle_entry(entry, protected):
    fields = {'contract', 'risk', 'structural', 'timeout', 'mutants'}
    if not isinstance(entry, dict) or set(entry) != fields:
        raise Rejected('ORACLE_POLICY: invalid review entry')
    if any(not isinstance(entry[key], str) or not entry[key].strip()
           for key in ('contract', 'risk', 'structural')):
        raise Rejected('ORACLE_POLICY: contract, risk and structure are required')
    if entry['contract'] not in protected:
        raise Rejected('ORACLE_POLICY: reviewed contract must be protected')
    if type(entry['timeout']) is not int or not 0 < entry['timeout'] <= 3600:
        raise Rejected('ORACLE_POLICY: timeout must be an integer in 1..3600')
    _oracle_sources(entry['mutants'], protected)


def _oracle_policy(data):
    if 'oracle_reviews' not in data:
        return
    if not isinstance(data['oracle_reviews'], list) or not data['oracle_reviews']:
        raise Rejected('ORACLE_POLICY: oracle_reviews must be a nonempty list')
    protected = set(data['protected'])
    if not {'scripts/' + name for name in ORACLE_MODULES}.issubset(protected):
        raise Rejected('ORACLE_POLICY: every frozen review runner module must be protected')
    for entry in data['oracle_reviews']:
        _oracle_entry(entry, protected)


def _control_path(root, value):
    try:
        return safe_path(root, value)
    except Rejected as error:
        raise Rejected('CONTROL_POLICY: ' + str(error)) from error


def _required_entry(root, entry, protected, identifiers):
    if not isinstance(entry, dict):
        raise Rejected('CONTROL_POLICY: required control must be an object')
    fields = {'id', 'contract', 'kind', 'mechanism'}
    if entry.get('kind') == 'forbid':
        fields.add('capability')
    if set(entry) != fields or any(not isinstance(entry[key], str) or not entry[key].strip()
                                   or '\0' in entry[key] for key in fields):
        raise Rejected('CONTROL_POLICY: invalid required control schema')
    if entry['id'] in identifiers:
        raise Rejected('CONTROL_POLICY: duplicate required control identity')
    identifiers.add(entry['id'])
    _control_path(root, entry['contract'])
    if entry['contract'] not in protected:
        raise Rejected('CONTROL_POLICY: required contract must be protected')


def _required_policy(root, data):
    if 'required_controls' not in data:
        return
    entries = data['required_controls']
    if not isinstance(entries, list) or not entries:
        raise Rejected('CONTROL_POLICY: nonempty required control inventory is required')
    protected, identifiers = set(data['protected']), set()
    if not {'scripts/' + name for name in CONTROL_MODULES}.issubset(protected):
        raise Rejected('CONTROL_POLICY: frozen measurement runner modules must be protected')
    for entry in entries:
        _required_entry(root, entry, protected, identifiers)


def validate_policy(root, data):
    fields = {'protected', 'implementation', 'pm', 'required_kinds', 'checks'}
    optional = {'generated_task_evidence', 'oracle_reviews', 'required_controls'}
    if not isinstance(data, dict) or not fields.issubset(data) or set(data) - fields - optional:
        raise Rejected('Policy fields must be: ' + ', '.join(sorted(fields)))
    path_checker = _control_path if 'required_controls' in data else safe_path
    for field in ('protected', 'implementation', 'pm'):
        for name in strings(data[field], field, field == 'protected'):
            path_checker(root, name)
    required = strings(data['required_kinds'], 'required_kinds', True)
    if not {'functional', 'adversarial'}.issubset(required):
        raise Rejected('functional and adversarial kinds are required')
    if not isinstance(data['checks'], list) or not data['checks']:
        raise Rejected('checks must be a nonempty list')
    names, kinds = set(), set()
    for check in data['checks']:
        _check_policy(check, names, kinds)
    if not set(required).issubset(kinds):
        raise Rejected('Required kind has no check')
    _generated_policy(data)
    _oracle_policy(data)
    _required_policy(root, data)
    return data


def normalized(content):
    return content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def changed_paths(root, commit):
    names = set()
    commands = [
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', commit, '--'),
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--cached', commit, '--'),
        ('diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', '--'),
        ('ls-files', '--others', '--exclude-standard', '-z'),
    ]
    for command in commands:
        names.update(p.decode('utf-8') for p in git(root, *command).split(b'\x00') if p)
    return names


_TASK_AUDIT = """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import task_git as journal
from validate_contracts import parse_frontmatter
from validate_tasks import validate_range
root,approved,head=Path(sys.argv[2]),sys.argv[3],sys.argv[4]
policy=json.loads(sys.stdin.read())
tasks=journal.read_tasks(root,head)
artifacts,nodes=[],[]
for entry in policy['generated_task_evidence']:
    contract=entry['contract']
    metadata,_=parse_frontmatter(journal.blob(root,approved,contract))
    if not isinstance(metadata,dict) or metadata.get('tests') not in policy['protected']:
        raise SystemExit('Generated task oracle must be protected')
    identifier=entry['task_id']
    node='knowledge/tasks/'+identifier+'.md'
    task=tasks.get(identifier)
    if task is not None:
        nodes.append(node)
        if task['contract']!=contract:
            raise SystemExit('Generated task contract mismatch')
        if task['status']=='done':
            artifacts.append(task['evidence'])
chain=journal.git(root,'rev-list','--first-parent','--reverse',head).splitlines()
findings=validate_range(root,chain[0],head)
if findings:
    raise SystemExit('Generated task history rejected: '+'; '.join(findings))
print(json.dumps({'artifacts':artifacts,'nodes':nodes}))
"""


def _task_manifest(root, commit, policy, approved, cache):
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode('ascii').strip()
    if head in cache:
        return cache[head]
    with tempfile.TemporaryDirectory(prefix='kdd-frozen-task-audit-') as directory:
        bundle = Path(directory)
        if bundle.resolve().is_relative_to(root):
            raise Rejected('Trusted task bundle must be outside the checkout')
        for name in TASK_MODULES:
            (bundle / name).write_bytes(approved['scripts/' + name])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
        for name in ('PYTHONPATH', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR'):
            env.pop(name, None)
        result = subprocess.run([sys.executable, '-I', '-c', _TASK_AUDIT,
                                 str(bundle), str(root), commit, head],
                                input=json.dumps(policy), capture_output=True, text=True,
                                encoding='utf-8', env=env, timeout=180, check=False)
    if result.returncode:
        raise Rejected('Task evidence audit failed: ' + result.stderr.strip())
    try:
        report = json.loads(result.stdout)
        artifacts, nodes = report['artifacts'], report['nodes']
        names = artifacts + nodes
        blobs = _objects(root, [head + ':' + name for name in names])
        manifest = {name: blobs[head + ':' + name] for name in names}
    except (ValueError, KeyError, TypeError) as exc:
        raise Rejected('Invalid trusted task manifest') from exc
    cache[head] = (artifacts, manifest)
    return cache[head]


def _generated_integrity(root, commit, policy, approved, cache):
    if 'generated_task_evidence' not in policy:
        return set()
    artifacts, manifest = _task_manifest(root, commit, policy, approved, cache)
    indices = _objects(root, [':' + name for name in manifest], allow_missing=True)
    for name, expected in manifest.items():
        path = safe_path(root, name)
        if not path.is_file() or path.is_symlink():
            raise Rejected('Committed task artifact missing: ' + name)
        work, index = path.read_bytes(), indices[':' + name]
        if name not in artifacts:
            work = normalized(work)
            index = normalized(index) if index is not None else None
        if work != expected or index != expected:
            raise Rejected('Task evidence or node differs from committed HEAD: ' + name)
    declared = {'knowledge/tasks/' + item['task_id'] + '.md'
                for item in policy['generated_task_evidence']}
    for name in declared - manifest.keys():
        if safe_path(root, name).exists():
            raise Rejected('Generated task node must be committed: ' + name)
    return set(artifacts)


def _protected_integrity(root, approved):
    indices = _objects(root, [':' + name for name in approved], allow_missing=True)
    for name, content in approved.items():
        path = safe_path(root, name)
        if not path.is_file() or path.is_symlink():
            raise Rejected('Protected file missing or symlink: ' + name)
        if normalized(path.read_bytes()) != normalized(content):
            raise Rejected('Protected file changed: ' + name)
        index = indices[':' + name]
        if index is None or normalized(index) != normalized(content):
            raise Rejected('Protected index changed: ' + name)


def integrity(root, commit, policy, approved, cache=None):
    for field in ('protected', 'implementation', 'pm'):
        for name in policy[field]:
            safe_path(root, name)
    _protected_integrity(root, approved)
    generated = _generated_integrity(root, commit, policy, approved,
                                     cache if cache is not None else {})
    allowed = set(policy['implementation']) | set(policy['pm']) | generated
    for name in changed_paths(root, commit):
        safe_path(root, name)
        if name not in allowed and name not in approved:
            raise Rejected('Outside approved perimeter: ' + name)


def _approved_regular(root, commit, name, label='process helper'):
    entry = git(root, 'ls-tree', commit, '--', name)
    header, separator, path = entry.rstrip(b'\n').partition(b'\t')
    fields = header.split()
    if (not separator or path != name.encode('ascii') or len(fields) != 3
            or fields[0] not in (b'100644', b'100755') or fields[1] != b'blob'):
        raise Rejected('Approved ' + label + ' must be a regular Git file')


@contextmanager
def _approved_process_runner(root, commit, content):
    _approved_regular(root, commit, 'scripts/process_tree.py')
    with tempfile.TemporaryDirectory(prefix='kdd-approved-quality-process-') as directory:
        helper = Path(directory) / 'process_tree.py'
        if helper.resolve().is_relative_to(root):
            raise Rejected('Approved process helper must be outside the checkout')
        helper.write_bytes(content)
        spec = importlib.util.spec_from_file_location('_kdd_approved_quality_process', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module.run


_ORACLE_AUDIT = """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import mutation_audit as audit
if not hasattr(audit,'_review_policy'):
    raise SystemExit('ORACLE_UNSUPPORTED: frozen runner predates required oracle reviews')
result=audit._review_policy(sys.argv[2],json.loads(Path(sys.argv[3]).read_text(encoding='utf-8')))
print(json.dumps(result,ensure_ascii=True,sort_keys=True))
raise SystemExit(0 if result['ok'] else 1)
"""


@contextmanager
def _oracle_bundle(root, context):
    with tempfile.TemporaryDirectory(prefix='kdd-approved-oracles-') as directory:
        bundle = Path(directory)
        if bundle.resolve().is_relative_to(root):
            raise Rejected('ORACLE_POLICY: frozen runner must be outside the checkout')
        for name in ORACLE_MODULES:
            path = 'scripts/' + name
            key = ('oracle-mode', context['commit'], path)
            if key not in context['cache']:
                _approved_regular(root, context['commit'], path, 'oracle review module')
                context['cache'][key] = True
            (bundle / name).write_bytes(context['approved'][path])
        yield bundle


def _review_target(root, name):
    path = safe_path(root, name)
    component = root
    for part in PurePosixPath(name).parts:
        component = component / part
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise Rejected('ORACLE_INCONCLUSIVE: reviewed target acquired a filesystem alias')
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Rejected('ORACLE_INCONCLUSIVE: reviewed target is no longer a regular file')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_review_targets(root, targets):
    try:
        if any(_review_target(root, name) != digest for name, digest in targets.items()):
            raise Rejected('ORACLE_INCONCLUSIVE: reviewed target changed after its experiment')
    except OSError as error:
        raise Rejected('ORACLE_INCONCLUSIVE: reviewed target became unavailable') from error


def _oracle_receipt(result):
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        code = 'ORACLE_UNSUPPORTED' if 'ORACLE_UNSUPPORTED' in (result.stderr or '') else 'ORACLE_INCONCLUSIVE'
        raise Rejected(code + ': frozen review runner did not produce its receipt') from error
    rows = data.get('reviews') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise Rejected('ORACLE_INCONCLUSIVE: required review coverage is absent')
    return data, rows


def _oracle_coverage(rows, expected):
    actual = [(row.get('contract'), row.get('risk')) for row in rows]
    if actual != [(entry['contract'], entry['risk']) for entry in expected]:
        raise Rejected('ORACLE_INCONCLUSIVE: required review identities are incomplete')
    for row, entry in zip(rows, expected):
        mutants, controls = row.get('mutants', []), row.get('controls', [])
        if [item.get('id') for item in mutants] != [item['id'] for item in entry['mutants']]:
            raise Rejected('ORACLE_INCONCLUSIVE: required counterexamples are incomplete')
        if any(item.get('status') != 'DETECTED' for item in mutants):
            raise Rejected('ORACLE_INCONCLUSIVE: counterexample evidence is incomplete')
        if len(controls) != 2 or any(item.get('passed_tests', 0) <= 0 for item in controls):
            raise Rejected('ORACLE_INCONCLUSIVE: healthy control evidence is incomplete')


def _oracle_reports(result, context, iteration):
    data, rows = _oracle_receipt(result)
    for row in rows:
        if not isinstance(row, dict) or row.get('contract') not in context['approved']:
            raise Rejected('ORACLE_INCONCLUSIVE: invalid review receipt')
        raw = normalized(context['approved'][row['contract']])
        row.update(schema_version=1, iteration=iteration, approved_ref=context['commit'],
                   contract_sha256=hashlib.sha256(raw).hexdigest())
        print('ORACLE_REVIEW ' + json.dumps(row, ensure_ascii=True, sort_keys=True), flush=True)
        if row.get('status') != 'PASS':
            raise Rejected(row.get('reason') or 'ORACLE_INCONCLUSIVE: required review failed')
    expected = context['policy']['oracle_reviews']
    if result.returncode or len(rows) != len(expected) or not data.get('ok'):
        raise Rejected('ORACLE_INCONCLUSIVE: required review execution was incomplete')
    _oracle_coverage(rows, expected)
    return data['targets']


def _oracle_pass(root, context, iteration):
    entries = context['policy'].get('oracle_reviews')
    if entries is None:
        return {}
    timeout = min(3600, sum((len(entry['mutants']) + 2) * entry['timeout'] for entry in entries)) + 30
    try:
        with _oracle_bundle(root, context) as bundle:
            payload = bundle / 'policy.json'
            payload.write_text(json.dumps(context['policy']), encoding='utf-8')
            try:
                result = context['run']([sys.executable, '-I', '-c', _ORACLE_AUDIT,
                                        str(bundle), str(root), str(payload)], cwd=root, capture_output=True,
                                        text=True, encoding='utf-8', errors='replace', timeout=timeout)
                return _oracle_reports(result, context, iteration)
            finally:
                integrity(root, context['commit'], context['policy'], context['approved'], context['cache'])
    except (OSError, subprocess.SubprocessError) as error:
        raise Rejected('ORACLE_INCONCLUSIVE: required review runner could not complete') from error


_CONTROL_AUDIT = """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import validate_budgets as measure
if not hasattr(measure,'measure_required'):
    raise SystemExit('CONTROL_UNSUPPORTED: frozen runner predates required measurement')
entry=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
path=Path(sys.argv[2])/entry['contract']
report=measure.measure_required(str(path.parent),sys.argv[2],path.stem)
print(json.dumps(report,ensure_ascii=True,sort_keys=True))
raise SystemExit(0 if report['status']=='PASS' else 1)
"""


@contextmanager
def _control_bundle(root, context):
    with tempfile.TemporaryDirectory(prefix='kdd-approved-controls-') as directory:
        bundle = Path(directory)
        if bundle.resolve().is_relative_to(root):
            raise Rejected('CONTROL_POLICY: frozen measurement runner must be outside the checkout')
        for name in CONTROL_MODULES:
            path = 'scripts/' + name
            key = ('control-mode', context['commit'], path)
            if key not in context['cache']:
                _approved_regular(root, context['commit'], path, 'measurement module')
                context['cache'][key] = True
            (bundle / name).write_bytes(context['approved'][path])
        yield bundle


def _control_failure(code, message):
    return {'schema_version': 1, 'status': 'FAIL', 'contracts_checked': 0,
            'functions_measured': 0, 'measurements': [],
            'findings': [{'rule': code, 'message': message}]}


def _control_result(completed):
    try:
        report = json.loads(completed.stdout)
    except (ValueError, TypeError):
        code = 'CONTROL_UNSUPPORTED' if 'CONTROL_UNSUPPORTED' in (completed.stderr or '') else 'CONTROL_INCONCLUSIVE'
        return _control_failure(code, 'frozen measurement runner did not produce its receipt')
    if not isinstance(report, dict) or report.get('schema_version') != 1:
        return _control_failure('CONTROL_INCONCLUSIVE', 'invalid measurement receipt schema')
    if completed.returncode and report.get('status') == 'PASS':
        return _control_failure('CONTROL_INCONCLUSIVE', 'measurement execution was not successful')
    report['exit_code'] = completed.returncode
    return report


def _control_run(root, context, entry):
    if entry['kind'] != 'budget' or entry['mechanism'] != 'python-ast':
        return _control_failure('CONTROL_UNSUPPORTED', 'required mechanism has no enforcement in this profile')
    try:
        with _control_bundle(root, context) as bundle:
            payload = bundle / 'entry.json'
            payload.write_text(json.dumps(entry), encoding='utf-8')
            completed = context['run']([sys.executable, '-I', '-c', _CONTROL_AUDIT,
                str(bundle), str(root), str(payload)], cwd=root, capture_output=True,
                text=True, encoding='utf-8', errors='replace', timeout=120)
            return _control_result(completed)
    except Rejected as error:
        return _control_failure('CONTROL_POLICY', str(error))
    except (OSError, subprocess.SubprocessError) as error:
        return _control_failure('CONTROL_INCONCLUSIVE', str(error))


def _control_row(context, entry, iteration, report):
    row = dict(report, id=entry['id'], contract=entry['contract'], iteration=iteration,
        approved_ref=context['commit'], mechanism=entry['mechanism'], runtime_isolation=False,
        scope='module-functions' if report.get('measurements') else 'not-measured',
        contract_sha256=hashlib.sha256(normalized(context['approved'][entry['contract']])).hexdigest(),
        runner_sha256={name: hashlib.sha256(context['approved']['scripts/' + name]).hexdigest()
                       for name in CONTROL_MODULES})
    for finding in row.get('findings', []):
        if finding.get('rule') == 'BUDGET_CONTRACT':
            finding['rule'] = 'CONTROL_CONTRACT'
    return row


def _control_targets(root, row):
    measurements = row.get('measurements', [])
    if (row.get('contracts_checked') != 1 or row.get('functions_measured', 0) <= 0
            or len(measurements) != 1 or measurements[0].get('contract') != row['contract']):
        raise Rejected('CONTROL_INCONCLUSIVE: required measurement has no exact positive coverage')
    measurement = measurements[0]
    if (measurement.get('method') != 'python-ast' or measurement.get('scope') != 'module-functions'
            or len(measurement.get('functions', [])) != row['functions_measured']):
        raise Rejected('CONTROL_INCONCLUSIVE: unsupported measurement coverage')
    targets = {measurement['target']: measurement['target_raw_sha256']}
    _stable_control_targets(root, targets)
    return targets


def _stable_control_targets(root, targets):
    try:
        _stable_review_targets(root, targets)
    except (OSError, Rejected) as error:
        raise Rejected('CONTROL_CHANGED: required measured target changed or became unavailable') from error


def _control_observation(root, row):
    if row.get('status') != 'PASS' or row.get('findings'):
        return row, {}
    try:
        return row, _control_targets(root, row)
    except (KeyError, TypeError, ValueError) as error:
        code = str(error).split(':', 1)[0]
        if not code.startswith('CONTROL_'):
            code = 'CONTROL_INCONCLUSIVE'
        row.update(status='FAIL', findings=[{'rule': code, 'message': str(error)}])
        return row, {}


def _required_pass(root, context, iteration):
    targets = {}
    for entry in context['policy'].get('required_controls', []):
        try:
            row = _control_row(context, entry, iteration, _control_run(root, context, entry))
            row, measured = _control_observation(root, row)
            print('REQUIRED_CONTROL ' + json.dumps(row, ensure_ascii=True, sort_keys=True), flush=True)
            if row.get('status') != 'PASS' or row.get('findings'):
                reasons = [item.get('rule', 'CONTROL_INCONCLUSIVE') for item in row.get('findings', [])]
                raise Rejected(', '.join(reasons) or 'CONTROL_INCONCLUSIVE: required measurement failed')
            if any(name in targets and targets[name] != digest for name, digest in measured.items()):
                raise Rejected('CONTROL_CHANGED: different measured versions within one pass')
            targets.update(measured)
            _stable_control_targets(root, targets)
        finally:
            integrity(root, context['commit'], context['policy'], context['approved'], context['cache'])
    return targets


def _profiles(root, context, iteration):
    _stable_review_targets(root, context['oracle_targets'])
    _stable_control_targets(root, context['control_targets'])
    measured = _required_pass(root, context, iteration)
    if context['control_targets'] and context['control_targets'] != measured:
        raise Rejected('CONTROL_CHANGED: required controls measured different target versions')
    context['control_targets'] = measured
    measured = _oracle_pass(root, context, iteration)
    if context['oracle_targets'] and context['oracle_targets'] != measured:
        raise Rejected('ORACLE_INCONCLUSIVE: required reviews observed different target versions')
    context['oracle_targets'] = measured
    _stable_review_targets(root, measured)
    _stable_control_targets(root, context['control_targets'])


def _run_check(root, context, check, iteration):
    print('RUN %s/2 %s [%s]' % (iteration, check['name'], check['kind']), flush=True)
    try:
        result = context['run'](check['argv'], cwd=root, timeout=check['timeout'], shell=False)
    finally:
        integrity(root, context['commit'], context['policy'], context['approved'], context['cache'])
        _stable_review_targets(root, context['oracle_targets'])
        _stable_control_targets(root, context['control_targets'])
    if result.returncode:
        raise Rejected('Check failed: %s (exit %s)' % (check['name'], result.returncode))


def _checks(root, commit, policy, approved, run):
    cache = {}
    integrity(root, commit, policy, approved, cache)
    context = {'commit': commit, 'policy': policy, 'approved': approved, 'run': run, 'cache': cache,
               'oracle_targets': {}, 'control_targets': {}}
    if 'oracle_reviews' not in policy:
        print('LIMIT quality: oracle assurance not requested', flush=True)
    if 'required_controls' not in policy:
        print('LIMIT quality: required controls not requested', flush=True)
    for iteration in (1, 2):
        _profiles(root, context, iteration)
        for check in policy['checks']:
            _run_check(root, context, check, iteration)


def approve(root, policy_path, reference):
    root = root.resolve(strict=True)
    actual = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if actual != root:
        raise Rejected('repo-root must be the Git repository root')
    safe_path(root, policy_path)
    commit = approved_commit(root, reference)
    raw = git(root, 'show', commit + ':' + policy_path)
    policy = validate_policy(root, json.loads(raw, object_pairs_hook=unique_object))
    helper = commit + ':scripts/process_tree.py'
    objects = _objects(root, [commit + ':' + name for name in policy['protected']] + [helper])
    approved = {name: objects[commit + ':' + name] for name in policy['protected']}
    approved[policy_path] = raw
    with _approved_process_runner(root, commit, objects[helper]) as run:
        _checks(root, commit, policy, approved, run)
    print('PASS quality: integrity, perimeter and all checks verified twice', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--policy', required=True)
    parser.add_argument('--approved-ref', required=True)
    args = parser.parse_args()
    try:
        approve(Path(args.repo_root), args.policy, args.approved_ref)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('REJECT quality: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
