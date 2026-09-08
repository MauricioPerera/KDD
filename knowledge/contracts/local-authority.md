---
type: 'Task Contract'
title: 'Aplicar autoridad en ejecutor local'
description: 'Comprobar permisos antes del IO y restringir handles delegados con cuotas compartidas.'
tags: ['authority', 'ccdd', 'executor']
task: local-authority
intent: 'Permitir operaciones locales autorizadas y rechazar ampliaciones antes de efectos.'
target: src/authority_executor.py
signature: 'def execute(self, request: dict) -> dict:'
test_command: 'python -m unittest tests.test_authority_executor'
budget:
  cyclomatic_max: 15
  nesting_max: 3
tests: 'tests/test_authority_executor.py'
tests_sha256: '67c3f26657a76d5bae40564ad720b689d67d99089f8ddb031140c0fc3617a2d9'
touch_only: ['src/authority_executor.py', 'src/authority_policy.py']
deps_allowed: ['argparse', 'hashlib', 'json', 'os', 'pathlib', 'stat', 'threading', 'dataclasses', 'src.authority_policy']
forbids: ['network', 'subprocess']
---

# Ejecutor de autoridad local

## Intent
Implementar el [modelo de autoridad](../data_models/local-authority.md) sin modificar
el runner, el planificador ni los oraculos existentes. El host es confiable y el agente
entrega solicitudes de datos; no se ejecuta codigo proporcionado por el agente.

## Interface
`AuthorityExecutor(root, policy)`; `execute(request: dict) -> dict`;
`delegate(child_policy)` devuelve un handle restringido o PermissionError;
`operations_used` informa contador global y `audit_log` devuelve copia de eventos.
CLI documentada en el modelo. No hay concesion de autoridad via request.

## Invariants
- Aplicar schema, catalogo, rutas, protecciones y cuotas del modelo enlazado.
- Rechazos por permisos no crean directorios ni escriben archivos.
- Crear solo con apertura exclusiva; existentes nunca se sobrescriben.
- Los comandos son internos de lectura, sin shell/subprocess ni red.
- Delegacion reduce permisos, mantiene protecciones y comparte cuotas de ancestros.
- Operaciones concurrentes del mismo ejecutor respetan cuota bajo lock.
- Limites no soportados se rechazan; no se afirma sandbox de sistema operativo.

## Examples
- Crear allowed/new.txt bajo autoridad y touch_only coincidentes: ok true.
- Crear private/new.txt fuera del permiso: ok false, sin efectos y con escalation.
- Hijo solicita write ** con padre limitado: PermissionError, sin handle concedido.

## Do / Don't
- DO: proteger oraculos explicitamente y probar efectos reales con fixtures temporales.
- DON'T: permitir shell arbitraria, scripts del proyecto o usar politicas como texto orientativo.

## Tests
Oraculo tests/test_authority_executor.py escrito antes del codigo y sellado.
Pruebas de enlaces pueden SKIP solo si el sistema impide crear el fixture; reportarlo.

## Constraints
PARAR y reportar si requiere permisos del sistema adicionales, aislamiento de procesos
hostiles o modificar tests congelados. Nivel 2 no medido; budget declarativo.
