"""Run reviewed quality checks, including opt-in canonical task evidence.

The reviewed runner and Git are trusted. Candidate checks are not sandboxed.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
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


def validate_policy(root, data):
    fields = {'protected', 'implementation', 'pm', 'required_kinds', 'checks'}
    if not isinstance(data, dict) or set(data) not in (fields, fields | {'generated_task_evidence'}):
        raise Rejected('Policy fields must be: ' + ', '.join(sorted(fields)))
    for field in ('protected', 'implementation', 'pm'):
        for name in strings(data[field], field, field == 'protected'):
            safe_path(root, name)
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


@contextmanager
def _approved_process_runner(root, commit, content):
    name = 'scripts/process_tree.py'
    entry = git(root, 'ls-tree', commit, '--', name)
    header, separator, path = entry.rstrip(b'\n').partition(b'\t')
    fields = header.split()
    if (not separator or path != name.encode('ascii') or len(fields) != 3
            or fields[0] not in (b'100644', b'100755') or fields[1] != b'blob'):
        raise Rejected('Approved process helper must be a regular Git file')
    with tempfile.TemporaryDirectory(prefix='kdd-approved-quality-process-') as directory:
        helper = Path(directory) / 'process_tree.py'
        if helper.resolve().is_relative_to(root):
            raise Rejected('Approved process helper must be outside the checkout')
        helper.write_bytes(content)
        spec = importlib.util.spec_from_file_location('_kdd_approved_quality_process', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module.run


def _checks(root, commit, policy, approved, run):
    cache = {}
    integrity(root, commit, policy, approved, cache)
    for iteration in (1, 2):
        for check in policy['checks']:
            print('RUN %s/2 %s [%s]' % (iteration, check['name'], check['kind']), flush=True)
            try:
                result = run(check['argv'], cwd=root, timeout=check['timeout'],
                             shell=False)
            finally:
                integrity(root, commit, policy, approved, cache)
            if result.returncode:
                raise Rejected('Check failed: %s (exit %s)' % (check['name'], result.returncode))


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
