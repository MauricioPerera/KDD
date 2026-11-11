---
type: 'Task Contract'
title: 'Verificar y actualizar el pin de adopción de KDD'
description: 'Resolver el commit antes de escribir y permitir actualizar o revertir el lock con revisión explícita.'
tags: ['adoption', 'git', 'installation']
task: adoption-validator-pin-lifecycle
intent: 'Evitar instalaciones con un validador inaccesible y habilitar el ciclo A a B a A.'
target: scripts/adopt_project.py
language: python
signature: 'def main(argv=None) -> int:'
test_command: 'python -m unittest tests/test_adoption_validator_pin.py'
test_runner: python-unittest
oracle_files: ['tests/test_adoption_validator_pin.py', 'tests/adoption_remediation_support.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 3
tests: tests/test_adoption_validator_pin.py
tests_sha256: '2564a16294b02ccc47fde97f1971b808516d59275c5283759edfe5d4e9607caf'
touch_only: ['scripts/adopt_project.py', 'tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Corregir la instalación que escribía un pin inexistente y convertir el cambio
de pin en un plan explícito del [instalador](reusable-kdd-adoption.md).

## Interface

`--validator-commit NUEVO --plan|--apply` comprueba el commit en el origen
oficial antes de devolver éxito o escribir. Para una instalación existente
`--expected-validator-commit ANTERIOR` permite actualizar el lock cuando el
valor coincide con el esperado y los tres archivos pertenecen al plan actual.
El resultado incluye `update` con la ruta del lock cuando lo cambia. Para
revertir se intercambian NUEVO y ANTERIOR.

## Invariants

- La resolución se hace por SHA completo en Git temporal sin reemplazos.
  Se exige un objeto commit exacto. Un fallo del fetch o discrepancia de SHA
  devuelve `ADOPTION_PIN` y conserva el árbol, el índice y HEAD.
- El cambio esperado se verifica antes de escribir. El plan es de solo
  lectura en el consumidor. Un conflicto, una instalación parcial o una
  plantilla distinta requieren revisión y bloquean el cambio de pin.
- La aplicación actualiza solo el lock, de forma atómica y recuperable con un
  escritor. Cambiar el pin sin declarar el anterior conserva el rechazo previo.
- La actualización de las plantillas antiguas se revisa aparte del cambio de
  SHA. Con aprobación externa, el consumidor registra otro baseline si
  cambió un archivo protegido.

## Examples

- Instalar A, previsualizar y aplicar A → B, previsualizar y aplicar B → A.
- SHA inexistente en plan o aplicación → error antes de escribir.
- Plan esperado A sobre lock B → conflicto y bytes intactos.

## Do / Don't

- DO reutilizar el transporte del lanzador para comprobar el objeto.
- DON'T reescribir un lanzador o workflow local como parte de cambiar el pin.

## Tests

Instalador en repositorios Git existentes y dos commits de un origen Git
local, con transportes controlados y real verificación de objetos.

## Constraints

El instalador administra las mismas tres rutas. Las pruebas usan Git local
sin depender de GitHub. El cambio de aprobación externa requiere revisión.
PARAR y reportar si se necesita cambiar una referencia remota del consumidor.
