"""Trusted unittest recorder invoked by oracle_execution in an isolated Python."""
import inspect
import json
from pathlib import Path
import sys
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


class IdentifiedResult(RecordedResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.case_ids = {}

    def startTest(self, test):
        super().startTest(test)
        self.case_ids.setdefault(source_path(test), []).append(test.id())


def main():
    root, output, *names = sys.argv[1:]
    record_ids = names[:1] == ['--record-ids']
    if record_ids:
        names = names[1:]
    sys.path.insert(0, root)
    names = [name[:-3].replace('/', '.') if name.endswith('.py') else name for name in names]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    recorder = IdentifiedResult if record_ids else RecordedResult
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
