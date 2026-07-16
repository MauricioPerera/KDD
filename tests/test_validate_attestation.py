"""Oraculo congelado del gate de atestacion (Contrato: attestation-gate).

Fija el comportamiento de ``scripts/validate_attestation.py``: verifica el
envelope mini-YAML al tope de cada ``.agents/logs/<task>-REPORT.md`` (evidencia
LOCAL, gitignorada -- ver knowledge/validacion.md, "verified"). El envelope
liga la evidencia a una identidad (agente/modelo), a un comando+exit_code, y a
DOS hashes recomputables: el del propio output pegado abajo del envelope, y el
del contrato (knowledge/contracts/<task>.md) tal como estaba al momento de
verificar. Sin esto, "verified" era una aserción humana sin sello.

  Formato de un REPORT valido (ejemplo):
    ---
    task: hello-world
    agent: glm-5.2:cloud
    model: glm-5.2:cloud
    command: "python -m unittest tests/test_sample.py"
    exit_code: 0
    output_sha256: <sha256 LF-normalizado del body de abajo>
    contract_sha256: <sha256 LF-normalizado de knowledge/contracts/hello-world.md>
    repo_head: 24706ab...
    timestamp: 2026-07-14T12:00:00Z
    ---
    <output real pegado sin modificar>

  API:
    ``REQUIRED_KEYS`` -- tupla de las 9 claves obligatorias del envelope, en
      el orden del ejemplo de arriba.
    ``parse_envelope(text) -> (dict|None, str)`` -- ``dict`` de
      ``{clave: valor_string}`` del bloque YAML entre los primeros DOS
      delimitadores ``---`` de ``text``, y el ``body`` (todo lo que sigue
      despues del segundo delimitador, sin la primera linea en blanco si la
      hay). ``(None, text)`` si ``text`` no empieza con ``---\\n`` o no tiene
      un segundo delimitador ``---`` en su propia linea.
    ``validate_report(path, repo_root) -> [{'file','level','rule','msg'}]``
      -- valida un unico archivo ``<task>-REPORT.md``:
        ``ENVELOPE_MISSING`` (WARNING) -- ``parse_envelope`` devuelve
          ``(None, ...)``. Unico finding en ese caso (nada mas se chequea).
        ``MISSING_KEY`` (ERROR) -- una por cada clave de ``REQUIRED_KEYS``
          ausente o vacia en el envelope.
        ``TASK_MISMATCH`` (ERROR, solo si ``task`` esta presente) --
          ``envelope['task']`` no coincide con el nombre del archivo sin el
          sufijo ``-REPORT.md`` (ej. archivo ``hello-world-REPORT.md`` exige
          ``task: hello-world``).
        ``EXIT_CODE_INVALID`` (ERROR, solo si ``exit_code`` esta presente)
          -- el valor no es un entero literal (regex ``^-?\\d+$``).
        ``EXIT_CODE_NONZERO`` (ERROR, solo si ``exit_code`` es un entero
          valido) -- el entero no es 0.
        ``OUTPUT_HASH_MISMATCH`` (ERROR, solo si ``output_sha256`` esta
          presente) -- el sha256 LF-normalizado del ``body`` no coincide.
        ``CONTRACT_MISSING`` (ERROR, solo si ``task`` y ``contract_sha256``
          estan presentes) -- ``knowledge/contracts/<task>.md`` no existe
          bajo ``repo_root``.
        ``CONTRACT_HASH_MISMATCH`` (ERROR, solo si el contrato existe) --
          el sha256 LF-normalizado del contrato no coincide con
          ``contract_sha256``.
      Ordenado por ``rule``. NO valida ``agent``/``model``/``timestamp``/
      ``repo_head`` mas alla de su presencia (son atestacion, no
      verificables mecanicamente).
    ``validate_directory(logs_dir, repo_root='.') -> [findings]`` -- valida
      cada ``*-REPORT.md`` de ``logs_dir`` (no recursivo), EXCLUYE
      ``TEMPLATE-REPORT.md`` (no es evidencia real). Directorio inexistente
      -> ``[]`` (evidencia local: sin `.agents/logs/`, nada que auditar, no
      es error). Ordenado por ``(file, rule)``.
    ``main(argv) -> int`` -- ``argv[1]``=logs_dir (default
      ``.agents/logs``), ``argv[2]``=repo_root (default ``.``). Imprime cada
      finding (``str``: ``"<level> [<rule>] <file>: <msg>"``). Devuelve 0 si
      no hay ningun finding con ``level == 'ERROR'`` (los WARNING, como
      ``ENVELOPE_MISSING``, NO bloquean -- retrocompatibilidad con reportes
      pre-atestacion); 1 si hay >=1 ERROR.
"""

import hashlib
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import validate_attestation as va  # noqa: E402


def _write(path, content):
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)


def _sha256(text):
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _envelope(task, body, exit_code='0', output_sha256=None, contract_sha256='c' * 64,
              extra_keys=None, omit=()):
    if output_sha256 is None:
        output_sha256 = _sha256(body)
    fields = {
        'task': task,
        'agent': 'glm-5.2:cloud',
        'model': 'glm-5.2:cloud',
        'command': '"python -m unittest tests/test_x.py"',
        'exit_code': exit_code,
        'output_sha256': output_sha256,
        'contract_sha256': contract_sha256,
        'repo_head': 'a' * 40,
        'timestamp': '2026-07-14T12:00:00Z',
    }
    if extra_keys:
        fields.update(extra_keys)
    for key in omit:
        fields.pop(key, None)
    lines = ['---']
    for key, value in fields.items():
        lines.append('{}: {}'.format(key, value))
    lines.append('---')
    lines.append('')
    lines.append(body)
    return '\n'.join(lines)


class TestParseEnvelope(unittest.TestCase):
    def test_valid_envelope(self):
        text = _envelope('hello-world', 'salida real\nlinea 2')
        data, body = va.parse_envelope(text)
        self.assertIsNotNone(data)
        self.assertEqual(data['task'], 'hello-world')
        self.assertEqual(data['exit_code'], '0')
        self.assertEqual(body, 'salida real\nlinea 2')

    def test_no_envelope_returns_none(self):
        text = 'solo texto plano, sin frontmatter\n'
        data, body = va.parse_envelope(text)
        self.assertIsNone(data)
        self.assertEqual(body, text)

    def test_unclosed_envelope_returns_none(self):
        text = '---\ntask: x\nno hay cierre\n'
        data, body = va.parse_envelope(text)
        self.assertIsNone(data)

    def test_parse_envelope_lf_igual_crlf(self):
        # H-3: un reporte con CRLF debe parsearse IGUAL que con LF. Antes del
        # fix ``text.startswith('---\\n')`` rechazaba el envelope CRLF ->
        # (None, text) y se trataba como "sin envelope" (WARNING).
        lf = _envelope('hello-world', 'salida real\nlinea 2')
        crlf = lf.replace('\n', '\r\n')
        d_lf, b_lf = va.parse_envelope(lf)
        d_crlf, b_crlf = va.parse_envelope(crlf)
        self.assertIsNotNone(d_crlf)
        self.assertEqual(d_lf, d_crlf)
        self.assertEqual(b_lf, b_crlf)
        self.assertEqual(d_crlf['task'], 'hello-world')


class TestValidateReportEnvelopeMissing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plain_text_report_is_warning_only(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, '# Reporte viejo\nSin envelope, solo prosa.\n')
        findings = va.validate_report(path, repo_root=self.tmp)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['rule'], 'ENVELOPE_MISSING')
        self.assertEqual(findings[0]['level'], 'WARNING')


class TestValidateReportKeys(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.contract_dir = os.path.join(self.tmp, 'knowledge', 'contracts')
        os.makedirs(self.contract_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_contract(self, task, content='# Contract\n'):
        path = os.path.join(self.contract_dir, '{}.md'.format(task))
        _write(path, content)
        return _sha256(content)

    def test_missing_key_reported(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out', omit=('agent',)))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('MISSING_KEY', rules)
        missing_finding = next(f for f in findings if f['rule'] == 'MISSING_KEY')
        self.assertIn('agent', missing_finding['msg'])
        self.assertEqual(missing_finding['level'], 'ERROR')

    def test_empty_key_value_reported_as_missing(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        text = _envelope('hello-world', 'out').replace('model: glm-5.2:cloud', 'model:')
        _write(path, text)
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('MISSING_KEY', rules)

    def test_task_mismatch(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('otra-tarea', 'out'))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('TASK_MISMATCH', rules)

    def test_exit_code_invalid(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out', exit_code='not-a-number'))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('EXIT_CODE_INVALID', rules)
        self.assertNotIn('EXIT_CODE_NONZERO', rules)

    def test_exit_code_nonzero(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out', exit_code='1'))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('EXIT_CODE_NONZERO', rules)

    def test_output_hash_mismatch(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out', output_sha256='f' * 64))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('OUTPUT_HASH_MISMATCH', rules)

    def test_contract_missing(self):
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out'))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('CONTRACT_MISSING', rules)

    def test_contract_hash_mismatch(self):
        self._write_contract('hello-world', '# Contract v1\n')
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'out', contract_sha256='e' * 64))
        findings = va.validate_report(path, repo_root=self.tmp)
        rules = [f['rule'] for f in findings]
        self.assertIn('CONTRACT_HASH_MISMATCH', rules)

    def test_fully_valid_report_no_findings(self):
        contract_hash = self._write_contract('hello-world', '# Contract v1\n')
        path = os.path.join(self.tmp, 'hello-world-REPORT.md')
        _write(path, _envelope('hello-world', 'salida real', contract_sha256=contract_hash))
        findings = va.validate_report(path, repo_root=self.tmp)
        self.assertEqual(findings, [])


class TestValidateDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.contract_dir = os.path.join(self.tmp, 'knowledge', 'contracts')
        os.makedirs(self.contract_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_contract(self, task, content='# Contract\n'):
        path = os.path.join(self.contract_dir, '{}.md'.format(task))
        _write(path, content)
        return _sha256(content)

    def test_nonexistent_logs_dir_returns_empty(self):
        findings = va.validate_directory(os.path.join(self.tmp, 'nope'), repo_root=self.tmp)
        self.assertEqual(findings, [])

    def test_skips_template_report(self):
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        _write(os.path.join(logs_dir, 'TEMPLATE-REPORT.md'), 'placeholder <task>\n')
        findings = va.validate_directory(logs_dir, repo_root=self.tmp)
        self.assertEqual(findings, [])

    def test_aggregates_across_files_sorted(self):
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        contract_hash = self._write_contract('aaa-task')
        _write(
            os.path.join(logs_dir, 'aaa-task-REPORT.md'),
            _envelope('aaa-task', 'ok', contract_sha256=contract_hash),
        )
        _write(
            os.path.join(logs_dir, 'zzz-task-REPORT.md'),
            'sin envelope\n',
        )
        findings = va.validate_directory(logs_dir, repo_root=self.tmp)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['rule'], 'ENVELOPE_MISSING')
        self.assertIn('zzz-task-REPORT.md', findings[0]['file'])

    def test_ignores_non_report_files(self):
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        _write(os.path.join(logs_dir, 'notes.txt'), 'not a report\n')
        findings = va.validate_directory(logs_dir, repo_root=self.tmp)
        self.assertEqual(findings, [])


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.contract_dir = os.path.join(self.tmp, 'knowledge', 'contracts')
        os.makedirs(self.contract_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_contract(self, task, content='# Contract\n'):
        path = os.path.join(self.contract_dir, '{}.md'.format(task))
        _write(path, content)
        return _sha256(content)

    def test_warning_only_returns_0(self):
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        _write(os.path.join(logs_dir, 'x-REPORT.md'), 'sin envelope\n')
        code = va.main(['prog', logs_dir, self.tmp])
        self.assertEqual(code, 0)

    def test_error_returns_1(self):
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        _write(os.path.join(logs_dir, 'hello-world-REPORT.md'), _envelope('hello-world', 'out'))
        code = va.main(['prog', logs_dir, self.tmp])
        self.assertEqual(code, 1)

    def test_fully_valid_returns_0(self):
        contract_hash = self._write_contract('hello-world')
        logs_dir = os.path.join(self.tmp, '.agents', 'logs')
        _write(
            os.path.join(logs_dir, 'hello-world-REPORT.md'),
            _envelope('hello-world', 'salida', contract_sha256=contract_hash),
        )
        code = va.main(['prog', logs_dir, self.tmp])
        self.assertEqual(code, 0)

    def test_missing_logs_dir_returns_0(self):
        code = va.main(['prog', os.path.join(self.tmp, 'nope'), self.tmp])
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
