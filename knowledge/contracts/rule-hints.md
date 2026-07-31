---
type: 'Task Contract'
title: 'Recetas de arreglo por rule-id: los gates dicen que falla, no que hacer'
description: 'Mapa rule-id -> receta accionable para los 107 codigos que emiten los validadores, usable como CLI y como dato. Los gates reportan QUE fallo ("clave requerida ausente: type") pero no QUE HACER; un humano lo deduce leyendo el nodo OKF, un agente efimero itera a ciegas. Analogo de tools/rule-hints.js del proyecto hermano game-protocol. NO es gate de CI ni entra en GATE_SPECS.'
tags: ['ccdd', 'dx', 'infra', 'agentes']

task: rule-hints
intent: "Devolver la receta de arreglo accionable que corresponde a un rule-id de los gates."
target: scripts/rule_hints.py
signature: "def hint_for(rule_id) -> str"
test_command: "python -m unittest tests/test_rule_hints.py"
budget:
  cyclomatic_max: 12
  nesting_max: 3
tests: "tests/test_rule_hints.py"
tests_sha256: "5e96d1d4fc8ba8a0a15926dd0e13e0a83155b830893e0c0de623bf2710f10b8d"
touch_only: ['scripts/rule_hints.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Recetas de arreglo por rule-id (rule-hints)

> **Nota de honestidad metodologica.** Este contrato se redacto DESPUES de
> implementar la herramienta, al detectar que era la unica del repo sin
> contrato mientras se auditaba el indice OKF antes de un release. El resto
> de contratos siguio el orden correcto (oraculo primero, sellado, luego
> implementacion delegada). Un contrato a posteriori documenta la frontera y
> congela el oraculo hacia adelante, pero NO demuestra que el oraculo
> precedio al codigo: esa garantia, para esta herramienta, no existe. Se deja
> escrito en vez de disimularlo.

## Intent
Los validadores reportan QUE fallo, no QUE HACER. `clave requerida ausente:
type` es un diagnostico correcto e inutil para quien no sabe donde mirar: un
humano lo resuelve leyendo el nodo OKF correspondiente, pero un agente
efimero llega en frio, no tiene ese contexto y tantea. Esta herramienta es la
mitad que faltaba: el mapa de cada rule-id a su receta.

Es la contraparte de `preflight.py` (que dice CUALES gates fallan) y de
`audit_seals.py` (que dice si un oraculo es debil). Diagnostico opt-in, no
gate: Nivel 1 sigue siendo 18 gates y el conteo no cambia.

Linaje: analogo de `tools/rule-hints.js` del proyecto hermano
[game-protocol](https://github.com/MauricioPerera/game-protocol), donde cada
hallazgo del linter viaja con su arreglo en el modo `--agent`. Cierra el
viaje de vuelta entre ambos repos: las familias declarativas
(`refs`/`bounds`/`enums`) salieron de alli hacia los rule contracts de este
(ver [rule-contract-spec](../rule-contract-spec.md)), y los hints hacen el
camino inverso.

## Interface
- `HINTS: dict[str, str]` — mapa rule-id -> receta. Puro dato, sin logica.
- `FALLBACK_HINT: str` — orientacion generica que apunta al nodo canonico;
  se devuelve ante un rule-id desconocido, para que la respuesta nunca sea
  vacia.
- `hint_for(rule_id) -> str`: la receta del codigo, o `FALLBACK_HINT` si no
  esta en el mapa. Nunca lanza, nunca devuelve None.
- `enrich(findings) -> list[dict]`: agrega la clave `hint` a cada finding
  `{file, level, rule, msg}` SIN mutar la entrada (devuelve copias).
- `main(argv) -> int`: argv sin el nombre del script. Un posicional
  (`<RULE_ID>`) imprime su receta; `--all` las imprime todas con su codigo;
  `--json` vuelca el mapa; `--help` la ayuda. Exit 0 = OK, 2 = input
  (rule-id desconocido o flag no reconocido). Nunca emite 1.

## Invariants
- Toda receta dice QUE HACER: nombra el archivo, la clave o el comando
  concreto, y cabe en 1-3 lineas.
- `hint_for` es total: cualquier string de entrada devuelve un str no vacio.
- `enrich` no muta su argumento (los findings originales quedan sin `hint`).
- Cero dependencias externas (stdlib: `json`, `sys`). Sin red, sin
  subprocess, sin LLM.
- ASCII puro (lo audita `lint_ascii`).
- El mapa es DATO, no logica: agregar un codigo es agregar una entrada, no
  tocar una funcion.

## Examples
- `hint_for('FM_TESTS_FROZEN')` -> receta que menciona
  `validate_contracts.py --hash`.
- `hint_for('CODIGO_INEXISTENTE')` -> `FALLBACK_HINT` (no lanza).
- `python scripts/rule_hints.py --all` -> las 101 recetas, exit 0.
- `python scripts/rule_hints.py NOPE` -> stderr + exit 2.
- `python scripts/preflight.py --agent` -> cada gate en rojo con la receta
  de los rule-ids que reporto.

## Do / Don't
- DO gatear la cobertura en LAS DOS direcciones: todo rule-id que un
  validador pueda emitir tiene receta, y ninguna receta documenta un codigo
  que ningun validador emite. Sin la segunda mitad el mapa acumula
  documentacion de reglas inexistentes.
- DO extraer los codigos del fuente de los validadores en el test, no de una
  lista mantenida a mano: la lista se desincroniza, el fuente no.
- DON'T asumir un unico formato de emision: un rule-id aparece como literal
  (`_finding(f, 'FM_KEY', ...)`) Y embebido en el texto impreso
  (`print("ERROR [CONFIG_MISSING]: ...")`), y no todos llevan guion bajo
  (`INDEX`, `LINK`, `ORPHAN`, `TAGS`, `TYPE`, `JSON`). Cubrir solo una forma
  deja codigos reales sin cobertura garantizada.
- DON'T agregarlo a `GATE_SPECS` de `mcp_gate_dispatch` ni a
  `.github/workflows/validate.yml`: no es un gate. Promoverlo seria su
  propio contrato con re-sellado explicito.
- DON'T enriquecer gates que reenvian salida ajena
  (`validate_test_commands` ejecuta la suite del proyecto y reimprime sus
  findings): daria recetas para problemas que no existen en el repo.

## Tests
Oraculo congelado en `tests/test_rule_hints.py` (sellado en `tests_sha256`):
6 tests — cobertura en ambas direcciones extrayendo los codigos del fuente
de los 13 validadores, recetas accionables (longitud minima y que ninguna
sea el fallback disfrazado), `hint_for` con fallback en vez de excepcion, y
`enrich` agregando `hint` sin mutar la entrada.
`python -m unittest tests/test_rule_hints.py`.

## Constraints
- `touch_only: scripts/rule_hints.py` — el oraculo, este contrato y la doc
  los gobierna el orquestador.
- Budget: complejidad ciclomatica <= 12, anidamiento <= 3 (medidos: 10 y 2,
  ambos en `main`, que despacha los flags del CLI).
- `test_command` < 120s (lo ejecuta `validate_test_commands` en CI).
- PARAR y reportar si: cumplir un test del oraculo exige tocar archivos
  fuera de `touch_only` (p.ej. cambiar un validador para que emita otro
  codigo). Documentar con evidencia; prohibido editar el oraculo.
