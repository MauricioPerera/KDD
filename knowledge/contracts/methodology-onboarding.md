---
type: 'Task Contract'
title: 'Mantener instrucciones metodologicas ejecutables'
description: 'Comprueba el tutorial con oraculo real y reconcilia guias, plantillas y limites.'
tags: ['ccdd', 'documentation', 'verification']
task: methodology-onboarding
intent: 'Comprobar que las instrucciones operativas producen contratos y pruebas validos.'
target: scripts/validate_documentation_examples.py
signature: 'def verify_documentation_examples(repo_root) -> dict'
test_command: 'python -m unittest tests.test_methodology_docs'
test_runner: python-unittest
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 65
  params_max: 5
tests: tests/test_methodology_docs.py
tests_sha256: 8b7bf6b979f4221d988a1408630bbbc8cbb12d8d56a871a7374920a6f2d9d284
oracle_files: ['tests/test_methodology_docs.py', 'tests/__init__.py']
touch_only: ['scripts/validate_documentation_examples.py', 'knowledge/*.md', 'knowledge/contracts/TEMPLATE-task-contract.md', '.agents/skills/kdd-okf-ccdd-hybrid/SKILL.md', '.agents/AGENTS.md', 'README.md', '.github/workflows/validate.yml']
deps_allowed: []
forbids: ['network', 'llm']
---

## Intent
Resolver la divergencia entre documentos y ejecucion reconocida en [las garantias](../verification-guarantees.md), usando una plantilla unica y escenarios reales del [quickstart](../quickstart.md).

## Interface
El verificador extrae las muestras normativas del tutorial, crea un proyecto temporal y comprueba contrato valido, stub rechazado e implementacion aprobada con dos casos reales.

## Invariants
- La skill referencia la plantilla canonica en vez de reproducir un contrato obsoleto.
- Los requisitos declarados incluyen runtimes y dependencias usados por el recorrido completo.
- El oraculo del tutorial falla sobre el stub y aprueba la implementacion documentada.
- Dos corridas se describen como comprobacion basica de repetibilidad, sin promesa de ausencia de flaky.

## Constraints
PARAR y reportar si una muestra no se puede extraer o ejecutar. No modificar historia congelada para actualizar instrucciones actuales. El recorrido de clonacion e inicializacion se comprueba ademas en copia limpia; no se autentican aprobaciones humanas.

## Examples
- Un nombre de budget que el validador rechaza no debe aparecer como campo de un ejemplo operativo en la skill.
- El stub de saludar falla antes de sustituirse por la implementacion del mismo tutorial.

## Do / Don't
- DO: extraer muestras de la guia real y fallar si faltan.
- DON'T: validar copias de muestras desconectadas de lo que lee el usuario.

## Tests
El oraculo ejecuta muestras, valida contrato y cuenta casos; tambien comprueba plantilla unica, requisitos y ausencia de afirmaciones metodologicas excesivas.
