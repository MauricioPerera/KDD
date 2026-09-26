---
type: 'Task Contract'
title: 'Integrar el gate nativo de nivel 2'
description: 'Adaptar contratos KDD al motor CCDD local sin transporte MCP ni degradacion silenciosa.'
tags: ['ccdd', 'native', 'gate']
task: native-level2
intent: 'Ejecutar el gate CCDD nativo con evidencia verificable.'
target: scripts/native_level2.py
signature: 'def run_level2(contract, repo_root, engine_root, *, python=None, timeout=120):'
test_command: 'python -m unittest tests.test_native_level2'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: tests/test_native_level2.py
tests_sha256: '79e9af913b41d12fd421d91c7f5a2198001875e3fcb398358946d60d91fd77d0'
touch_only: ['scripts/native_level2.py', 'scripts/native_level2_worker.py', 'scripts/setup_native_level2.py']
deps_allowed: ['stdlib', 'scripts.validate_contracts', 'scripts.native_level2', 'pyyaml', 'jsonschema', 'ccdd-gate']
forbids: ['llm']
---

## Intent
Aplicar [el perfil nativo](../native-level2.md) conservando el motor upstream.

## Interface
run_level2 devuelve un dict serializable con veredicto y evidencia. CLI documentada
en el nodo de arquitectura. Setup independiente y explicito, sin instalar al verificar.

## Invariants
- No ejecutar antes de comprobar contrato, sello y revision del motor.
- No convertir error, timeout o capacidad ausente en PASS.
- No modificar contrato, target ni oraculo; exports exclusivos y temporales.
- Preservar test_command y explicitar cwd/presupuesto efectivos.
- Cambios de entradas durante ejecucion invalidan PASS.

## Examples
- Contrato valido y motor PASS -> ok true con hashes.
- Oraculo cambiado -> INVALID antes de invocar tests.

## Do / Don't
- DO: usar motor real fijado, pruebas negativas y evidencia.
- DON'T: duplicar algoritmos de metricas ni afirmar sandbox o firma humana.

## Tests
Oraculo congelado tests/test_native_level2.py, escrito antes de implementar.
Prueba real adicional contra checkout upstream en entorno limpio para paridad.

## Constraints
PARAR y reportar si requiere ampliar a lenguajes/grupos, modificar el motor upstream
o publicar GitHub. subprocess esta permitido por intent; network solo en setup.
Nivel 2 del propio adaptador no medido; budget declarativo hasta evidencia explicita.
