"""Trusted unittest recorder invoked by oracle_execution in an isolated Python."""
from functools import partial
import hashlib
import inspect
import json
import marshal
from pathlib import Path
import sys
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


def portable_code(code, root):
    source = Path(code.co_filename).resolve().relative_to(root).as_posix()
    constants = tuple(portable_code(value, root) if isinstance(value, CodeType) else value
                      for value in code.co_consts)
    return code.replace(co_filename=source, co_consts=constants)


def bound_method_fingerprint(method, root):
    digest = hashlib.sha256()
    seen = set()
    while method is not None:
        function = method.__func__ if isinstance(method, MethodType) else method
        if not isinstance(function, FunctionType) or function in seen:
            raise ValueError('Unsupported Python method for oracle receipt')
        seen.add(function)
        # Format 2 excludes reference tracking and preserves stable code fields.
        digest.update(marshal.dumps(portable_code(function.__code__, root), 2))
        method = getattr(function, '__wrapped__', None)
    return digest.hexdigest()


class IdentifiedResult(RecordedResult):
    def __init__(self, *args, root):
        super().__init__(*args)
        self.root = root
        self.case_ids = {}
        self.restore = {}

    def startTest(self, test):
        super().startTest(test)
        name = '_callTestMethod'
        attributes = vars(test)
        self.restore[test] = {name: attributes[name]} if name in attributes else {}
        invoke = test._callTestMethod

        def record_and_invoke(method):
            label = unittest.TestCase.id(test)
            fingerprint = bound_method_fingerprint(method, self.root)
            self.case_ids.setdefault(source_path(test), []).append(label + '#' + fingerprint)
            return invoke(method)

        attributes[name] = record_and_invoke

    def stopTest(self, test):
        attributes = vars(test)
        attributes.pop('_callTestMethod', None)
        attributes.update(self.restore.pop(test))
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
