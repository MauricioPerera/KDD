---
type: 'Task Contract'
title: 'Instalación reutilizable de KDD en repositorios existentes'
description: 'Instala el validador fijado de KDD con un plan reversible y repetible.'
tags: ['adoption', 'plugin', 'git', 'validation']
task: reusable-kdd-adoption
intent: 'Incorporar la validación KDD a un repositorio Python existente.'
target: 'scripts/adopt_project.py'
signature: 'def main(argv=None) -> int:'
test_command: 'python -m unittest tests/test_adopt_project.py'
test_runner: python-unittest
oracle_files: ['tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt', 'scripts/validate_contracts.py', 'scripts/validate_okf.py', 'scripts/validate_test_commands.py', 'scripts/oracle_execution.py', 'scripts/oracle_inventory.py', 'scripts/validation_runtime.py', 'scripts/process_tree.py', 'scripts/unittest_oracle_runner.py']
budget:
  cyclomatic_max: 12
  nesting_max: 3
tests: 'tests/test_adopt_project.py'
tests_sha256: 'c94ba967ce3344552c5f067431ea2193e84b15b2f342992d8e10b4bf7c69c8a8'
touch_only: ['scripts/adopt_project.py', 'tools/kdd-adoption/**', 'plugins/kdd-codex/skills/kdd-workflow/SKILL.md', 'plugins/kdd-codex/README.md']
deps_allowed: ['git']
forbids: ['llm']
---

# Instalación reutilizable de KDD

## Intent

Convertir el [piloto](../piloto-kdd-complemento.md) en un paso de adopción que el responsable pueda previsualizar y repetir. El proyecto ya tiene Git, un índice OKF y un directorio explícito de contratos preparados por el responsable. Los contratos, los oráculos y el CI existente pertenecen al proyecto.

La evolución del piloto se define en [referencia de calidad](adoption-quality-reference.md),
[control de PR](adoption-trusted-pr.md), [preparación Python](adoption-python-preparation.md)
y [ciclo del pin](adoption-validator-pin-lifecycle.md). Sus opciones explícitas
amplían la instalación original descrita aquí.

## Interface

```text
python scripts/adopt_project.py --repo-root RUTA --contracts-dir knowledge/contracts --validator-commit SHA --plan
python scripts/adopt_project.py --repo-root RUTA --contracts-dir knowledge/contracts --validator-commit SHA --apply
```

El plan enumera, en JSON, las rutas relativas en `create` y `keep` con estado `planned`. La aplicación devuelve las mismas listas con estado `applied`, o `unchanged` si no creó archivos. Las rutas están ordenadas. Los errores devuelven un código distinto de cero y un diagnóstico que empieza con `ADOPTION_`.

El perímetro de escritura son tres archivos de texto. El lock `.kdd/validator.lock` contiene el SHA completo del validador. El lanzador `.kdd/validate.py` fija el directorio de contratos solicitado. El workflow `.github/workflows/kdd-validate.yml` usa Python 3.11 en Ubuntu y Windows con permisos de lectura. El perfil piloto ejecuta el lanzador del checkout en push y ejecución manual. El control aprobado de PR aplica el contrato enlazado arriba.

## Invariants

- El destino es la raíz física de un repositorio Git con historial. El directorio de contratos es relativo, está bajo `knowledge/contracts`, contiene al menos un contrato real en ese directorio exacto y tiene un índice OKF existente. Los caminos deben mantenerse dentro del repositorio.
- `--plan` deja intacto el árbol de trabajo. `--apply` conserva los archivos coincidentes, incluidos los checkouts con finales CRLF. Un SHA distinto, una colisión de contenido, un destino no regular o un ancestro enlazado se informa antes de escribir cualquier archivo. Una ruta administrada ausente del árbol de trabajo pero presente en HEAD o en el índice se trata como colisión y conserva su estado.
- La aplicación por defecto crea únicamente archivos ausentes. El cambio explícito de pin actualiza el lock según su contrato. Si falla una escritura, se recuperan las rutas administradas afectadas. El comando admite un solo escritor en el árbol de trabajo durante la aplicación.
- El lanzador obtiene el commit fijado del repositorio oficial de KDD y verifica su identidad y los archivos ejecutados según el diseño del piloto. Terminal, Codex y Actions usan la misma entrada. Este perfil ejecuta los validadores fijados de contratos y OKF y el runner gestionado `python-unittest` sobre el directorio seleccionado. Rechaza en la etapa de contrato cero archivos ejecutables, también después de instalar. El registro `KDD_PILOT` informa SHA solicitado, SHA comprobado, etapa, casos y resultado. La selección de política se rige por el contrato de referencia de calidad.
- La adopción preserva el producto, sus contratos, sus pruebas, sus workflows y sus modificaciones locales. La política de calidad del consumidor conserva su aprobación independiente.

## Examples

- Aplicar el mismo SHA dos veces -> la segunda aplicación devuelve `unchanged` con las tres rutas en `keep`.
- Un workflow existente ocupa la ruta del plan con otros bytes -> devuelve `ADOPTION_CONFLICT` con su ruta y conserva todo el árbol de trabajo.

## Do / Don't

- DO usar la operación de previsualización y el [mecanismo de recuperación de escrituras](bootstrap-transaction.md) cuando se mantenga su perímetro.
- DON'T usar el inicializador de una copia de la plantilla sobre el repositorio consumidor ni escribir encima de un archivo existente.

## Tests

Las pruebas del instalador crean repositorios con Git real en directorios temporales. El oráculo analiza el YAML con PyYAML del lock existente y verifica sus relaciones de jobs y pasos. El inventario protege los ocho módulos de KDD que copia el repositorio Git controlado. Un centinela verifica que los rechazos previos de sello o aprobación no ejecuten el oráculo. Ejercen previsualización, instalación, reaplicación, checkout con CRLF, colisiones, SHA inválido, rutas inválidas, borrados locales de destinos administrados y recuperación de una segunda escritura parcial. Un repositorio Git local con scripts reales de KDD verifica A → B → A, la regresión y la reversión desde el lanzador instalado. Prueba también commit inexistente, SHA resuelto discrepante, blob alterado, sello incorrecto y falta de referencia de calidad. La prueba posterior en un segundo repositorio debe conservar su suite original y ejecutar el lanzador instalado en Ubuntu y Windows.

Los casos de filesystem fijan la resolución del pin para poder aislar sus
escrituras. La resolución real del instalador se verifica con repositorios
Git locales en el oráculo del ciclo del pin.

## Constraints

PARAR y reportar si se necesita cambiar la aprobación del consumidor, publicar el complemento o ampliar el perímetro de escritura del instalador. La publicación y la comprobación del workflow sobre un consumidor remoto requieren su propia verificación.
