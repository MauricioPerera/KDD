---
type: 'Task Contract'
title: 'Lecturas agrupadas del baseline aprobado'
description: 'Comparar contratos y oraculos aprobados en lotes sin perder integridad ni aprobacion explicita.'
tags: ['git', 'baseline', 'security', 'performance']
task: baseline-git-batch
intent: 'Reducir procesos Git al verificar muchos contratos sin debilitar las comprobaciones.'
target: scripts/validate_baseline.py
signature: 'def validate_all_baselines(approved_ref, repo_root=".", contracts_dir="knowledge/contracts"):'
test_command: 'python -m unittest tests.test_baseline_git_batch'
budget:
  cyclomatic_max: 12
  nesting_max: 4
  lines_max: 100
  params_max: 5
tests: tests/test_baseline_git_batch.py
tests_sha256: 'bb46510cd144e9df0906d51d755643803b5fea3375e84117a196aa92ceef8653'
touch_only: ['scripts/validate_baseline.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['network', 'llm']
---

## Intent
Reducir el coste repetido de [referencia aprobada](validate-baseline.md) sin
alterar su autoridad, la seleccion explicita ni el caracter de solo lectura.

## Interface
Conservar firmas y CLI de verificacion individual y `--all`, codigos de salida,
resultados deterministas y normalizacion de finales de linea.

## Invariants
- Resolver la referencia una vez y leer contratos y oraculos exclusivamente del
  commit resuelto. No confiar en el contenido actual para elegir un oraculo.
- Detectar altas, bajas, cambios de contenido, oraculos compartidos, rutas que
  escapan y blobs ausentes. Un lote incompleto, corrupto o ambiguo falla cerrado.
- Preservar rutas admitidas y el comportamiento seguro de nombres que no pueden
  representarse en el protocolo de lotes; nunca interpretar nombres como comandos.
- Rechazar entradas invalidas sin devolver exito parcial; no modificar arbol,
  indice, referencias, configuracion Git ni ejecutar producto del candidato.
- Para doce contratos y sus oraculos, `--all` inicia como maximo seis procesos
  Git reales, contabilizados por un hook de auditoria en el proceso verificador.
- Conservar las pruebas anteriores y la matriz, limites y dos pasadas de CI.
  Medir por separado; el ahorro de procesos no prueba que post-init termine.

## Examples
- Doce contratos validos y oraculos sin cambios -> exito e inventario completo.
- Contrato, oraculo o objeto aprobado ausente -> fallo, nunca exito parcial.

## Do / Don't
- DO comprobar Git real, exit codes, datos binarios y estados antes/despues.
- DON'T sustituir la referencia explicita por HEAD ni confiar en un sello nuevo.

## Tests
`tests/test_baseline_git_batch.py` crea repositorios Git reales y controla numero
 de procesos, cambios, ausencias, fallos, normalizacion y CLI.

## Constraints
PARAR y reportar si requiere modificar un oraculo anterior, runtime o proteccion.
