---
type: 'Task Contract'
title: 'Gate determinista de rule contracts'
description: 'Validador de rule contracts: estructura, familias conocidas, golden sellado por hash y reproduccion del golden por el motor declarativo; capa opcional.'
tags: ['ccdd', 'rule-contract', 'gate', 'validador']

task: rules-gate
intent: "Validar deterministicamente los rule contracts de un directorio: estructura, sello del golden y reproduccion por el motor."
target: scripts/validate_rules.py
signature: "def validate_rules(rules_dir: str) -> list:"
test_command: "python -m unittest tests/test_validate_rules.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_validate_rules.py"
tests_sha256: "6fcfbbb07a6b2c1be026c9a37ef75aa30b172e2190ea3ac8fd4340c7fd9a0482"
touch_only: ['scripts/validate_rules.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: rules-gate

## Intent
Darle a la vertiente [rule contract](../rule-contract-spec.md) su gate de nivel 1: lo que
`validate_contracts` es para los task contracts. Sin este gate, un rule-set con familias
mal tipeadas, golden aflojado o `code_only` sin razon pasa CI en silencio. Mismo movimiento
que C03/C09/C13: convertir la disciplina en check. Spec: `specs/CONTRACT-18-rules-gate.md`.

## Interface
```python
def validate_rules(rules_dir: str) -> list:
    """Valida todos los *.rules.json bajo rules_dir. Devuelve findings
    [{'file','level','rule','msg'}] ordenados (archivo, regla); vacia si todo es
    conforme O si el directorio no existe / no tiene rule-sets (capa opcional).
    No lanza ante rule-sets invalidos (reporta)."""
```
CLI: `python scripts/validate_rules.py [rules_dir]` -- estilo de `validate_okf.py`;
exit 0 sin ERRORs (incluye el caso capa-opcional, con INFO) - 1 con >=1 ERROR.

## Invariants
- Reglas y semantica EXACTAS del docstring del oraculo congelado: `JSON`, `FAMILIA`
  (top-level fuera de _comment + 7 familias + code_only + golden), `GOLDEN`,
  `GOLDEN_FROZEN` (sha256 LF-normalizado, mismo algoritmo que tests_sha256; msg con
  esperado y actual), `GOLDEN_FORMA`, `CODE_ONLY` (reason no vacia), `REPRO`
  (rule_engine.evaluate reproduce violations - code_only_miss por campo top-level,
  nombrando el caso divergente).
- El gate importa SOLO `rule_engine` (motor declarativo); JAMAS el validador de codigo de
  ningun dominio (los oraculos son independientes).
- Escanea SOLO `*.rules.json`; otros .json se ignoran. `golden.path` relativo al rule-set.
- Capa opcional: dir ausente o sin rule-sets -> findings vacios; el CLI lo anuncia (INFO).
- Determinista: findings ordenados (archivo, regla), estables entre corridas; stdlib puro;
  sin red; sin subprocess; sin LLM; mensajes ASCII.

## Examples
- Par rule-set+golden valido y sellado -> `[]` y CLI exit 0.
- Clave top-level `requird` (typo) -> ERROR `FAMILIA` nombrandola.
- Golden editado sin re-sellar -> ERROR `GOLDEN_FROZEN` con ambos hashes.
- Rule-set al que le falta una regla que el golden espera -> ERROR `REPRO` nombrando el caso.
- Directorio vacio o inexistente -> exit 0 con INFO (post-init verde).

## Do / Don't
- DO: espejar interfaz, formato de salida y estilo de `scripts/validate_okf.py`.
- DO: mensajes con archivo + regla + causa exacta; el de GOLDEN_FROZEN nombra el comando
  de sellado (`python scripts/validate_contracts.py --hash <golden>`).
- DON'T: red, subprocess, dependencias fuera de stdlib; importar validadores de dominio;
  ejecutar `code_only`; tocar rule_engine.py, su oraculo, el ejemplo de pagos o el CI.

## Tests
(Los tests estan en `tests/test_validate_rules.py`, autorados por el orquestador y
congelados por `tests_sha256`: el implementador no los escribe ni los modifica. Fixtures
en tempdir para cada regla + capa opcional + determinismo + ejemplo real del repo + CLI.)

## Constraints
- PARAR y reportar si... reproducir el golden exigiera importar el validador de codigo de
  un dominio, o si el oraculo congelado fuera internamente contradictorio.
