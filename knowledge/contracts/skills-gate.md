---
type: 'Task Contract'
title: 'Gate de skills de agente'
description: 'Validador determinista de las skills del repo (skills/ y .agents/skills): estructura, frontmatter, cuerpo, enlaces y unicidad de nombres. Infraestructura, no ejemplo.'
tags: ['ccdd', 'skills', 'gate', 'infra']

task: skills-gate
intent: "Implementar el gate determinista de skills de agente contra su oraculo congelado."
target: scripts/validate_skills.py
signature: "def validate_skills(skill_dirs) -> list"
test_command: "python -m unittest tests/test_validate_skills.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_skills.py"
tests_sha256: "35f2a4a4b11c120a85135e37517de84b3d8b82d27ae661af805c49e6250cff4a"
touch_only: ['scripts/validate_skills.py', 'tests/test_parser_coherence.py']
deps_allowed: []
forbids: ['network', 'subprocess', 'llm']
---

# Contract: Gate de skills (validate_skills)

## Intent
Implementar `scripts/validate_skills.py`: el gate de nivel 1 que valida las
skills de agente del repo (`skills/` y `.agents/skills`) — estructura,
frontmatter, cuerpo, enlaces y unicidad de nombres. Es INFRAESTRUCTURA:
custodia activos reales, no ejemplos. Spec: `specs/CONTRACT-24-skills-gate.md`.

## Interface
- `validate_skills(skill_dirs) -> list` — lista de directorios; cada
  SUBDIRECTORIO INMEDIATO es una skill que debe tener `SKILL.md` (archivos
  sueltos en el dir se ignoran). Devuelve findings `{'file','level','rule','msg'}`
  ordenados por (file, rule); rutas posix ('/'). Dir inexistente -> finding
  INFO `DIR_MISSING` (no es error).
- `main(argv) -> int` — CLI `python scripts/validate_skills.py [dir ...]`
  (default `skills .agents/skills`); imprime findings + `Resumen` honesto;
  exit 0 sin ERRORs, 1 con >=1.
- Reglas y semantica EXACTAS: docstring del oraculo congelado
  `tests/test_validate_skills.py` (SKILL_MISSING, FM_PARSE, FM_NAME,
  FM_NAME_KEBAB, FM_NAME_DIR, FM_DESC, FM_DESC_LEN [50,1024], BODY_EMPTY,
  LINK_BROKEN, NAME_DUP, DIR_MISSING).

## Invariants
- Python stdlib puro; sin red, sin subprocess, sin LLM; determinista.
- Parser de frontmatter: COPIA del mini-YAML de `scripts/validate_okf.py`
  (`_split_inline_list`, `_parse_scalar`, `_parse_block`, `parse_frontmatter`)
  con los MISMOS nombres — la coherencia del dialecto se fija extendiendo
  `tests/test_parser_coherence.py` a 3 vias (importar `validate_skills` y
  comparar contra los otros dos con las MISMAS fixtures; solo AGREGAR, no
  debilitar lo existente).
- Stripping de code spans y fences antes de extraer enlaces: misma semantica
  que `_strip_code` de `validate_okf.py`.
- Mensajes de findings y prints en ASCII (gate `lint_ascii`).
- Archivos leidos con `encoding='utf-8'` (las skills reales tienen acentos).

## Examples
- `validate_skills(['skills', '.agents/skills'])` sobre el repo real -> sin
  ERRORs (los 3 enlaces rotos ya fueron reparados por el orquestador).
- Subdir `sk/a-vacia/` sin SKILL.md -> `SKILL_MISSING` con file `.../a-vacia`.
- `description` de 49 chars -> `FM_DESC_LEN` con "49" en el msg.

## Do / Don't
- DO: estilo de `validate_rules.py`/`validate_okf.py` (findings, Resumen).
- DON'T: tocar `tests/test_validate_skills.py` (oraculo congelado, sellado).
- DON'T: tocar otros scripts, skills, nodos ni workflows.
- DON'T: dependencias externas (PyYAML incluido) ni heuristicas no testeadas.

## Tests
`python -m unittest tests/test_validate_skills.py` debe pasar SIN modificar el
oraculo. Ademas `python -m unittest tests/test_parser_coherence.py` en verde
tras la extension a 3 vias, y la suite completa
`python -m unittest discover -s tests` sin regresiones.

## Constraints
- Tocar SOLO: `scripts/validate_skills.py` y `tests/test_parser_coherence.py`
  (solo extender a 3 vias). Reporte local en `.agents/logs/C24-REPORT.md`.
- NO commitear (el PM commitea tras verificar).
- PARAR y reportar si: el oraculo exigiera comportamiento contradictorio; la
  extension a 3 vias no pudiera pasar sin modificar los otros dos parsers; o
  el budget de complejidad no alcanzara sin romper un test.
