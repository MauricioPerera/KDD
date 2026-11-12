"""Trusted unittest recorder invoked by oracle_execution in an isolated Python."""
from functools import lru_cache, partial
import hashlib
import inspect
import json
import marshal
from pathlib import Path
import sys
import sysconfig
from types import CodeType, FunctionType, MethodType
import unittest


def source_path(test):
    return str(Path(inspect.getfile(type(test))).resolve())


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.files = {}

    def _item(self, test):
        return self.files.setdefault(source_path(test), {'executed': 0, 'skipped': 0, 'ok': True})

    def startTest(self, test):
        super().startTest(test)
        self._item(test)['executed'] += 1

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if isinstance(test, unittest.TestCase):
            item = self._item(test)
            item['skipped'] += 1
            item['executed'] -= 1


def runtime_origins():
    paths = sysconfig.get_paths()
    return [(name, Path(paths[name]).resolve()) for name in ('purelib', 'platlib', 'stdlib', 'platstdlib')]


def code_source(filename, root, origins):
    path = (root / filename).resolve()
    if path.is_relative_to(root):
        return path.relative_to(root).as_posix()
    for name, base in origins:
        if path.is_relative_to(base):
            return '<{0}>/{1}'.format(name, path.relative_to(base).as_posix())
    raise ValueError('Unsupported Python source for oracle receipt: ' + path.name)


def portable_code(code, root, origins):
    constants = tuple(portable_code(value, root, origins) if isinstance(value, CodeType) else value
                      for value in code.co_consts)
    return code.replace(co_filename=code_source(code.co_filename, root, origins), co_consts=constants)


CACHE_WRAPPER_TYPE = type(lru_cache()(lambda: None))


def record_definition(method, root, origins, digest, stack):
    function = method.__func__ if isinstance(method, MethodType) else method
    identity = id(function)
    if identity in stack:
        raise ValueError('Circular Python method for oracle receipt')
    stack.add(identity)
    wrapped = getattr(function, '__wrapped__', None)
    if type(function) is partial:
        digest.update(b'partial:')
        record_definition(function.func, root, origins, digest, stack)
    elif isinstance(function, FunctionType):
        # Format 2 excludes reference tracking and preserves stable code fields.
        module = function.__globals__.get('__name__', '')
        code = portable_code(function.__code__, root, origins)
        digest.update(marshal.dumps((module, code), 2))
    elif type(function) is CACHE_WRAPPER_TYPE and wrapped is not None:
        digest.update(b'lru_cache:')
    elif wrapped is not None and isinstance(type(function).__call__, FunctionType):
        digest.update(b'callable:')
        record_definition(type(function).__call__, root, origins, digest, stack)
    else:
        raise ValueError('Unsupported Python method for oracle receipt')
    if wrapped is not None:
        digest.update(b'wrapped:')
        record_definition(wrapped, root, origins, digest, stack)
    stack.remove(identity)


def bound_method_fingerprint(method, root, origins):
    digest = hashlib.sha256()
    record_definition(method, root, origins, digest, set())
    return digest.hexdigest()


class IdentifiedResult(RecordedResult):
    def __init__(self, *args, root):
        super().__init__(*args)
        self.root = root
        self.origins = runtime_origins()
        self.case_ids = {}
        self.restore = {}

    def startTest(self, test):
        super().startTest(test)
        name = '_callTestMethod'
        attributes = vars(test)
        self.restore[id(test)] = {name: attributes[name]} if name in attributes else {}
        invoke = test._callTestMethod
        label = unittest.TestCase.id(test).encode('utf-8').hex()
        path = source_path(test)

        def record_and_invoke(method):
            fingerprint = bound_method_fingerprint(method, self.root, self.origins)
            self.case_ids.setdefault(path, []).append(label + ':' + fingerprint)
            return invoke(method)

        attributes[name] = record_and_invoke

    def stopTest(self, test):
        attributes = vars(test)
        attributes.pop('_callTestMethod', None)
        attributes.update(self.restore.pop(id(test)))
        super().stopTest(test)


def main():
    root, output, *names = sys.argv[1:]
    record_ids = names[:1] == ['--record-ids']
    if record_ids:
        names = names[1:]
    sys.path.insert(0, root)
    names = [name[:-3].replace('/', '.') if name.endswith('.py') else name for name in names]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    recorder = partial(IdentifiedResult, root=Path(root).resolve()) if record_ids else RecordedResult
    result = unittest.TextTestRunner(resultclass=recorder, verbosity=1).run(suite)
    ok = result.wasSuccessful() and not result.skipped and not result.expectedFailures
    for item in result.files.values():
        item['ok'] = bool(ok)
    evidence = {'files': result.files}
    if record_ids:
        evidence['case_ids'] = result.case_ids
    Path(output).write_text(json.dumps(evidence), encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
