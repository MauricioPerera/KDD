---
type: 'Task Contract'
title: 'Preparar proyectos Python existentes antes de validar'
description: 'Preparar ruedas fijadas y un proyecto con estructura src en un entorno temporal.'
tags: ['adoption', 'python', 'integration']
task: adoption-python-preparation
intent: 'Preparar la ejecución del oráculo gestionado con las dependencias del consumidor.'
target: tools/kdd-adoption/validate.py
language: python
signature: 'def validate(record):'
test_command: 'python -m unittest tests/test_adoption_python_preparation.py'
test_runner: python-unittest
oracle_files: ['tests/test_adoption_python_preparation.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt', 'scripts/validate_contracts.py', 'scripts/validate_okf.py', 'scripts/validate_test_commands.py', 'scripts/validate_baseline.py', 'scripts/verify_quality.py', 'scripts/oracle_execution.py', 'scripts/oracle_inventory.py', 'scripts/validation_runtime.py', 'scripts/process_tree.py', 'scripts/unittest_oracle_runner.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_adoption_python_preparation.py
tests_sha256: '0678816b9248aa71f29702075fc74785fa76f3fc7a091d5b20cd3d1ea67bcd99'
touch_only: ['scripts/adopt_project.py', 'tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib', 'git', 'pip']
forbids: ['llm']
---

## Intent

Permitir que el [perfil de adopción](reusable-kdd-adoption.md) ejecute
oráculos de proyectos instalables y con dependencias.

## Interface

`adopt_project.py` admite `--requirements-file RUTA` y `--source-dir RUTA`
de forma independiente. Las rutas relativas exactas se revisan en el plan y
quedan en el lanzador generado. Terminal, Codex y Actions ejecutan el mismo
lanzador. El directorio fuente admite proyectos Python puros con layout src.

## Invariants

- Se usa Python 3.11. Sin opciones, el lanzador usa su intérprete actual.
  Con opciones, crea un venv temporal fuera del consumidor y lo prepara una vez
  para ambas pasadas.
- El manifiesto debe ser un archivo regular interno. Con baseline, coincide
  con la versión aprobada antes de pasarlo a pip. Enumera todas las ruedas
  directas y transitivas como `nombre==versión` y hashes SHA-256. Permite
  continuaciones, comentarios, `--no-index` y `--find-links` a un directorio
  relativo interno. Rechaza archivos incluidos, URLs, opciones de build
  y dependencias sin pin o hash. Pip instala con
  `--require-hashes --only-binary=:all: --no-deps`.
- La ruta fuente se registra como ruta de importación del entorno preparado.
  Se rechazan ancestros enlazados y módulos o paquetes de inicio
  `sitecustomize` y `usercustomize` en esa ruta. La preparación no ejecuta un
  backend de build del candidato ni intenta construir sdists. Proyectos que
  necesitan compilación o metadatos de instalación conservan su CI de paquete.
- Se ejecuta preparación después de comprobar el baseline del PR. Un error de
  ruta, venv, hash o instalación falla antes de calidad y del oráculo.
  La instalación no requiere editar archivos de producto ni instalar paquetes
  en el intérprete global. El venv se descarta al finalizar.

## Examples

- Wheel local con hash aprobado → la prueba puede importar el paquete.
- Hash distinto → fallo en preparación, sin ejecutar la prueba.
- Paquete con layout `src/` → se importa con el código del candidato y el
  backend de compilación no se ejecuta.

## Do / Don't

- DO documentar las ruedas requeridas por todas las dependencias.
- DON'T deducir comandos de instalación de archivos candidatos ni aceptar
  comandos shell arbitrarios en el instalador.

## Tests

Git, venv, pip y ruedas locales reales. Comprueban import de dependencia,
hash inválido, rechazo de configuración incluida y paquete con layout src
sin ejecutar el backend. Un módulo de arranque candidato se rechaza antes
del oráculo.

## Constraints

Python 3.11 y runner gestionado `python-unittest`. Los oráculos no descargan
dependencias externas.
PARAR y reportar si se necesita otro runtime o una dependencia sin revisión.
