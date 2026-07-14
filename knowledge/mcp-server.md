---
type: 'Concept'
title: 'MCP server propio: los gates de KDD como tools'
description: 'Como instalar y registrar scripts/mcp_server.py, que expone los 12 gates + orquestacion + sellado como tools MCP. Herramienta opt-in (depende del paquete externo mcp), no parte de Nivel 1/CI.'
tags: ['ccdd', 'mcp', 'infra', 'reference']
---

# MCP server propio

Cierra el ultimo gap de la auditoria de posicionamiento de KDD ("MCP server
propio que expone los gates como tools MCP", ver
[por-que-kdd.md](./por-que-kdd.md) y el analisis delta que la origino): hasta
ahora KDD **consumia** MCP (`ccdd-complexity`, Nivel 2) pero no **ofrecia**
el suyo. Cualquier agente con un cliente MCP puede ahora llamar
`run_all_level1` y saber, en una sola llamada, si un repo KDD esta verde en
Nivel 1 — sin tener que saber que existe `validate_contracts.py`,
`scan_secrets.py`, etc. por separado.

## Arquitectura: dos modulos, una sola frontera

- **`scripts/mcp_gate_dispatch.py`** — logica PURA (stdlib, sin el SDK
  `mcp`). Sabe que script `scripts/*.py` correr por cada gate y como armar
  su `argv`; ejecuta via `subprocess.run`. Tiene contrato+oraculo sellado
  ([mcp-gate-dispatch](./contracts/mcp-gate-dispatch.md)) como cualquier
  otro gate del repo.
- **`scripts/mcp_server.py`** — wiring delgado sobre el modulo anterior,
  usando el SDK oficial `mcp` (`FastMCP`) para exponer cada entrada como
  tool via stdio. **NO tiene task contract**: depende de un paquete
  externo (`mcp`), lo que rompe la convencion `deps_allowed: []` que
  siguen los demas 13 contratos de este repo. Es deliberado — separar la
  logica testeable-sin-SDK de su wiring MCP es lo que permite que
  `mcp_gate_dispatch.py` SI tenga oraculo congelado sin forzar esa
  dependencia sobre el resto del pipeline.

## Instalar y correr

```bash
pip install mcp
python scripts/mcp_server.py
```

Corre por stdio (el transporte estandar para clientes MCP locales tipo
Claude Code/Desktop). Para registrarlo en un cliente MCP, agregalo a su
config (`.mcp.json` o equivalente):

```json
{
  "mcpServers": {
    "kdd-gates": {
      "command": "python",
      "args": ["scripts/mcp_server.py"],
      "cwd": "/ruta/a/tu/clon/de/KDD"
    }
  }
}
```

## Tools expuestas (14)

Una tool por cada gate de `mcp_gate_dispatch.GATE_SPECS` (los mismos 12
gates documentados en [validacion.md](./validacion.md), con los mismos
parametros y defaults que usa `.github/workflows/validate.yml`), mas dos
de orquestacion/utilidad:

- `validate_contracts`, `validate_specs`, `validate_okf`, `lint_ascii`,
  `validate_rules`, `validate_skills`, `validate_changelog`,
  `validate_ux_page`, `validate_diagrams`, `validate_test_commands`,
  `scan_secrets`, `validate_attestation` — un wrapper 1:1 por gate.
- `run_all_level1` — corre los 11 gates de Nivel 1 (todos excepto
  `validate_attestation`, que es local-only) en una sola llamada. Devuelve
  `{'overall_ok': bool, 'results': {...}}`. **La tool de mayor valor**:
  un agente que quiere saber "¿este repo esta Nivel 1 verde?" no necesita
  conocer los 11 gates por separado.
- `seal_tests(tests_path)` — corre `validate_contracts.py --hash` y
  devuelve el hash a copiar en `tests_sha256`, sin que el agente tenga que
  invocar el CLI a mano.

No se incluyen `assemble_context`/`export_gate_contract` (prep de Nivel 2)
en esta primera version — extensible siguiendo el mismo patron si hace
falta.

## Por que NO corre en CI ni es Nivel 1

`scripts/mcp_server.py` requiere `pip install mcp`; ningun step de
`.github/workflows/validate.yml` lo instala ni lo invoca. Es herramienta
opt-in para quien quiera un cliente MCP arbitrario consumiendo los gates,
no parte del pipeline obligatorio. `mcp_gate_dispatch.py` (la logica que
SI reusan las tools) sigue verificandose via su propio `test_command`
dentro de Nivel 1, igual que cualquier otro gate.

## Advertencia de diseno: `run_all_level1` nunca se prueba contra este mismo repo

El oraculo de `mcp_gate_dispatch.py` (y el smoke test de `mcp_server.py`)
deliberadamente NUNCA llaman `run_all_level1` (que incluye
`validate_test_commands`) contra el propio repo KDD corriendo su propia
suite: `validate_test_commands` corre el `test_command` de CADA contrato,
incluido `init-project.md`, cuyo test copia el repo entero y corre
`python -m unittest discover` DENTRO de esa copia — una llamada a
`run_all_level1` contra el repo real, ejecutada DESDE DENTRO de esa
suite, dispara el mismo ciclo recursivamente. Ver la nota completa en
[mcp-gate-dispatch.md](./contracts/mcp-gate-dispatch.md). No es un bug del
modulo; es una interaccion real con el test de auto-copia de
`init-project.md` que solo se activa en ese escenario especifico.

## Ver tambien

- [mcp-gate-dispatch](./contracts/mcp-gate-dispatch.md) — contrato de la
  capa de despacho.
- [validacion.md](./validacion.md) — que verifica cada gate en detalle.
- [por-que-kdd.md](./por-que-kdd.md) — posicionamiento; menciona este gap
  como parte de "no consumible como infraestructura".
