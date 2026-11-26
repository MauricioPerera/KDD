"""Compare a sealed unittest oracle on two trusted Git commits."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from types import FunctionType, MethodType
import unittest

if __package__:
    from . import oracle_execution, process_tree, unittest_oracle_runner as identity
    from .oracle_inventory import exact_path, inventory_paths
    from .validate_contracts import _calculate_tests_hash, parse_frontmatter
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import oracle_execution
    import process_tree
    import unittest_oracle_runner as identity
    from oracle_inventory import exact_path, inventory_paths
    from validate_contracts import _calculate_tests_hash, parse_frontmatter


SCRIPT = Path(__file__).resolve()
MODES = {'100644': 0o644, '100755': 0o755}
TREE_MODE = '040000'
TEST_METHOD_DISPATCH = unittest.TestCase._callTestMethod
TEST_CASE_RUN = unittest.TestCase.run


def _snapshot_entries(root):
    paths = {}
    for path in root.rglob('*'):
        info = path.lstat()
        reparse = os.name == 'nt' and info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if stat.S_ISLNK(info.st_mode) or reparse:
            raise ValueError('Snapshot contains a link: ' + path.name)
        paths[path.relative_to(root).as_posix()] = (path, info.st_mode)
    return paths


class SnapshotReader:
    """Materialize regular blobs without Git checkout or archive transformations."""

    def __init__(self, root):
        self.root = root
        self.binary = shutil.which('git')
        if not self.binary:
            raise ValueError('Git executable is required')
        self.binary = str(Path(self.binary).resolve(strict=True))
        self.env = {key: value for key, value in os.environ.items()
                    if not key.upper().startswith('GIT_')}
        self.env.update(GIT_GRAFT_FILE=os.devnull, GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='',
                        GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        top = self.git('rev-parse', '--show-toplevel').decode('utf-8').rstrip('\r\n')
        if Path(top).resolve() != root:
            raise ValueError('--repo-root must be the root of the Git worktree')
        self.algorithm = self.git('rev-parse', '--show-object-format').decode('ascii').strip()
        self.width = {'sha1': 40, 'sha256': 64}[self.algorithm]

    def git(self, *args, data=None):
        result = subprocess.run([self.binary, '--no-replace-objects', '-C', str(self.root), *args],
                                input=data, env=self.env, capture_output=True, timeout=60)
        if result.returncode:
            raise ValueError('Git could not complete ' + args[0] + ': ' +
                             result.stderr.decode('utf-8', 'replace').strip())
        return result.stdout

    def verify_pair(self, base, candidate):
        for revision in (base, candidate):
            if not re.fullmatch('[0-9a-f]{%d}' % self.width, revision):
                raise ValueError('Both revisions must be full native commit IDs')
            resolved = self.git('rev-parse', '--verify', '--end-of-options', revision + '^{commit}')
            if resolved.strip() != revision.encode('ascii'):
                raise ValueError('Revision must identify a commit object')
        if base == candidate or self.git('rev-parse', '--is-shallow-repository').strip() != b'false':
            raise ValueError('Proof requires distinct commits in a complete history')
        self.git('merge-base', '--is-ancestor', base, candidate)

    def tree(self, revision):
        entries = {}
        folded = set()
        records = self.git('ls-tree', '-r', '-t', '-z', '--full-tree', revision).split(b'\0')
        for record in records[:-1]:
            raw, name = record.split(b'\t', 1)
            mode, kind, oid = raw.decode('ascii').split()
            name = exact_path(name.decode('utf-8'))
            key = name.casefold()
            expected_kind = 'tree' if mode == TREE_MODE else 'blob' if mode in MODES else None
            if (kind != expected_kind or key in folded
                    or any(part.casefold() == '.git' for part in name.split('/'))):
                raise ValueError('Unsupported or ambiguous Git tree entry: ' + name)
            entries[name] = (mode, oid)
            folded.add(key)
        if records[-1]:
            raise ValueError('Incomplete Git tree')
        return entries

    def blob_id(self, data):
        digest = hashlib.new(self.algorithm, b'blob %d\0' % len(data))
        digest.update(data)
        return digest.hexdigest()

    def contents(self, entries):
        oids = sorted({oid for mode, oid in entries.values() if mode != TREE_MODE})
        if not oids:
            return {}
        raw = self.git('cat-file', '--batch', data=('\n'.join(oids) + '\n').encode('ascii'))
        offset = 0
        blobs = {}
        for oid in oids:
            line, newline, _ = raw[offset:offset + 128].partition(b'\n')
            fields = line.split()
            if not newline or fields[:2] != [oid.encode('ascii'), b'blob'] or len(fields) != 3:
                raise ValueError('Invalid Git blob header')
            start = offset + len(line) + 1
            stop = start + int(fields[2])
            data = raw[start:stop]
            if raw[stop:stop + 1] != b'\n' or self.blob_id(data) != oid:
                raise ValueError('Git blob differs from the tree')
            blobs[oid] = data
            offset = stop + 1
        if offset != len(raw):
            raise ValueError('Unexpected trailing Git blob data')
        return blobs

    def materialize(self, root, entries, blobs):
        root.mkdir()
        for name, (mode, oid) in entries.items():
            path = root / name
            if mode == TREE_MODE:
                path.mkdir()
                continue
            with path.open('xb') as output:
                output.write(blobs[oid])
            if os.name != 'nt':
                path.chmod(MODES[mode])
        self.verify_copy(root, entries)

    def verify_copy(self, root, entries):
        if root.resolve(strict=True) != root:
            raise ValueError('Snapshot root changed')
        paths = _snapshot_entries(root)
        if paths.keys() != entries.keys():
            raise ValueError('Snapshot paths differ from the Git tree')
        for name, (path, flags) in paths.items():
            mode, oid = entries[name]
            if not self.matches(path, flags, mode, oid):
                raise ValueError('Snapshot differs from the Git tree: ' + name)

    def matches(self, path, flags, mode, oid):
        if mode == TREE_MODE:
            return stat.S_ISDIR(flags)
        return (stat.S_ISREG(flags) and self.blob_id(path.read_bytes()) == oid
                and (os.name == 'nt' or stat.S_IMODE(flags) == MODES[mode]))


def _contract(base, trees, slug):
    name = 'knowledge/contracts/' + slug + '.md'
    metadata, _ = parse_frontmatter((base / name).read_text(encoding='utf-8'))
    if not metadata or metadata.get('task') != slug or metadata.get('test_runner') != 'python-unittest':
        raise ValueError('Expected an explicit python-unittest contract')
    paths = [name, *inventory_paths(metadata, required=True)]
    base_tree, candidate_tree = trees
    if any(base_tree[name] != candidate_tree[name] for name in paths):
        raise ValueError('Contract or oracle differs between commits')
    seal = _calculate_tests_hash(base / metadata['tests'])
    if not seal or seal != metadata.get('tests_sha256'):
        raise ValueError('Primary oracle seal does not match')
    _, _, files = oracle_execution._invocation(metadata, base)
    checksums = {path: hashlib.sha256((base / path).read_bytes()).hexdigest() for path in paths[1:]}
    return files, oracle_execution.declared_timeout(metadata), checksums


def _plain_method(test, method, inventory):
    if type(method) is not MethodType or method.__self__ is not test:
        return False
    function = method.__func__
    return (isinstance(function, FunctionType)
            and not (function.__closure__ or function.__defaults__ or function.__kwdefaults__)
            and not hasattr(function, '__wrapped__')
            and Path(function.__code__.co_filename).resolve() in inventory)


class ProofResult(unittest.TestResult):
    def __init__(self, root, selection):
        super().__init__()
        self.root = root
        self.files = {root / path for path in selection['files']}
        self.inventory = {root / path for path in selection['inventory']}
        self.seen = set()
        self.ids = set()
        self.fingerprints = {}
        self.assertions = set()
        self.passed = set()
        self.restore = {}
        self.unsupported = False
        self.origins = identity.runtime_origins()

    def startTest(self, test):
        super().startTest(test)
        source = Path(identity.source_path(test))
        label = unittest.TestCase.id(test)
        invoke = test._callTestMethod
        if source not in self.files or label in self.ids:
            self.unsupported = True
            return
        self.ids.add(label)
        if (getattr(invoke, '__func__', None) is not TEST_METHOD_DISPATCH
                or getattr(test.run, '__func__', None) is not TEST_CASE_RUN):
            self.unsupported = True
            return

        def record_and_invoke(method):
            if _plain_method(test, method, self.inventory):
                self.seen.add(source)
                self.fingerprints[label] = identity.bound_method_fingerprint(method, self.root, self.origins)
            else:
                self.unsupported = True
            return invoke(method)

        self.restore[id(test)] = vars(test).get('_callTestMethod')
        test._callTestMethod = record_and_invoke

    def stopTest(self, test):
        if id(test) in self.restore:
            previous = self.restore.pop(id(test))
            if previous is None:
                vars(test).pop('_callTestMethod', None)
            else:
                test._callTestMethod = previous
        super().stopTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.add(unittest.TestCase.id(test))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        if err[0] is AssertionError:
            self.assertions.add(unittest.TestCase.id(test))
        else:
            self.unsupported = True

    def addSubTest(self, test, subtest, err):
        self.unsupported = True
        super().addSubTest(test, subtest, err)

    def receipt(self):
        status = 'inconclusive'
        if (not self.unsupported and not self.errors and not self.skipped
                and not self.expectedFailures and not self.unexpectedSuccesses
                and self.seen == self.files and self.ids
                and self.ids == self.fingerprints.keys() == (self.passed | self.assertions)):
            status = 'assertion_failure' if self.assertions else 'passed'
        return dict(status=status, case_ids=sorted(self.ids), failed_cases=sorted(self.assertions),
                    case_fingerprints=self.fingerprints)


def _record(output, selection_json):
    root = Path.cwd().resolve()
    sys.path.insert(0, str(root))
    selection = json.loads(selection_json)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames([file[:-3].replace('/', '.') for file in selection['files']])
    result = ProofResult(root, selection)
    suite.run(result)
    Path(output).write_text(json.dumps(result.receipt()), encoding='utf-8')
    return 0


def _execute_attempt(root, selection, timeout):
    output = root.parent / 'result.json'
    command = [sys.executable, '-I', '-B', '-X', 'utf8',
               '-X', 'pycache_prefix=' + str(root.parent / 'cache'),
               SCRIPT, '--record', output, json.dumps(selection)]
    completed = process_tree.run(command, cwd=root, timeout=timeout, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if completed.returncode:
        return dict(reason='runner_exit', exit_code=completed.returncode)
    return json.loads(output.read_text(encoding='utf-8'))


def _attempt(copy, invocation, checksums, verify_copy):
    root, side, number, tree = copy
    item = dict(side=side, number=number, status='inconclusive',
                case_ids=[], failed_cases=[], case_fingerprints={})
    try:
        verify_copy(root, tree)
    except (OSError, ValueError):
        return dict(item, reason='snapshot_changed')
    selection, timeout = invocation
    try:
        item.update(_execute_attempt(root, selection, timeout))
    except subprocess.TimeoutExpired:
        return dict(item, reason='timeout')
    except (OSError, ValueError):
        return dict(item, reason='runner_result_unavailable')
    try:
        intact = all(hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
                     for path, digest in checksums.items())
    except OSError:
        intact = False
    return item if intact else dict(item, status='inconclusive', reason='oracle_changed')


def _proven(attempts, expected):
    first = attempts[0]['case_fingerprints']
    return bool(first) and all(
        item['case_fingerprints'] == first and
        (item['status'], item['failed_cases']) ==
        (('assertion_failure', expected) if item['side'] == 'base' else ('passed', []))
        for item in attempts)


def _external_temp(root):
    # tempfile.gettempdir() probes the directory with a write before returning.
    configured = next((os.environ[key] for key in ('TMPDIR', 'TEMP', 'TMP') if os.environ.get(key)), None)
    default = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Temp'
    path = Path(configured or (default if os.name == 'nt' else '/tmp')).resolve(strict=True)
    if not path.is_dir() or path.is_relative_to(root):
        raise ValueError('Temporary directory must be outside the source checkout')
    return path


def _prepare_copies(repository, options, directory):
    copies, trees = [], []
    for side, revision in (('base', options.base), ('candidate', options.candidate)):
        tree = repository.tree(revision)
        trees.append(tree)
        blobs = repository.contents(tree)
        for number in (1, 2):
            attempt_dir = directory / ('%s-%d' % (side, number))
            attempt_dir.mkdir()
            copy = attempt_dir / 'worktree'
            repository.materialize(copy, tree, blobs)
            copies.append((copy, side, number, tree))
    return copies, trees


def _compare(options, report):
    expected = sorted(set(options.expect_failure))
    if (len(expected) != len(options.expect_failure) or not all(value.strip() for value in expected)
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', options.contract)):
        raise ValueError('Expected a contract slug and distinct nonempty failure IDs')
    root = options.repo_root.resolve(strict=True)
    repository = SnapshotReader(root)
    repository.verify_pair(options.base, options.candidate)
    with tempfile.TemporaryDirectory(prefix='kdd-proof-', dir=_external_temp(root)) as directory:
        copies, trees = _prepare_copies(repository, options, Path(directory))
        files, timeout, checksums = _contract(copies[0][0], trees, options.contract)
        report['oracle_sha256'] = checksums
        selection = dict(files=files, inventory=list(checksums))
        contract_path = 'knowledge/contracts/' + options.contract + '.md'
        contract_digest = hashlib.sha256((copies[0][0] / contract_path).read_bytes()).hexdigest()
        sealed = {**checksums, contract_path: contract_digest}
        for copy in copies:
            report['attempts'].append(_attempt(copy, (selection, timeout), sealed, repository.verify_copy))
    passed = _proven(report['attempts'], expected)
    report['status'] = 'proven' if passed else 'inconclusive'
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--expect-failure', required=True, action='append')
    options = parser.parse_args(argv)
    report = dict(schema_version=1, base_commit=options.base, candidate_commit=options.candidate,
                  status='invalid', oracle_sha256={}, attempts=[])
    try:
        code = _compare(options, report)
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        report['error'] = str(exc)
        if report['attempts']:
            report['status'] = 'inconclusive'
        code = 1 if report['attempts'] else 2
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == '__main__':
    if sys.argv[1:2] == ['--record']:
        raise SystemExit(_record(*sys.argv[2:]))
    raise SystemExit(main())
