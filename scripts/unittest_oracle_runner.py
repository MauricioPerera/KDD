"""Trusted unittest recorder invoked by oracle_execution in an isolated Python."""
import inspect
import json
from pathlib import Path
import sys
import unittest


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.files = {}

    def _item(self, test):
        name = str(Path(inspect.getfile(type(test))).resolve())
        return self.files.setdefault(name, {'executed': 0, 'skipped': 0, 'ok': True})

    def startTest(self, test):
        super().startTest(test)
        self._item(test)['executed'] += 1

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._item(test)['skipped'] += 1
        self._item(test)['executed'] -= 1


def main():
    root, output, *names = sys.argv[1:]
    sys.path.insert(0, root)
    names = [name[:-3].replace('/', '.') if name.endswith('.py') else name for name in names]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(resultclass=RecordedResult, verbosity=1).run(suite)
    ok = result.wasSuccessful() and not result.expectedFailures and not result.unexpectedSuccesses
    for item in result.files.values():
        item['ok'] = bool(ok)
    Path(output).write_text(json.dumps({'files': result.files}), encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
