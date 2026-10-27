---
type: 'Task Contract'
title: 'Configuracion de aprobaciones coherente en el onboarding'
description: 'Alinear README y nodos canonicos con el registro externo del workflow generado.'
tags: ['documentation', 'approval', 'integration']
task: approval-onboarding-consistency
intent: 'Permitir que el equipo configure el CI siguiendo cualquiera de las entradas documentadas.'
target: README.md
language: markdown
signature: 'README onboarding and canonical approval configuration'
test_command: 'python -m unittest tests/test_approval_onboarding_consistency.py'
budget:
  cyclomatic_max: 8
  nesting_max: 3
tests: tests/test_approval_onboarding_consistency.py
tests_sha256: 'c3ca8655c0190e7c67b74ebd679154c1f476312842535649c1b764fef5563c72'
touch_only: ['README.md', 'knowledge/validacion.md', 'knowledge/verification-guarantees.md']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [protocolo de correccion](../audit-quality-cache-onboarding.md)
y enlazar el [registro externo](../approval-registry.md) como fuente unica.

## Interface
Las tres entradas de inicializacion del README y los dos nodos canonicos
describen registro por arbol para modo nativo e inputs explicitos para reusable.
Conservar politica propia, revision humana, calidad obligatoria y dos rondas.

## Invariants
No indicar configurar las dos variables globales antiguas como alternativa
al registro. No aprobar HEAD ni inferir aprobaciones. La guia generada sigue
coherente. Documentacion historica fechada y reglas ajenas quedan intactas.

## Examples
- Registro revisado por arbol: selector y calidad reales pasan dos rondas.
- Solo variables antiguas: falla antes de checks, sin imprimir PASS quality.
- Arbol o referencia de calidad ausente: rechazo explicito.

## Do / Don't
- DO: enlazar la fuente normativa y ejecutar cuerpos reales del workflow.
- DON'T: cambiar el selector para acomodar documentacion obsoleta o habilitar fallback.

## Tests
tests/test_approval_onboarding_consistency.py crea un proyecto Git propio y
ejecuta bootstrap/seleccion/calidad reales. Se ejecuta tambien en una copia
ya inicializada sin inicializarla otra vez ni omitir sus checks aplicables.

## Constraints
PARAR y reportar si se necesita cambiar el selector, un workflow, otra
referencia aprobada o una proteccion remota.
Sin cambios en workflows, bootstrap o selector para este P2. Conservar las
tres traducciones. Baseline revisado antes de actualizar los documentos.
