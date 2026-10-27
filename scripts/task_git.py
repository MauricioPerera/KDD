"""Official task state is committed on main; task branches contain the work."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

import task_evidence as proof
from task_model import TaskError, new_task, parse_task, render_task, task_path, valid_sha, validate_transition
from validate_contracts import parse_frontmatter, validate_file


_OBJECT_CACHE = ContextVar('kdd_git_objects', default=None)


@contextmanager
def object_cache():
    if _OBJECT_CACHE.get() is not None:
        yield
        return
    token = _OBJECT_CACHE.set({})
    try:
        yield
    finally:
        _OBJECT_CACHE.reset(token)


def _key(root, kind, revision, *parts):
    return (str(Path(root).resolve()), kind, revision, *parts)


def _output(root, args):
    try:
        result = subprocess.run(['git', '--literal-pathspecs', '-C', str(root), *args],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise TaskError('TASK_GIT: ' + str(exc)) from exc
    if result.returncode:
        raise TaskError('TASK_GIT: ' + result.stderr.strip())
    return result.stdout


def git(root, *args):
    return _output(root, args).strip()


def _native_oid(root, ref):
    if not valid_sha(ref):
        return False
    cache = _OBJECT_CACHE.get()
    key = _key(root, 'object-format', '')
    try:
        if cache is not None and key in cache:
            algorithm = cache[key]
        else:
            algorithm = git(root, 'rev-parse', '--show-object-format')
            if cache is not None:
                cache[key] = algorithm
    except TaskError:
        return False
    return len(ref) == {'sha1': 40, 'sha256': 64}.get(algorithm)


def commit_sha(root, ref):
    cache = _OBJECT_CACHE.get()
    if cache is None:
        return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    key = _key(root, 'commit', ref)
    format_key = _key(root, 'object-format', '')
    if format_key not in cache:
        try:
            fields = git(root, 'rev-parse', '--show-object-format', '--verify',
                         '--end-of-options', ref + '^{commit}').splitlines()
        except TaskError:
            fields = []
        if (len(fields) == 2 and valid_sha(fields[1])
                and len(fields[1]) == {'sha1': 40, 'sha256': 64}.get(fields[0])):
            cache[format_key] = fields[0]
            if valid_sha(ref) and len(ref) == len(fields[1]):
                cache[key] = fields[1]
            return fields[1]
        return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    immutable = _native_oid(root, ref)
    if cache is not None and immutable and key in cache:
        return cache[key]
    revision = git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    if cache is not None and immutable:
        cache[key] = revision
    return revision


def blob(root, ref, path):
    return blobs(root, ref, [path])[path]


def _batch_blobs(root, revision, names):
    specifications = [revision + ':' + name for name in names]
    if any(any(c in spec for c in '\r\n\0') for spec in specifications):
        raise TaskError('TASK_PATH: invalid batch object path')
    try:
        result = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'],
                                input=('\n'.join(specifications) + '\n').encode('utf-8'),
                                capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise TaskError('TASK_GIT: batch read failed')
        offset, values = 0, {}
        for name in names:
            end = result.stdout.find(b'\n', offset)
            header = result.stdout[offset:end].split() if end >= 0 else []
            if (len(header) != 3 or header[1] != b'blob' or not header[2].isdigit()
                    or not valid_sha(header[0].decode('ascii'))):
                raise TaskError('TASK_GIT: missing or invalid blob: ' + name)
            size, offset = int(header[2]), end + 1
            if result.stdout[offset + size:offset + size + 1] != b'\n':
                raise TaskError('TASK_GIT: truncated batch blob')
            value = result.stdout[offset:offset + size].decode('utf-8')
            values[name] = value.replace('\r\n', '\n').replace('\r', '\n')
            offset += size + 1
        if offset != len(result.stdout):
            raise TaskError('TASK_GIT: unexpected batch output')
        return values
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise TaskError('TASK_GIT: ' + str(exc)) from exc


def blobs(root, ref, names):
    if not names:
        return {}
    revision = ref if _native_oid(root, ref) else commit_sha(root, ref)
    cache = _OBJECT_CACHE.get()
    names = list(dict.fromkeys(names))
    if cache is not None:
        for name in names:
            key = _key(root, 'blob', revision, name)
            oid = cache.get(_key(root, 'regular-path', revision, name))
            content_key = _key(root, 'blob-object', oid)
            if key not in cache and oid and content_key in cache:
                cache[key] = cache[content_key]
    missing = [name for name in names if cache is None or _key(root, 'blob', revision, name) not in cache]
    values = _batch_blobs(root, revision, missing) if missing else {}
    if cache is not None:
        for name, value in values.items():
            cache[_key(root, 'blob', revision, name)] = value
            oid = cache.get(_key(root, 'regular-path', revision, name))
            if oid:
                cache[_key(root, 'blob-object', oid)] = value
        return {name: cache[_key(root, 'blob', revision, name)] for name in names}
    return values


def paths(root, ref, directory):
    cache = _OBJECT_CACHE.get()
    key = _key(root, 'paths', ref, directory)
    immutable = cache is not None and _native_oid(root, ref)
    if cache is not None and immutable and key in cache:
        return list(cache[key])
    output = git(root, 'ls-tree', '-r', '--name-only', '-z', ref, '--', directory)
    result = sorted(filter(None, output.split('\0')))
    if cache is not None and immutable:
        cache[key] = tuple(result)
    return result


def _ancestor_key(root, before, after, cache):
    if cache is not None and _native_oid(root, before) and _native_oid(root, after):
        return _key(root, 'ancestor', before, after)
    return None


def ancestor(root, before, after):
    cache = _OBJECT_CACHE.get()
    key = _ancestor_key(root, before, after, cache)
    if cache is not None and key is not None and key in cache:
        return True
    try:
        git(root, 'merge-base', '--is-ancestor', before, after)
        if cache is not None and key is not None:
            cache[key] = True
        return True
    except TaskError:
        return False


def _relative_parts(relative):
    parts = PurePosixPath(relative).parts
    if not parts or relative.startswith('/') or any(p in ('.', '..') for p in parts):
        raise TaskError('TASK_PATH: exact relative path required')
    if any(c in relative for c in '\\:\0'):
        raise TaskError('TASK_PATH: invalid path')
    return parts


def safe_path(root, relative):
    parts = _relative_parts(relative)
    path = Path(root).joinpath(*parts)
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise TaskError('TASK_PATH: path escapes repository')
    if any(p.is_symlink() for p in (path, *path.parents) if p != Path(root).parent):
        raise TaskError('TASK_PATH: symlinks are not supported')
    return path


def _regular_paths(output):
    records = {}
    for record in filter(None, output.split('\0')):
        header, separator, path = record.partition('\t')
        fields = header.split()
        if (not separator or path in records or len(fields) != 3
                or fields[0] not in ('100644', '100755') or fields[1] != 'blob'
                or not valid_sha(fields[2])):
            raise TaskError('TASK_PATH: expected a regular Git blob: ' + path)
        records[path] = fields[2]
    return records


def _committed_paths(root, revision, names):
    for name in names:
        _relative_parts(name)
    revision = revision if _native_oid(root, revision) else commit_sha(root, revision)
    cache = _OBJECT_CACHE.get()
    missing = [name for name in names
               if cache is None or _key(root, 'regular-path', revision, name) not in cache]
    if not missing:
        return
    records = _regular_paths(git(root, 'ls-tree', '-z', revision, '--', *missing))
    if set(records) != set(missing):
        raise TaskError('TASK_PATH: missing regular Git file')
    if cache is not None:
        for name in missing:
            oid = records[name]
            cache[_key(root, 'regular-path', revision, name)] = oid
            content_key = _key(root, 'blob', revision, name)
            if content_key in cache:
                cache[_key(root, 'blob-object', oid)] = cache[content_key]


def _metadata_paths(root, data, metadata, revision, committed_only):
    if committed_only:
        names = (data['contract'], metadata['tests'], metadata['target'])
        for ref in (data['approved_ref'], revision):
            _committed_paths(root, ref, names)
            if _OBJECT_CACHE.get() is not None:
                blobs(root, ref, names[:2])


def _artifact_path(root, relative, committed_only):
    if not committed_only:
        safe_path(root, relative)


def read_nodes(root, ref='main'):
    with object_cache():
        return _read_nodes(root, ref)


def _read_nodes(root, ref):
    revision = commit_sha(root, ref)
    records = {}
    names = [name for name in paths(root, revision, 'knowledge/tasks')
             if name.endswith('.md') and PurePosixPath(name).name != 'index.md']
    contents = blobs(root, revision, names)
    for name in names:
        data, body = parse_task(contents[name], name)
        if name != task_path(data['task_id']):
            raise TaskError('TASK_PATH: nested task records are unsupported')
        records[data['task_id']] = (data, body)
    return records


def read_tasks(root, ref='main'):
    return {key: pair[0] for key, pair in read_nodes(root, ref).items()}


def history(root, task_id):
    with object_cache():
        return _history(root, task_id)


def _history(root, task_id):
    path = task_path(task_id)
    if task_id not in read_tasks(root):
        raise TaskError('TASK_MISSING: ' + task_id)
    commits = git(root, 'log', '--topo-order', '--reverse', '--format=%H', 'main', '--', path)
    result = []
    for revision in commits.splitlines():
        data, _ = parse_task(blob(root, revision, path), path)
        result.append({'commit': revision, 'status': data['status'], 'reason': data['reason']})
    return result


def _clean_main(root, expected=None):
    actual = Path(git(root, 'rev-parse', '--show-toplevel')).resolve()
    if actual != root or git(root, 'branch', '--show-current') != 'main':
        raise TaskError('TASK_MAIN: run mutations from the repository root on main')
    if git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise TaskError('TASK_DIRTY: preserve unrelated changes; commit or stash them first')
    head = commit_sha(root, 'HEAD')
    if expected and head != expected:
        raise TaskError('TASK_RACE: HEAD changed during the operation')
    return head


@contextmanager
def _lock(root):
    directory = Path(git(root, 'rev-parse', '--git-common-dir'))
    lock = (root / directory).resolve() / 'kdd-tasks.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise TaskError('TASK_LOCK: another coordinator owns the task lock') from exc
    try:
        os.write(descriptor, str(os.getpid()).encode('ascii'))
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def contract_metadata(root, data, revision, *, committed_only=False):
    approved = data['approved_ref']
    if not valid_sha(approved) or not ancestor(root, approved, revision):
        raise TaskError('TASK_APPROVAL: supply an explicit approved ancestor SHA')
    original = blob(root, approved, data['contract'])
    metadata, _ = parse_frontmatter(original)
    if not isinstance(metadata, dict) or metadata.get('type') != 'Task Contract':
        raise TaskError('TASK_CONTRACT: approved artifact is not a Task Contract')
    required = ('target', 'tests', 'test_command', 'tests_sha256')
    if not all(isinstance(metadata.get(k), str) and metadata[k] for k in required):
        raise TaskError('TASK_CONTRACT: approved contract has invalid oracle metadata')
    _metadata_paths(root, data, metadata, revision, committed_only)
    for path in (data['contract'], metadata['tests']):
        _artifact_path(root, path, committed_only)
        if proof.normalized(blob(root, revision, path)) != proof.normalized(blob(root, approved, path)):
            raise TaskError('TASK_APPROVAL: contract or oracle differs from approved reference')
    if proof.digest(proof.normalized(blob(root, revision, metadata['tests']))) != metadata.get('tests_sha256'):
        raise TaskError('TASK_ORACLE: approved oracle seal is invalid')
    _artifact_path(root, metadata['target'], committed_only)
    return metadata


def _ready(root, task, options, head):
    task['approved_ref'] = options.get('approved_ref', '')
    contract_metadata(root, task, head)
    findings = validate_file(str(root / task['contract']), repo_root=str(root))
    if any(f.level == 'ERROR' for f in findings):
        raise TaskError('TASK_CONTRACT: ' + '; '.join(map(str, findings)))


def _start(root, task, options, head):
    contract_metadata(root, task, head)
    task['assignee'] = options.get('assignee', '')
    branch = task['branch']
    exists = branch in git(root, 'for-each-ref', '--format=%(refname:short)', 'refs/heads/').splitlines()
    if task['branch_base']:
        if not exists or not ancestor(root, task['branch_base'], commit_sha(root, branch)):
            raise TaskError('TASK_BRANCH: original task branch is missing or rewritten')
        return None
    if exists:
        raise TaskError('TASK_BRANCH: refusing to replace an existing branch')
    task['branch_base'] = head
    return branch


def _finish(root, task, options, head):
    tip = commit_sha(root, task['branch'])
    if tip == task['branch_base'] or not ancestor(root, task['branch_base'], tip):
        raise TaskError('TASK_INTEGRATION: task branch has no preserved implementation')
    if not ancestor(root, tip, head):
        raise TaskError('TASK_INTEGRATION: integrate the task branch into main first')
    metadata = contract_metadata(root, task, head)
    report = proof.execute(metadata, root, options.get('timeout', 120))
    _clean_main(root, head)
    report.update(schema_version=1, task_id=task['task_id'], tested_commit=head,
                  branch_tip=tip, approved_ref=task['approved_ref'],
                  contract_sha256=proof.digest(proof.normalized(blob(root, head, task['contract']))),
                  target_sha256=proof.digest(proof.normalized(blob(root, head, metadata['target']))),
                  oracle_sha256=proof.digest(proof.normalized(blob(root, head, metadata['tests']))))
    content = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    task.update(verified_ref=head, evidence='docs/task-evidence/{}-{}.json'.format(task['task_id'], head),
                evidence_sha256=proof.digest(content))
    if safe_path(root, task['evidence']).exists():
        raise TaskError('TASK_EVIDENCE: refusing to overwrite an existing artifact')
    return {task['evidence']: content.encode('utf-8')}


def _prepare(root, operation, task_id, options):
    from validate_tasks import validate_snapshot
    head = _clean_main(root)
    findings = validate_snapshot(root, head)
    if findings:
        raise TaskError('; '.join(findings))
    nodes = read_nodes(root)
    if operation == 'create':
        if task_id in nodes:
            raise TaskError('TASK_EXISTS: ' + task_id)
        task = new_task(task_id, options['title'], options['description'],
                        options['contract'], options.get('depends_on', []))
        blob(root, head, task['contract'])
        return head, nodes, None, task, None
    if task_id not in nodes:
        raise TaskError('TASK_MISSING: ' + task_id)
    before, body = nodes[task_id]
    return head, nodes, before, dict(before), body


def _changes(root, operation, task, options, head):
    statuses = {'ready': 'ready', 'start': 'in_progress', 'block': 'needs_human_input',
                'resume': 'ready', 'finish': 'done'}
    task['status'] = statuses.get(operation, 'backlog')
    task['reason'] = options.get('reason') or {'create': 'Created', 'ready': 'Contract approved',
                                            'start': 'Implementation started', 'finish': 'Oracle verified'}.get(operation, '')
    extra, branch = {}, None
    if operation == 'ready':
        _ready(root, task, options, head)
    if operation == 'start':
        branch = _start(root, task, options, head)
    if operation == 'finish':
        extra = _finish(root, task, options, head)
    return extra, branch


def _restore(root, backups):
    git(root, 'reset', '-q', 'HEAD', '--', *backups)
    for name, content in backups.items():
        path = safe_path(root, name)
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def _publish(root, head, changes, branch, message):
    backups = {name: safe_path(root, name).read_bytes() if safe_path(root, name).exists() else None
               for name in changes}
    created = False
    try:
        _clean_main(root, head)
        if branch:
            git(root, 'branch', branch, head)
            created = True
        for name, content in changes.items():
            path = safe_path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        git(root, 'add', '--', *changes)
        git(root, 'commit', '-m', message, '--only', '--', *changes)
        return commit_sha(root, 'HEAD')
    except BaseException:
        if commit_sha(root, 'HEAD') == head:
            _restore(root, backups)
            if created and commit_sha(root, branch) == head:
                git(root, 'branch', '-d', branch)
        raise


def mutate(repo_root, operation, task_id, options):
    task_path(task_id)
    if operation not in ('create', 'ready', 'start', 'block', 'resume', 'finish'):
        raise TaskError('TASK_OPERATION: unknown operation')
    root = Path(repo_root).resolve()
    with _lock(root), object_cache():
        head, nodes, before, task, body = _prepare(root, operation, task_id, options)
        expected = {'ready': 'backlog', 'start': 'ready', 'block': 'in_progress',
                    'resume': 'needs_human_input', 'finish': 'in_progress'}
        if before and before['status'] != expected[operation]:
            raise TaskError('TASK_TRANSITION: {} cannot {}'.format(before['status'], operation))
        extra, branch = _changes(root, operation, task, options, head)
        completed = {key for key, pair in nodes.items() if pair[0]['status'] == 'done'}
        errors = validate_transition(before, task, completed)
        if any(dep not in nodes for dep in task['depends_on']):
            errors.append('TASK_DEPENDENCIES: prerequisite task is missing')
        if errors:
            raise TaskError('; '.join(errors))
        changes = {task_path(task_id): render_task(task, body).encode('utf-8'), **extra}
        if operation == 'create':
            index = safe_path(root, 'knowledge/index.md')
            content = index.read_text(encoding='utf-8')
            if '(./tasks/)' not in content and '(tasks/)' not in content:
                changes['knowledge/index.md'] = (content.rstrip() + '\n\n- [Tasks](./tasks/)\n').encode('utf-8')
        revision = _publish(root, head, changes, branch, 'chore({}): {}'.format(task_id.lower(), operation))
        return {'commit': revision, 'task': task}
