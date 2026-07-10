---
type: 'Task Contract'
title: 'Versionado de la plantilla: coherencia CHANGELOG/README/upgrade'
description: 'Test de coherencia que fija el versionado de la plantilla: CHANGELOG semver, mencion en README (EN/ES) y nodo de upgrade enlazado desde el index.'
tags: ['versionado', 'changelog', 'upgrade', 'coherencia', 'tooling']

task: versioning-plantilla
intent: "Fijar por test de coherencia el versionado de la plantilla: CHANGELOG, README y nodo de upgrade no pueden desincronizarse."
target: tests/test_versioning.py
signature: "def test_changelog_first_entry_is_semver(self) -> None:"
test_command: "python -m unittest tests/test_versioning.py"
budget:
  max_cyclomatic_complexity: 5
  max_nesting_depth: 3
tests: "tests/test_versioning.py"
tests_sha256: "0115ea5cd92b787cdc46f2e4717fe1d6f582fca711579d0ff2125b0416bae9e2"
touch_only: ['tests/test_versioning.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: versioning-plantilla

## Intent
Que la plantilla tenga versión y quien la instanció pueda traer mejoras: CHANGELOG con
semver, README que lo anuncia (EN/ES) y la historia de upgrade como nodo OKF. El test de
coherencia (target de este contrato) fija doc↔doc, patrón de
[agents-context-rule](./agents-context-rule.md). Spec:
`specs/CONTRACT-14-versionado-plantilla.md`; proceso: [metodología de
ejecución](../metodologia-ejecucion.md).

## Interface
```python
class TestVersioning(unittest.TestCase):
    def test_changelog_first_entry_is_semver(self) -> None: ...
    def test_readme_mentions_changelog_en_and_es(self) -> None: ...
    def test_upgrade_node_exists_and_indexed(self) -> None: ...
```
La "implementación" incluye los artefactos que el test fija: `CHANGELOG.md`,
`knowledge/plantilla-upgrade.md`, el enlace en `index.md` y la subsección del README.

## Invariants
- El test lee archivos con `pathlib`/`open` (UTF-8); sin red, sin subprocess, sin mocks.
- `CHANGELOG.md` existe y su primera entrada `## v` matchea `\d+\.\d+\.\d+`.
- README menciona `CHANGELOG.md` al menos una vez en la mitad EN y una en la ES.
- `knowledge/plantilla-upgrade.md` existe y `knowledge/index.md` lo enlaza.
- Mensajes de aserción que nombran QUÉ falta y EN QUÉ archivo.
- Borrar la entrada semver del CHANGELOG o el enlace del index pone el test en rojo.

## Examples
- Repo tras la tarea: `python -m unittest tests/test_versioning.py` -> OK (3+ tests).
- Mutación: quitar la mención de `CHANGELOG.md` del bloque ES del README -> el test
  falla nombrando el README y la mitad ES.

## Do / Don't
- DO: regex simple para semver; particionar el README por el ancla `<a id="español">`
  para distinguir EN de ES.
- DO: historia retroactiva del CHANGELOG destilada de `docs/reports/` (rastreable).
- DON'T: red, subprocess, editar specs/reportes históricos, crear tags (los crea el PM).

## Tests
(Los tests están en `tests/test_versioning.py` — el target de este contrato. El dev
reemplaza el stub sellado y re-sella `tests_sha256` aquí al terminar.)

## Constraints
- PARAR y reportar si... la coherencia exigiera editar `tests/test_init_project.py`,
  `scripts/init_project.py` o estructura del index más allá del enlace nuevo.
