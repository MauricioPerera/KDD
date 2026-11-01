"""Official task state is committed on main; task branches contain the work."""
from contextlib import contextmanager
from contextvars import ContextVar
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
from typing import NamedTuple

import task_evidence as proof
from task_model import TaskError, new_task, parse_task, render_task, task_path, valid_sha, validate_transition
from validate_contracts import parse_frontmatter, validate_file


_OBJECT_CACHE = ContextVar('kdd_git_objects', default=None)


class _MutationContext(NamedTuple):
    head: str
    options: dict


class _PerimeterContext(NamedTuple):
    base: str
    tip: str
    tested: str


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


def _commit_with_uninitialized_format(root, ref, cache, key):
    format_key = _key(root, 'object-format', '')
    try:
        fields = git(root, 'rev-parse', '--show-object-format', '--verify',
                     '--end-of-options', ref + '^{commit}').splitlines()
    except TaskError:
        fields = []
    if (len(fields) == 2 and valid_sha(fields[1])
            and len(fields[1]) == {'sha1': 40, 'sha256': 64}.get(fields[0])):
        cache[format_key] = fields[0]
        cache[_key(root, 'commit', fields[1])] = fields[1]
        if valid_sha(ref) and len(ref) == len(fields[1]):
            cache[key] = fields[1]
        return fields[1]
    return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')


def commit_sha(root, ref):
    cache = _OBJECT_CACHE.get()
    if cache is None:
        return git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    key = _key(root, 'commit', ref)
    if _key(root, 'object-format', '') not in cache:
        return _commit_with_uninitialized_format(root, ref, cache, key)
    immutable = _native_oid(root, ref)
    if cache is not None and immutable and key in cache:
        return cache[key]
    revision = git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}')
    if cache is not None:
        cache[_key(root, 'commit', revision)] = revision
        if immutable:
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


def _reuse_cached_blob_objects(root, revision, names, cache):
    for name in names:
        key = _key(root, 'blob', revision, name)
        oid = (cache.get(_key(root, 'regular-path', revision, name))
               or cache.get(_key(root, 'blob-path', revision, name)))
        content_key = _key(root, 'blob-object', oid)
        if key not in cache and oid and content_key in cache:
            cache[key] = cache[content_key]


def _remember_blob_objects(root, revision, values, cache):
    for name, value in values.items():
        cache[_key(root, 'blob', revision, name)] = value
        oid = (cache.get(_key(root, 'regular-path', revision, name))
               or cache.get(_key(root, 'blob-path', revision, name)))
        if oid:
            cache[_key(root, 'blob-object', oid)] = value


def blobs(root, ref, names):
    if not names:
        return {}
    revision = ref if _native_oid(root, ref) else commit_sha(root, ref)
    cache = _OBJECT_CACHE.get()
    names = list(dict.fromkeys(names))
    if cache is not None:
        _reuse_cached_blob_objects(root, revision, names, cache)
    missing = [name for name in names if cache is None or _key(root, 'blob', revision, name) not in cache]
    values = _batch_blobs(root, revision, missing) if missing else {}
    if cache is not None:
        _remember_blob_objects(root, revision, values, cache)
        return {name: cache[_key(root, 'blob', revision, name)] for name in names}
    return values


def _cacheable_git_path(name):
    try:
        _relative_parts(name)
    except TaskError:
        return False
    return PurePosixPath(name).as_posix() == name and not any(c in name for c in '\r\n')


def _structured_directory(directory):
    return (isinstance(directory, str) and _cacheable_git_path(directory)
            and not directory[0].isspace())


def _object_paths(root, revision, output):
    names, objects = [], {}
    for record in filter(None, output.split('\0')):
        header, separator, name = record.partition('\t')
        fields = header.split()
        if not separator or len(fields) != 3 or not valid_sha(fields[2]):
            raise TaskError('TASK_GIT: invalid tree inventory')
        if not name:
            continue
        names.append(name)
        if name in objects:
            objects[name] = None
        else:
            objects[name] = fields[2] if fields[1] == 'blob' else None
    cache = _OBJECT_CACHE.get()
    # Inventory OIDs identify bytes; they do not certify regular file modes.
    for name, oid in objects.items():
        if oid and _cacheable_git_path(name):
            cache[_key(root, 'blob-path', revision, name)] = oid
    return sorted(names)


def paths(root, ref, directory):
    cache = _OBJECT_CACHE.get()
    key = _key(root, 'paths', ref, directory)
    immutable = cache is not None and _native_oid(root, ref)
    if cache is not None and immutable and key in cache:
        return list(cache[key])
    structured = immutable and _structured_directory(directory)
    options = [] if structured else ['--name-only']
    output = git(root, 'ls-tree', '-r', *options, '-z', ref, '--', directory)
    result = (_object_paths(root, ref, output) if structured else
              sorted(filter(None, output.split('\0'))))
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
    component = Path(root)
    for index, part in enumerate(parts):
        component = component / part
        try:
            info = component.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise TaskError('TASK_PATH: symlinks and reparse points are not supported')
        if index < len(parts) - 1:
            if not stat.S_ISDIR(info.st_mode):
                raise TaskError('TASK_PATH: ancestor must be a directory')
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise TaskError('TASK_PATH: expected a regular file with one hardlink')
    if not path.resolve().is_relative_to(Path(root).resolve()):
        raise TaskError('TASK_PATH: path escapes repository')
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


def _metadata_requests(root, revisions, names, cache):
    requests = []
    for ref in revisions:
        _reuse_cached_blob_objects(root, ref, names[:2], cache)
        for name in names:
            content = name in names[:2] and _key(root, 'blob', ref, name) not in cache
            regular = _key(root, 'regular-path', ref, name) not in cache
            if regular or content:
                requests.append((ref, name, content))
    return requests


def _metadata_record(output, offset, request):
    end = output.find(b'\n', offset)
    if end < 0:
        raise TaskError('TASK_GIT: truncated metadata header')
    header = output[offset:end]
    if header == (request[0] + ':' + request[1] + ' missing').encode('utf-8'):
        return None, end + 1
    fields = header.split()
    if (len(fields) != 4 or not valid_sha(fields[0].decode('ascii'))
            or not fields[2].isdigit()):
        raise TaskError('TASK_GIT: invalid metadata header')
    if fields[1] != b'blob' or fields[3] not in (b'100644', b'100755'):
        return None, end + 1
    start, size = end + 1, int(fields[2])
    body = None
    if request[2]:
        if output[start + size:start + size + 1] != b'\n':
            raise TaskError('TASK_GIT: truncated metadata content')
        body, start = output[start:start + size], start + size + 1
    return (*request[:2], fields[0].decode('ascii'), body), start


def _metadata_unsupported(stderr):
    first = stderr.splitlines()[0] if stderr.splitlines() else b''
    return (first.endswith(b'unknown format element: objectmode') or
            (b'unknown option' in first and b'batch-command' in first))


def _read_metadata(root, requests):
    commands = [('contents ' if content else 'info ') + ref + ':' + name
                for ref, name, content in requests]
    try:
        result = subprocess.run(['git', '-C', str(root), 'cat-file',
            '--batch-command=%(objectname) %(objecttype) %(objectsize) %(objectmode)', '--buffer'],
            input=('\n'.join(commands) + '\nflush\n').encode('utf-8'),
            capture_output=True, timeout=30, check=False)
        if result.returncode:
            if _metadata_unsupported(result.stderr):
                return False
            raise TaskError('TASK_GIT: ' + result.stderr.decode('utf-8', errors='replace').strip())
        records, offset = [], 0
        for request in requests:
            record, offset = _metadata_record(result.stdout, offset, request)
            if record is None:
                return None
            records.append(record)
        if offset != len(result.stdout):
            raise TaskError('TASK_GIT: unexpected metadata output')
        return records
    except (OSError, UnicodeError, subprocess.SubprocessError) as error:
        raise TaskError('TASK_GIT: ' + str(error)) from error


def _store_metadata(root, cache, records):
    # Decode everything before extending the cache. Failed/ambiguous batches
    # leave the original serial checks responsible for their first error.
    try:
        values = [(ref, name, oid, None if body is None else
                   body.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'))
                  for ref, name, oid, body in records]
    except UnicodeError as error:
        raise TaskError('TASK_GIT: ' + str(error)) from error
    for ref, name, oid, content in values:
        cache[_key(root, 'regular-path', ref, name)] = oid
        if content is None:
            content = cache.get(_key(root, 'blob', ref, name))
        if content is not None:
            _remember_blob_objects(root, ref, {name: content}, cache)


def _prefetch_metadata(root, revisions, names):
    cache = _OBJECT_CACHE.get()
    support = _key(root, 'metadata-mode-support', '')
    if cache is None or cache.get(support) is False:
        return False
    if any(PurePosixPath(name).as_posix() != name or
           any(c in name for c in '\r\n\0') for name in names):
        return False
    for name in names:
        _relative_parts(name)
    if not all(_native_oid(root, ref) for ref in revisions):
        return False
    requests = _metadata_requests(root, revisions, names, cache)
    if not requests:
        return True
    records = _read_metadata(root, requests)
    if records is False:
        cache[support] = False
    if records is False or records is None:
        return False
    _store_metadata(root, cache, records)
    return True


def _metadata_paths(root, data, metadata, revision):
    names = (data['contract'], metadata['tests'], metadata['target'])
    revisions = (data['approved_ref'], revision)
    if _prefetch_metadata(root, revisions, names):
        return
    for ref in revisions:
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
    if actual != root:
        raise TaskError('TASK_MAIN: run mutations from the repository root on main')
    records = git(root, 'status', '--porcelain=v2', '--branch', '-z',
                  '--untracked-files=all').split('\0')
    headers = {}
    dirty = False
    for record in filter(None, records):
        if not dirty and record.startswith('# '):
            key, separator, value = record[2:].partition(' ')
            if not separator or key in headers:
                raise TaskError('TASK_MAIN: invalid Git branch metadata')
            headers[key] = value
        else:
            dirty = True
    head = headers.get('branch.oid', '')
    if headers.get('branch.head') != 'main' or not valid_sha(head):
        raise TaskError('TASK_MAIN: run mutations from an existing main commit')
    if dirty:
        raise TaskError('TASK_DIRTY: preserve unrelated changes; commit or stash them first')
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


def _require_approved_ancestor(root, approved, revision):
    try:
        identity = commit_sha(root, approved) if valid_sha(approved) else None
    except TaskError:
        identity = None
    if not valid_sha(approved) or identity != approved or not ancestor(root, approved, revision):
        raise TaskError('TASK_APPROVAL: supply an explicit approved ancestor SHA')


def _require_valid_contract(root, name):
    findings = validate_file(str(root / name), repo_root=str(root))
    if any(f.level == 'ERROR' for f in findings):
        raise TaskError('TASK_CONTRACT: ' + '; '.join(map(str, findings)))


def _approved_contract_schema(root, data, metadata):
    cache = _OBJECT_CACHE.get()
    approved = data['approved_ref']
    key = _key(root, 'contract-schema', approved, data['contract'])
    if cache is not None and key in cache:
        return
    scratch = Path(tempfile.gettempdir()).resolve()
    if scratch.is_relative_to(Path(root).resolve()):
        raise TaskError('TASK_PATH: contract validation requires external scratch space')
    # Target presence/mode was checked against Git. The full validator reads
    # only its presence; preserve the real contract and sealed oracle bytes.
    artifacts = {metadata['target']: '',
                 data['contract']: blob(root, approved, data['contract']),
                 metadata['tests']: blob(root, approved, metadata['tests'])}
    with tempfile.TemporaryDirectory(prefix='kdd-contract-schema-', dir=scratch) as directory:
        destination = Path(directory)
        for name, content in artifacts.items():
            path = destination.joinpath(*_relative_parts(name))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8', newline='\n')
        _require_valid_contract(destination, data['contract'])
    if cache is not None:
        cache[key] = True


def _live_contract(root, data, metadata):
    for name in (data['contract'], metadata['tests']):
        try:
            content = safe_path(root, name).read_text(encoding='utf-8')
        except OSError as error:
            raise TaskError('TASK_CONTRACT: required artifact is unavailable: ' + name) from error
        if proof.normalized(content) != proof.normalized(blob(root, data['approved_ref'], name)):
            raise TaskError('TASK_APPROVAL: checkout contract or oracle differs from approval')
    _require_valid_contract(root, data['contract'])


def _require_runner(metadata, live):
    argv, _ = proof.invocation(metadata)
    if live and shutil.which(argv[0]) is None:
        raise TaskError('TASK_RUNNER: required executable is unavailable: ' + argv[0])


def contract_metadata(root, data, revision, *, committed_only=False):
    approved = data['approved_ref']
    _require_approved_ancestor(root, approved, revision)
    original = blob(root, approved, data['contract'])
    metadata, _ = parse_frontmatter(original)
    if not isinstance(metadata, dict) or metadata.get('type') != 'Task Contract':
        raise TaskError('TASK_CONTRACT: approved artifact is not a Task Contract')
    required = ('target', 'tests', 'test_command', 'tests_sha256')
    if not all(isinstance(metadata.get(k), str) and metadata[k] for k in required):
        raise TaskError('TASK_CONTRACT: approved contract has invalid oracle metadata')
    _metadata_paths(root, data, metadata, revision)
    for path in (data['contract'], metadata['tests']):
        _artifact_path(root, path, committed_only)
        if proof.normalized(blob(root, revision, path)) != proof.normalized(blob(root, approved, path)):
            raise TaskError('TASK_APPROVAL: contract or oracle differs from approved reference')
    if proof.digest(proof.normalized(blob(root, revision, metadata['tests']))) != metadata.get('tests_sha256'):
        raise TaskError('TASK_ORACLE: approved oracle seal is invalid')
    _artifact_path(root, metadata['target'], committed_only)
    _approved_contract_schema(root, data, metadata)
    if not committed_only:
        _live_contract(root, data, metadata)
    _require_runner(metadata, not committed_only)
    return metadata


def _ready(root, task, options, head):
    task['approved_ref'] = options.get('approved_ref', '')
    contract_metadata(root, task, head)


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


def _perimeter_refs(root, references):
    for reference in references:
        if not _native_oid(root, reference) or commit_sha(root, reference) != reference:
            raise TaskError('TASK_PERIMETER: canonical commit identities are required')


def _perimeter_rows(root, bounds, first_parent=False):
    tip, base = bounds
    cache = _OBJECT_CACHE.get()
    key = _key(root, 'perimeter-rows', tip, base, first_parent)
    if cache is not None and key in cache:
        return cache[key]
    # This bounded DAG walk is separate from the journal's first-parent
    # rev-list. Read all parent identities in one call, never per commit.
    args = ['log', '--reverse', '--topo-order', '--format=%H %P']
    if first_parent:
        args.append('--first-parent')
    rows = tuple(tuple(line.split()) for line in git(root, *args, tip, '^' + base).splitlines())
    if cache is not None:
        cache[key] = rows
    return rows


def _perimeter_diff(root, parent, revision):
    args = ('diff', '--no-ext-diff', '--no-textconv', '--no-renames',
            '--name-only', '-z', parent, revision, '--')
    return set(filter(None, _output(root, args).split('\0')))


def _perimeter_changes(root, rows):
    changed = set()
    for row in rows:
        if len(row) != 2:
            raise TaskError('TASK_PERIMETER: ambiguous implementation merge ' + row[0])
        changed.update(_perimeter_diff(root, row[1], row[0]))
    return changed


def _perimeter_incoming(root, merge, owned):
    selected = []
    for side in merge[2:]:
        for row in _perimeter_rows(root, (side, merge[1])):
            parents = row[1:]
            if row[0] in owned or (parents and parents[0] in owned):
                if len(row) != 2:
                    raise TaskError('TASK_PERIMETER: ambiguous implementation merge ' + row[0])
                owned.add(row[0])
                selected.append(row)
            elif any(parent in owned for parent in parents[1:]):
                raise TaskError('TASK_PERIMETER: ambiguous integration lineage ' + row[0])
    if selected and len(merge) != 3:
        raise TaskError('TASK_PERIMETER: ambiguous integration merge ' + merge[0])
    return selected


def _perimeter_paths(root, context):
    rows = _perimeter_rows(root, (context.tip, context.base))
    owned = {row[0] for row in rows}
    if not owned:
        raise TaskError('TASK_PERIMETER: implementation history is empty')
    changed = _perimeter_changes(root, rows)
    for merge in _perimeter_rows(root, (context.tested, context.base), first_parent=True):
        if len(merge) > 2:
            incoming = _perimeter_incoming(root, merge, owned)
            if incoming:
                changed.update(_perimeter_changes(root, incoming))
                changed.update(_perimeter_diff(root, merge[1], merge[0]))
    return changed


def _perimeter_check(metadata, contract, changed):
    patterns = metadata.get('touch_only')
    if (not isinstance(patterns, list) or not patterns
            or any(not isinstance(item, str) or not item for item in patterns)):
        raise TaskError('TASK_PERIMETER: approved touch_only must be a nonempty list')
    protected = {contract}
    if metadata['tests'] != metadata['target']:
        protected.add(metadata['tests'])
    outside = sorted(path for path in changed
                     if path in protected or not any(fnmatch.fnmatch(path, p) for p in patterns))
    if outside:
        raise TaskError('TASK_PERIMETER: paths outside approved scope: ' + json.dumps(outside))


def task_perimeter(root, task, revision, branch_tip):
    context = _PerimeterContext(task['branch_base'], branch_tip, revision)
    key = _key(root, 'task-perimeter', revision, task['contract'], task['approved_ref'],
               context.base, context.tip)
    cache = _OBJECT_CACHE.get()
    if cache is not None and key in cache:
        changed = cache[key]
    else:
        _perimeter_refs(root, (task['approved_ref'], *context))
        if not ancestor(root, context.base, context.tip) or not ancestor(root, context.tip, revision):
            raise TaskError('TASK_PERIMETER: implementation is not integrated from its base')
        metadata, _ = parse_frontmatter(blob(root, task['approved_ref'], task['contract']))
        changed = tuple(sorted(_perimeter_paths(root, context)))
        _perimeter_check(metadata, task['contract'], changed)
        if cache is not None:
            cache[key] = changed
    return {'schema_version': 1, 'approved_ref': task['approved_ref'],
            'branch_base': context.base, 'branch_tip': context.tip,
            'tested_commit': revision, 'paths': list(changed)}


def _finish_artifacts(root, task, metadata, revision):
    names = {task['contract'], metadata['tests'], metadata['target'], task_path(task['task_id'])}
    for name in sorted(names):
        content = safe_path(root, name).read_text(encoding='utf-8')
        if proof.normalized(content) != proof.normalized(blob(root, revision, name)):
            raise TaskError('TASK_DIRTY: checkout artifact differs from tested commit: ' + name)


def _finish(root, task, options, head):
    evidence = 'docs/task-evidence/{}-{}.json'.format(task['task_id'], head)
    if safe_path(root, evidence).exists():
        raise TaskError('TASK_EVIDENCE: refusing to overwrite an existing artifact')
    tip = commit_sha(root, task['branch'])
    if tip == task['branch_base'] or not ancestor(root, task['branch_base'], tip):
        raise TaskError('TASK_INTEGRATION: task branch has no preserved implementation')
    if not ancestor(root, tip, head):
        raise TaskError('TASK_INTEGRATION: integrate the task branch into main first')
    metadata = contract_metadata(root, task, head)
    perimeter = task_perimeter(root, task, head, tip)
    _finish_artifacts(root, task, metadata, head)
    report = proof.execute(metadata, root, options.get('timeout', 120))
    _clean_main(root, head)
    if commit_sha(root, task['branch']) != tip:
        raise TaskError('TASK_RACE: implementation tip changed during verification')
    contract_metadata(root, task, head)
    _finish_artifacts(root, task, metadata, head)
    report.update(schema_version=1, task_id=task['task_id'], tested_commit=head,
                  branch_tip=tip, approved_ref=task['approved_ref'], perimeter=perimeter,
                  contract_sha256=proof.digest(proof.normalized(blob(root, head, task['contract']))),
                  target_sha256=proof.digest(proof.normalized(blob(root, head, metadata['target']))),
                  oracle_sha256=proof.digest(proof.normalized(blob(root, head, metadata['tests']))))
    content = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2) + '\n'
    task.update(verified_ref=head, evidence=evidence,
                evidence_sha256=proof.digest(content))
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


def _changes(root, operation, task, context):
    options, head = context.options, context.head
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
    paths = {name: safe_path(root, name) for name in backups}
    git(root, 'reset', '-q', 'HEAD', '--', *backups)
    for name, content in backups.items():
        path = paths[name]
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def _publish(root, head, changes, publication):
    branch, message = publication
    paths = {name: safe_path(root, name) for name in changes}
    backups = {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}
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
        safe_path(root, task_path(task_id))
        if operation == 'create':
            safe_path(root, 'knowledge/index.md')
        extra, branch = _changes(root, operation, task, _MutationContext(head, options))
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
        publication = (branch, 'chore({}): {}'.format(task_id.lower(), operation))
        revision = _publish(root, head, changes, publication)
        return {'commit': revision, 'task': task}
