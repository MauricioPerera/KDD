---
type: 'Task Contract'
title: 'Regla de contexto presupuestado en las reglas de agentes'
description: 'Ancla el ensamblador de contexto CCDD Nivel 2 como paso obligatorio de la delegación, con un test de coherencia que fija la regla.'
tags: ['ccdd', 'agents', 'context', 'coherencia']

task: agents-context-rule
intent: "Anclar el ensamblador de contexto como paso obligatorio de las reglas de agentes con un test de coherencia."
target: tests/test_agents_rules.py
signature: "def test_agents_md_references_assembler(self) -> None:"
test_command: "python -m unittest tests/test_agents_rules.py"
budget:
  max_cyclomatic_complexity: 5
  max_nesting_depth: 3
tests: "tests/test_agents_rules.py"
tests_sha256: "479a23349260b9e0b98c2b2e1504720bae3a9c18a29306c35145936f021446c4"
touch_only: ['tests/test_agents_rules.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: agents-context-rule

## Intent
Que ningún agente que clone el repo se pierda el ensamblador de contexto: la regla vive en
`.agents/AGENTS.md` y en la skill híbrida, y el test de coherencia (el target de este
contrato) las fija contra la herramienta real. Contexto: [metodología de
ejecución](../metodologia-ejecucion.md).

## Interface
```python
class TestAgentsRules(unittest.TestCase):
    def test_agents_md_references_assembler(self) -> None: ...
    def test_skill_references_assembler(self) -> None: ...
    def test_referenced_files_exist(self) -> None: ...
```
La "implementación" de esta tarea incluye las ediciones documentales que el test fija:
la regla nueva en `.agents/AGENTS.md` y la sección nueva en
`.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md`.

## Invariants
- El test lee archivos con `pathlib`/`open` (UTF-8); sin red, sin subprocess, sin mocks.
- `.agents/AGENTS.md` y la SKILL referencian literalmente `scripts/assemble_context.py` y
  `ccdd/context.json`; ambos archivos existen en el repo.
- Los puentes raíz (`AGENTS.md`, `CLAUDE.md`) no se modifican.
- Quitar la mención del script de AGENTS.md pone el test en rojo.

## Examples
- Repo tras la tarea: `python -m unittest tests/test_agents_rules.py` -> OK (3 tests).
- Mutación: borrar la línea del ensamblador de `.agents/AGENTS.md` -> el test falla con
  mensaje que nombra el archivo y la referencia faltante.

## Do / Don't
- DO: mensajes de aserción que digan QUÉ referencia falta y EN QUÉ archivo.
- DO: regla y sección nuevas cortas, referenciando por ruta (sin duplicar doc del ensamblador).
- DON'T: tocar scripts/, ccdd/, src/, tests existentes, README ni los puentes raíz.

## Tests
(Los tests están en `tests/test_agents_rules.py` — el target de este contrato.)

## Constraints
- PARAR y reportar si... fijar la regla exigiera modificar el ensamblador o el contrato de
  contexto (fuera de alcance), o si algún test existente se rompiera con el cambio.
