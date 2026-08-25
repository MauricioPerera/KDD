"""Tests para validate_compliance_findings.py: exit 2 ante findings.json corrupto.

Cubre el contrato del docstring del modulo: si <scan_dir>/findings.json existe
pero esta corrupto/mal formado (JSON invalido), el script debe salir con exit
code 2 y un mensaje claro (no traceback/exit 1 por una excepcion no manejada).
Capa opcional: path inexistente sigue siendo exit 0 (INFO PATH_MISSING).
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import validate_compliance_findings as v  # noqa: E402


class TestCorruptFindings(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="compfind_")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def _run_main(self, argv):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exit_code = v.main(argv)
        return exit_code, out.getvalue(), err.getvalue()

    def _write_findings(self, content):
        scan_dir = os.path.join(self.base, "scan")
        os.makedirs(scan_dir)
        with open(os.path.join(scan_dir, "findings.json"), "w", encoding="utf-8") as fh:
            fh.write(content)
        return scan_dir

    def test_json_invalido_da_exit_2(self):
        scan_dir = self._write_findings("{invalid")
        exit_code, out, err = self._run_main([scan_dir])
        self.assertEqual(exit_code, 2)
        self.assertIn("PARSE_ERROR", err)

    def test_texto_no_json_da_exit_2(self):
        scan_dir = self._write_findings("esto no es json")
        exit_code, out, err = self._run_main([scan_dir])
        self.assertEqual(exit_code, 2)
        self.assertIn("PARSE_ERROR", err)

    def test_path_inexistente_da_exit_0(self):
        exit_code, out, err = self._run_main([os.path.join(self.base, "no-existe")])
        self.assertEqual(exit_code, 0)
        self.assertIn("PATH_MISSING", out)


if __name__ == "__main__":
    unittest.main()