---
type: 'Concept'
title: 'MCP server propio: los gates de KDD como tools'
description: 'Como instalar y registrar scripts/mcp_server.py, que expone los 19 gates + orquestacion + sellado como tools MCP. Herramienta opt-in (depende del paquete externo mcp), no parte de Nivel 1/CI.'
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
  siguen los demas contratos de este repo. Es deliberado — separar la
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

## Tools expuestas (16)

Una tool por cada gate de `mcp_gate_dispatch.GATE_SPECS` (los mismos 13
gates documentados en [validacion.md](./validacion.md), con los mismos
parametros y defaults que usa `.github/workflows/validate.yml`), mas tres
de orquestacion/utilidad:

- `validate_contracts`, `validate_specs`, `validate_okf`, `lint_ascii`,
  `validate_rules`, `validate_skills`, `validate_changelog`,
  `validate_ux_page`, `validate_diagrams`, `validate_security_findings`,
  `validate_compliance_findings`, `validate_test_commands`,
  `scan_secrets`, `validate_attestation` — un wrapper 1:1 por gate.
- `run_all_level1` — corre los 18 gates de Nivel 1 (todos excepto
  `validate_attestation`, que es local-only) en una sola llamada. Devuelve
  `{'overall_ok': bool, 'results': {...}}`. **La tool de mayor valor**:
  un agente que quiere saber "¿este repo esta Nivel 1 verde?" no necesita
  conocer los 18 gates por separado.
- `seal_tests(tests_path)` — corre `validate_contracts.py --hash` y
  devuelve el hash a copiar en `tests_sha256`, sin que el agente tenga que
  invocar el CLI a mano.
- `rule_hint(rule_id)` — la **receta de arreglo** de un rule-id: el QUE
  HACER que el mensaje del gate no da. Devuelve
  `{'rule_id', 'hint', 'known'}`. Es el complemento natural de un veredicto
  en rojo: un agente que recibe `FM_TESTS_FROZEN` de `validate_contracts`
  pide el arreglo sin salir del protocolo. Un `rule_id` desconocido **no es
  un error**: devuelve el fallback con `known: false`, para que preguntar de
  mas oriente en vez de abortar. Ver la seccion "Recetas de arreglo por
  rule-id" de [validacion.md](./validacion.md).

`rule_hint` es la unica tool que **no** pasa por `mcp_gate_dispatch`: no es
un gate y no corre subprocess, asi que llama directo a
`rule_hints.hint_for` (stdlib pura). Por lo mismo **no** entra en
`GATE_SPECS` — meterla ahi la sumaria a `LEVEL1_GATES` y romperia el
oraculo congelado del preflight (19 gates exactos).

No se incluyen `assemble_context`/`export_gate_contract` (prep de Nivel 2)
en esta primera version — extensible siguiendo el mismo patron si hace
falta.

## Que entra como tool y que no

> **Por MCP viajan veredictos y utilidades; los diagnosticos se corren en
> local.**

| Herramienta | Tipo | Tool MCP |
|---|---|---|
| los 19 gates, `run_all_level1` | veredicto (exit 0/1) | si |
| `seal_tests`, `rule_hint` | utilidad puntual | si |
| `preflight`, `audit_seals`, `benchmark_gates` | diagnostico advisory | **no** |

Tres razones, no simetria:

1. **Un advisory no es accionable en remoto.** Sin `--strict`,
   `audit_seals` sale **exit 0 aunque haya findings**. Un cliente que
   recibe "ok" no puede distinguir "sano" de "hay 6 seals debiles" sin
   interpretar el payload — justo la ambiguedad que un gate determinista
   existe para evitar.
2. **Se usan cuando ya estas en el repo.** `preflight` corre antes de
   delegar; `audit_seals`, al autorar o revisar un oraculo antes de
   sellarlo (ver [supervision-humana](./supervision-humana.md)). En esos
   momentos hay shell abierta y el MCP no ahorra nada.
3. **Operan sobre el arbol local** (contratos, tests y logs en disco), asi
   que un cliente remoto no tiene sobre que accionar el resultado.

El contraste que hace util la regla: `rule_hint` **si** se expone porque es
una **consulta pura** — sin estado, sin tocar el arbol — que responde a un
veredicto que el agente acaba de recibir por el mismo canal. Ahi el MCP si
ahorra un cambio de contexto.

Romper la regla es legitimo, pero **con la excepcion escrita aqui**: si
algun dia `audit_seals` gana un modo con veredicto real (`--strict` por
default, exit code accionable) o aparece un flujo donde un cliente remoto
deba auditar un repo que no tiene delante, se expone y se documenta por que
deja de ser un diagnostico.

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

## Preflight CLI vs `run_all_level1`

Dos bocas sobre la misma logica de despacho (`mcp_gate_dispatch`), para
distintos consumidores:

- **`run_all_level1` (tool MCP)** — corre los **18 gates de Nivel 1**
  (excluye `validate_attestation`, que es local-only) en una sola
  llamada. Requiere `pip install mcp` + un cliente MCP; ideal para un
  agente que consume los gates por MCP.
- **`scripts/preflight.py` (CLI)** — cero dependencias (stdlib + modulos
  hermanos, sin el SDK `mcp`); corre los **19 gates** (los 18 de Nivel 1
  + `validate_attestation`, el unico lugar donde corren juntos porque
  `.agents/logs/` es local). Modo `--contract <nombre>`: 3 chequeos
  acotados a un task contract (frontmatter, sello, `test_command`). Es
  diagnostico opt-in, NO un gate de Nivel 1 (el conteo sigue en 13) y no
  corre en CI — mismo estatus que `benchmark_gates.py`. Ver
  [preflight](./contracts/preflight.md) y
  [validacion.md](./validacion.md#preflight--diagnóstico-local-opt-in-no-es-un-gate).
