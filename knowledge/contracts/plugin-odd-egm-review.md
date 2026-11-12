---
type: 'Task Contract'
title: 'Revision ODD y EGM desde el complemento KDD'
description: 'Inspeccionar cambios y verificar revisiones independientes con el validador fijado por el consumidor.'
tags: ['plugin', 'odd', 'egm', 'adoption', 'integration']
task: plugin-odd-egm-review
intent: 'Ofrecer una entrada local para elegir el flujo editorial o preparar una revision proporcional.'
target: tools/kdd-adoption/validate.py
signature: 'def review_main(argv):'
test_command: 'python -m unittest tests/test_plugin_odd_egm_review.py'
test_runner: python-unittest
budget:
  cyclomatic_max: 10
  nesting_max: 3
tests: tests/test_plugin_odd_egm_review.py
tests_sha256: '36bab1b273da169b6b93e8fb655af3012bc68d51918ce2f0b13bc95c378e174b'
oracle_files: ['tests/test_plugin_odd_egm_review.py', 'tests/adoption_remediation_support.py', 'tests/test_adopt_project.py', 'tests/__init__.py', 'tools/context-v03/requirements.txt']
touch_only: ['tools/kdd-adoption/validate.py', 'tools/kdd-adoption/README.md', 'plugins/kdd-codex/README.md', 'plugins/kdd-codex/skills/kdd-workflow/SKILL.md', 'knowledge/piloto-kdd-complemento.md']
deps_allowed: ['stdlib', 'git']
forbids: ['llm']
---

## Intent

Exponer el [flujo editorial](../odd-lightweight.md) y la [revision
proporcional](../baseline-risk-review.md) al instalar KDD en un proyecto
existente. Usar el mismo lanzador desde Codex y la terminal.

## Interface

```sh
python -I .kdd/validate.py review --approved-ref ADOPCION --base-ref BASE --candidate-ref CANDIDATO
```

`--approved-ref` es obligatorio y explicito en este modo. Identifica la
adopcion vigente y su pin, con las comprobaciones existentes de Git, indice
y checkout. `--repo-root` permite indicar el proyecto; por defecto se usa
la raiz del lanzador. BASE y CANDIDATO son OID nativos completos. Se puede
inspeccionar otro ref desde el checkout de confianza. Para el flujo ODD se
agrega `--small-change`, con `--editorial-only` despues de leer el diff y la
politica aplicable. Para EGM se agrega `--review ARCHIVO.json`, incompatible
con `--small-change`. Una ruta relativa del registro se resuelve desde el
directorio de invocacion.

Ejecutar `scripts/baseline_review.py` desde el arbol verificado del pin, en
un temporal externo y con el entorno Git y Python saneado del lanzador.
Conservar el JSON del revisor y agregar `verified_kdd_sha`. Los codigos son
0 para inspeccion o registro listo, 1 para registro valido pendiente y 2
para errores sin veredicto JSON. Un pin sin el revisor produce un error
que indica actualizar al pin compatible. `review` no usa el modo normal de
ejecucion de oraculos o calidad.

## Invariants

- El flujo ligero requiere un commit editorial elegible y confirmacion
  explicita. Los cambios de garantias siguen contratos, oraculos y baseline.
- Reusar los pisos, lentes y registros exactos del revisor fijado. Un
  revisor no disponible queda pendiente. La aprobacion humana de calidad
  y el registro del SHA siguen el [protocolo](../quality-approval.md).
- Inspeccionar objetos Git sin sustituciones, ejecutar solo el revisor del
  pin y conservar refs, indice, configuracion y working tree del consumidor.
- El complemento sigue siendo una skill. Se conservan los tres archivos
  administrados, los comandos historicos, Ubuntu y Windows y las dos pasadas.
  La revision usa el Git local y la descarga existente del pin oficial.

## Examples

- Una errata en README en un commit permite `lightweight` con confirmacion.
- Un contrato o una prueba cambiada devuelve `standard` aun con confirmacion.
- Un registro con lector `not_run` devuelve 1 y `review_ready: false`.

## Do / Don't

- DO comprobar objetivo, diff y politica del proyecto antes de confirmar.
- DO entregar a los revisores el candidato y las fuentes exactas.
- DON'T registrar una aprobacion a partir de `review_ready`.

## Tests

Instalar en un Git Python existente, comparar el pin de la terminal, probar
la clasificacion de un cambio real, verificar un registro y probar ausencia
de revisor, identidad ajena, sustitucion local del pin y un pin sin el
revisor. Comparar el estado Git y del checkout alrededor de la revision.

## Constraints

PARAR y reportar si se necesita una dependencia, servidor, hook, cambio de
workflow o permiso adicional. El piloto no publica una release.
