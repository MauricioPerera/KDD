"""Oraculo congelado del gate de supresiones de lint (Contrato: lint-suppression-gate).

Fija el comportamiento de ``scripts/scan_lint_suppressions.py``: escaneo
determinista (regex stdlib, sin red/subprocess/LLM) de un DIFF unificado
(``git diff``) buscando supresiones de lint (hoy: ``#[allow(clippy::...)]`` /
``#![allow(clippy::...)]``) en lineas AGREGADAS por el implementador. Una
supresion preexistente que solo aparece como CONTEXTO (sin prefijo ``+``) o
que se BORRA (prefijo ``-``) no cuenta.

  API:
    ``PATTERNS`` -- lista de ``(rule_name, compiled_regex)``.
        - CLIPPY_ALLOW: ``#!?\\[\\s*allow\\(\\s*clippy::[A-Za-z0-9_:]+``
    ``iter_added_lines(diff_text) -> [(file, line_no, content)]`` -- cada
      linea agregada (prefijo ``+``, sin contar ``+++``) de un diff unificado,
      con `line_no` 1-indexed en el archivo NUEVO (calculado desde los
      headers ``@@ -a,b +c,d @@``). Archivos borrados (``+++ /dev/null``) no
      producen entradas. Nunca lanza.
    ``scan_diff(diff_text) -> [{'file','level','rule','msg'}]`` -- un
      finding ERROR por cada match de PATTERNS en una linea agregada.
      Ordenado por (file, rule, msg).
    ``main(argv) -> int`` -- sin argv[1], lee el diff de stdin; con argv[1],
      lo lee de ese archivo. Imprime findings + resumen. Exit 0 sin
      findings, 1 con >=1.
"""

import os
import sys
import unittest
from unittest import mock
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import scan_lint_suppressions as sls  # noqa: E402


def _diff(*files):
    """Concatena bloques de diff (cada uno ya con su propio header)."""
    return '\n'.join(files) + '\n'


DIFF_ADDED_ATTR = """\
diff --git a/src/lib.rs b/src/lib.rs
index abc123..def456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,4 +1,5 @@
 fn main() {
+    #[allow(clippy::len_zero)]
     let v = Vec::<i32>::new();
     if v.len() == 0 {}
 }
"""

DIFF_ADDED_INNER_ATTR = """\
diff --git a/src/lib.rs b/src/lib.rs
index abc123..def456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,2 +1,3 @@
+#![allow(clippy::pedantic)]
 fn main() {
 }
"""

DIFF_CONTEXT_ONLY = """\
diff --git a/src/lib.rs b/src/lib.rs
index abc123..def456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,4 +1,4 @@
 #[allow(clippy::len_zero)]
 fn main() {
-    let old = 1;
+    let new = 2;
 }
"""

DIFF_REMOVED_SUPPRESSION = """\
diff --git a/src/lib.rs b/src/lib.rs
index abc123..def456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,3 +1,2 @@
-#[allow(clippy::len_zero)]
 fn main() {
 }
"""

DIFF_DELETED_FILE = """\
diff --git a/src/old.rs b/src/old.rs
deleted file mode 100644
index abc123..0000000
--- a/src/old.rs
+++ /dev/null
@@ -1,2 +0,0 @@
-#[allow(clippy::len_zero)]
-fn main() {}
"""

DIFF_TWO_FILES = """\
diff --git a/src/a.rs b/src/a.rs
index 1111111..2222222 100644
--- a/src/a.rs
+++ b/src/a.rs
@@ -1,2 +1,3 @@
 fn a() {
+    #[allow(clippy::len_zero)]
 }
diff --git a/src/b.rs b/src/b.rs
index 3333333..4444444 100644
--- a/src/b.rs
+++ b/src/b.rs
@@ -1,2 +1,3 @@
 fn b() {
+    #![allow(clippy::pedantic)]
 }
"""


class IterAddedLines(unittest.TestCase):
    def test_added_line_and_line_number(self):
        got = sls.iter_added_lines(DIFF_ADDED_ATTR)
        self.assertEqual(got, [
            ('src/lib.rs', 2, '    #[allow(clippy::len_zero)]'),
        ])

    def test_added_line_at_start_of_hunk(self):
        got = sls.iter_added_lines(DIFF_ADDED_INNER_ATTR)
        self.assertEqual(got, [
            ('src/lib.rs', 1, '#![allow(clippy::pedantic)]'),
        ])

    def test_added_non_suppression_line_still_yielded(self):
        got = sls.iter_added_lines(DIFF_CONTEXT_ONLY)
        self.assertEqual(got, [('src/lib.rs', 3, '    let new = 2;')])

    def test_removed_line_not_yielded(self):
        got = sls.iter_added_lines(DIFF_REMOVED_SUPPRESSION)
        self.assertEqual(got, [])

    def test_deleted_file_not_yielded(self):
        got = sls.iter_added_lines(DIFF_DELETED_FILE)
        self.assertEqual(got, [])

    def test_two_files_tracked_independently(self):
        got = sls.iter_added_lines(DIFF_TWO_FILES)
        self.assertEqual(got, [
            ('src/a.rs', 2, '    #[allow(clippy::len_zero)]'),
            ('src/b.rs', 2, '    #![allow(clippy::pedantic)]'),
        ])

    def test_empty_diff_never_raises(self):
        self.assertEqual(sls.iter_added_lines(''), [])

    def test_garbage_input_never_raises(self):
        self.assertEqual(sls.iter_added_lines('not a diff at all\n@@ garbage @@'), [])


class ScanDiff(unittest.TestCase):
    def test_added_attribute_is_a_finding(self):
        got = sls.scan_diff(DIFF_ADDED_ATTR)
        self.assertEqual(len(got), 1)
        f = got[0]
        self.assertEqual(f['file'], 'src/lib.rs')
        self.assertEqual(f['level'], 'ERROR')
        self.assertEqual(f['rule'], 'CLIPPY_ALLOW')
        self.assertIn('line 2', f['msg'])
        self.assertIn('clippy::len_zero', f['msg'])

    def test_added_inner_attribute_is_a_finding(self):
        got = sls.scan_diff(DIFF_ADDED_INNER_ATTR)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['rule'], 'CLIPPY_ALLOW')

    def test_preexisting_suppression_as_context_is_not_a_finding(self):
        got = sls.scan_diff(DIFF_CONTEXT_ONLY)
        self.assertEqual(got, [])

    def test_removed_suppression_is_not_a_finding(self):
        got = sls.scan_diff(DIFF_REMOVED_SUPPRESSION)
        self.assertEqual(got, [])

    def test_two_files_both_reported_sorted_by_file(self):
        got = sls.scan_diff(DIFF_TWO_FILES)
        self.assertEqual([f['file'] for f in got], ['src/a.rs', 'src/b.rs'])

    def test_clean_diff_no_findings(self):
        clean = """\
diff --git a/src/lib.rs b/src/lib.rs
index abc123..def456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,2 +1,3 @@
 fn main() {
+    println!("hi");
 }
"""
        self.assertEqual(sls.scan_diff(clean), [])

    def test_empty_diff_no_findings(self):
        self.assertEqual(sls.scan_diff(''), [])


class MainCli(unittest.TestCase):
    def test_findings_exit1_from_stdin(self):
        with mock.patch('sys.stdin', StringIO(DIFF_ADDED_ATTR)):
            code = sls.main(['scan_lint_suppressions.py'])
        self.assertEqual(code, 1)

    def test_clean_exit0_from_stdin(self):
        with mock.patch('sys.stdin', StringIO(DIFF_REMOVED_SUPPRESSION)):
            code = sls.main(['scan_lint_suppressions.py'])
        self.assertEqual(code, 0)

    def test_reads_from_file_argument(self):
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.diff')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(DIFF_ADDED_ATTR)
            code = sls.main(['scan_lint_suppressions.py', path])
        finally:
            os.remove(path)
        self.assertEqual(code, 1)

    def test_missing_file_argument_exit1(self):
        code = sls.main(['scan_lint_suppressions.py', 'does-not-exist.diff'])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
