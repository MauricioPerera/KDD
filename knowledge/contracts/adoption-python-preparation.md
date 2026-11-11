---
type: 'Task Contract'
title: 'Preparar proyectos Python existentes antes de validar'
description: 'Instalar dependencias fijadas y un proyecto con estructura src en un entorno temporal.'
tags: ['adoption', 'python', 'integration']
task: adoption-python-preparation
intent: 'Preparar la ejecución del oráculo gestionado con las dependencias del consumidor.'
target: tools/kdd-adoption/validate.py
language: python
signature: 'def validate(record):'
test_command: 'python -m unittest tests/test_adoption_python_preparation.py'
test_runner: python-unittest
oracle_files: ['tests/test_adoption_python_preparation.py', 'tests/adoption_remediation_support.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: tests/test_adoption_python_preparation.py
tests_sha256: '422b65e6c51a5823991f707bea6a9425a57edce4a797e8f934b5eb6fa7161940'
touch_only: ['scripts/adopt_project.py', 'tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md']
deps_allowed: ['stdlib', 'git', 'pip']
forbids: ['llm']
---

## Intent

Permitir que el [perfil de adopción](reusable-kdd-adoption.md) ejecute
oráculos de proyectos instalables y con dependencias.

## Interface

`adopt_project.py` admite `--requirements-file RUTA` y
`--install-project` de forma independiente. La ruta relativa exacta se
revisa en el plan y queda en el lanzador generado junto a la opción de
instalar el proyecto. Terminal, Codex y Actions ejecutan el mismo lanzador.

## Invariants

- Se usa Python 3.11. Sin opciones, el lanzador usa su intérprete actual.
  Con opciones, crea un venv temporal fuera del consumidor y lo prepara una vez
  para ambas pasadas.
- El manifiesto debe ser un archivo regular interno. Con baseline, coincide
  con la versión aprobada antes de pasarlo a pip. Las dependencias se instalan
  con `--require-hashes`. Si se pidió instalar el proyecto, pip instala el
  checkout con `--no-deps --no-build-isolation`, usando herramientas de
  compilación proporcionadas por el entorno preparado.
- Se ejecuta preparación después de comprobar el baseline del PR. Un error de
  ruta, venv, hash o instalación falla antes de calidad y del oráculo.
  La instalación no requiere editar archivos de producto ni instalar paquetes
  en el intérprete global. Un backend aprobado puede crear artefactos en su
  checkout. El venv se descarta al finalizar.

## Examples

- Wheel local con hash aprobado → la prueba puede importar el paquete.
- Hash distinto → fallo en preparación, sin ejecutar la prueba.
- Paquete con layout `src/` → se instala antes de las dos pasadas.

## Do / Don't

- DO documentar dependencias y backend fijados y los artefactos de compilación.
- DON'T deducir comandos de instalación de archivos candidatos ni aceptar
  comandos shell arbitrarios en el instalador.

## Tests

Git, venv, pip y wheels locales reales. Comprueban import de dependencia,
hash inválido y paquete con layout src con backend local sin red.

## Constraints

Python 3.11 y runner gestionado `python-unittest`. Los oráculos no descargan
dependencias externas.
PARAR y reportar si se necesita otro runtime o una dependencia sin revisión.
