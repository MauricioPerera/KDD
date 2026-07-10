---
type: 'Task Contract'
title: 'Checker de cableado de agentes'
description: 'Integridad referencial del triangulo agente-skills-MCP: toda skill/servidor referenciado debe existir en su registro y todo agente referenciado debe estar declarado. Cierra por codigo la frontera code_only del dominio agent-wiring (refs bajo each, primera aparicion de la clase).'
tags: ['ccdd', 'agentes', 'wiring', 'example']

task: check-agent-wiring
intent: "Validar la integridad referencial del cableado agente-skills-MCP de un record de wiring."
target: src/check_agent_wiring.py
signature: "def check_agent_wiring(record) -> list"
test_command: "python -m unittest tests/test_check_wiring.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_check_wiring.py"
tests_sha256: "47d4c06151ce70ff678bc211eb837e2c9f488b22c8d6cd11ba7484ffd7c90571"
touch_only: ['src/check_agent_wiring.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Checker de cableado de agentes (check_agent_wiring)

## Intent
Cerrar por código la frontera `code_only` del dominio agent-wiring
([agent_wiring.md](../data_models/agent_wiring.md)): las referencias cruzadas
entre colecciones bajo `each` que la familia `refs` no alcanza. Precedente:
C22 (ciclos de grafo). Spec: `specs/CONTRACT-26-agent-wiring.md`.

## Interface
`check_agent_wiring(record) -> list` de violaciones canónicas ordenadas.
Semántica, formato exacto de mensajes, saltos y robustez: docstring del
oráculo congelado `tests/test_check_wiring.py`.

## Invariants
- SOLO integridad referencial: presencia de campos es trabajo de las reglas
  declarativas (entradas incompletas se saltan; no duplicar `required`).
- Mensajes ASCII con la forma canónica exacta del oráculo (índice + nombre).
- Orden determinista: colección alfabética, índice ascendente.
- Nunca lanza con records raros; stdlib puro; sin red/subprocess/LLM.

## Examples
- Cableado íntegro -> `[]`.
- `{"agent": "pm-nativo", "skill": "fantasma"}` con registro sin "fantasma"
  -> `["agent_skills: entrada 0: skill 'fantasma' no registrada"]`.

## Do / Don't
- DO: sets de nombres declarados/registrados; recorrido simple por colección.
- DON'T: tocar `tests/test_check_wiring.py` (oráculo congelado, sellado).
- DON'T: validar presencia/tipos del record (eso es del rule contract).

## Tests
`python -m unittest tests/test_check_wiring.py` en verde SIN modificar el
oráculo; suite completa sin regresiones.

## Constraints
- Tocar SOLO: `src/check_agent_wiring.py`. Reporte local en
  `.agents/logs/C26-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oráculo exigiera comportamiento contradictorio o el
  budget de complejidad no alcanzara sin romper un test.
