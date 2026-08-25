"""Smoke test del wiring MCP real (scripts/mcp_server.py) via sesion in-memory.

NO es un oraculo congelado CCDD (mcp_server.py no tiene task contract: depende
del paquete externo `mcp`, fuera de la convencion deps_allowed: [] del resto
del repo -- ver knowledge/contracts/mcp-gate-dispatch.md). Este archivo
verifica, con el SDK real y sin stdio real (streams en memoria), que el
server: (a) expone las 14 tools esperadas, y (b) al menos una tool corrida de
punta a punta via el protocolo MCP real (tools/call) devuelve el resultado
correcto contra el repo real.

Se salta LIMPIO (unittest.SkipTest) si el paquete `mcp` no esta instalado --
asi `python -m unittest discover` sigue verde en CI (que no instala `mcp`;
esta herramienta es opt-in, no parte de Nivel 1). Correr localmente con
`pip install mcp` primero para que esto se ejecute de verdad.
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    import mcp.types as types
    from mcp.shared.memory import create_connected_server_and_client_session
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False


EXPECTED_TOOLS = {
    'validate_contracts', 'validate_specs', 'validate_okf', 'lint_ascii',
    'validate_rules', 'validate_skills', 'validate_changelog',
    'validate_ux_page', 'validate_diagrams', 'validate_test_commands',
    'scan_secrets', 'validate_attestation', 'run_all_level1', 'seal_tests',
    # No es un gate: no pasa por mcp_gate_dispatch ni por subprocess. Es la
    # receta de arreglo de un rule-id, el complemento natural de un veredicto
    # en rojo (un agente que recibe FM_TESTS_FROZEN quiere el arreglo sin
    # salir del protocolo).
    'rule_hint',
}


@unittest.skipUnless(_MCP_AVAILABLE, "paquete 'mcp' no instalado (pip install mcp)")
class TestMcpServerSmoke(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_lists_all_expected_tools(self):
        import mcp_server  # noqa: E402  (importa solo si mcp esta instalado)

        async def _list():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                result = await session.list_tools()
                return {tool.name for tool in result.tools}

        names = self._run(_list())
        self.assertEqual(names, EXPECTED_TOOLS)

    # 'lint_ascii' (no 'validate_contracts') a proposito -- ver el comentario
    # equivalente en tests/test_mcp_gate_dispatch.py:TestRunGate: esta suite
    # a veces corre dentro de una copia mutada de test_init_project.py donde
    # validate_contracts falla por una razon ajena a esta tool. lint_ascii no
    # depende de ese estado.
    def test_lint_ascii_tool_call_end_to_end(self):
        import mcp_server  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                result = await session.call_tool('lint_ascii', {})
                return result

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        # FastMCP serializa el dict que devuelve run_gate como JSON en el
        # primer TextContent (structuredContent queda None: el tipo de
        # retorno de la tool es 'dict' liso, no un schema mas especifico).
        self.assertEqual(len(result.content), 1)
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['exit_code'], 0, payload)

    def test_rule_hint_tool_call_end_to_end(self):
        """La receta de un rule-id conocido viaja por el protocolo MCP real."""
        import mcp_server  # noqa: E402
        import rule_hints  # noqa: E402

        async def _call(rule_id):
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool('rule_hint', {'rule_id': rule_id})

        result = self._run(_call('FM_TESTS_FROZEN'))
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['rule_id'], 'FM_TESTS_FROZEN')
        self.assertTrue(payload['known'])
        self.assertEqual(payload['hint'], rule_hints.HINTS['FM_TESTS_FROZEN'])

    def test_rule_hint_unknown_id_falls_back_without_error(self):
        """Un rule-id desconocido NO es un error de tool: devuelve el fallback.

        Es deliberado -- un agente que pregunta por un codigo que no existe
        debe recibir orientacion, no una excepcion que lo haga abandonar.
        """
        import mcp_server  # noqa: E402
        import rule_hints  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool('rule_hint', {'rule_id': 'NO_EXISTE_ESTE'})

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertFalse(payload['known'])
        self.assertEqual(payload['hint'], rule_hints.FALLBACK_HINT)

    # NO hay test de 'run_all_level1' contra el repo real: esa tool corre
    # validate_test_commands, que corre el test_command de CADA contrato,
    # incluido init-project.md (cuyo test copia el repo entero y vuelve a
    # correr `python -m unittest discover` adentro -- lo que incluiria a
    # ESTE MISMO archivo, causando una explosion recursiva). Ver la nota
    # equivalente en knowledge/contracts/mcp-gate-dispatch.md. La tool
    # 'run_all_level1' SI esta cubierta por 'test_lists_all_14_tools' y por
    # el smoke test de 'validate_contracts' arriba (que ejercen el mismo
    # camino MCP real sin disparar validate_test_commands).

    # --- Confinamiento de paths del cliente al repo_root (AUDIT-MCP) -----
    # Un cliente MCP comprometido podria pasar un dir/tests_path que resuelva
    # fuera del repo y leer o hashear archivos arbitrarios del host. La tool
    # debe rechazarlo (exit_code 2 + stderr claro) sin correr subprocess, en
    # vez de ejecutarlo o crashear. Un path normal dentro del repo sigue
    # funcionando. El path que escapa se arma relativo con os.path.join para
    # ser portable (sube suficientes niveles para salir del repo en cualquier
    # layout).
    _ESCAPE = os.path.join(*(['..'] * 6))

    def test_gate_rejects_dir_escaping_repo(self):
        import mcp_server  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool(
                    'validate_contracts', {'dir': self._ESCAPE})

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['exit_code'], 2, payload)
        self.assertIn('escapes repo_root', payload['stderr'])
        self.assertIn('dir', payload['stderr'])

    def test_gate_rejects_list_dir_escaping_repo(self):
        # Un elemento que escapa dentro de un list (dirs de scan_secrets) basta
        # para rechazar toda la llamada.
        import mcp_server  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool(
                    'scan_secrets', {'dirs': ['scripts', self._ESCAPE]})

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['exit_code'], 2, payload)
        self.assertIn('escapes repo_root', payload['stderr'])

    def test_gate_accepts_explicit_dir_inside_repo(self):
        # Contraparte: un path del cliente que SI esta dentro del repo se
        # despacha y corre el gate normalmente.
        import mcp_server  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool(
                    'lint_ascii', {'dir': 'scripts'})

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertEqual(payload['exit_code'], 0, payload)

    def test_seal_tests_rejects_path_escaping_repo(self):
        import mcp_server  # noqa: E402

        async def _call():
            async with create_connected_server_and_client_session(
                mcp_server.mcp._mcp_server
            ) as session:
                await session.initialize()
                return await session.call_tool(
                    'seal_tests',
                    {'tests_path': os.path.join(self._ESCAPE, 'passwd')})

        result = self._run(_call())
        self.assertFalse(result.isError, result.content)
        payload = json.loads(result.content[0].text)
        self.assertIsNone(payload['hash'])
        self.assertEqual(payload['exit_code'], 2, payload)
        self.assertIn('escapes repo_root', payload['stderr'])


if __name__ == '__main__':
    unittest.main()
