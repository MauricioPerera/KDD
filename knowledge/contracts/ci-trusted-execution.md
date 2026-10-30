---
type: 'Task Contract'
title: 'Arranque de CI desde runtime confiable aislado'
description: 'Rechazar imports suplantados y verdes sin evidencia al ejecutar comandos y dos suites.'
tags: ['ci', 'security', 'integration']
task: ci-trusted-execution
intent: 'Cerrar el P1 sin ejecutar el candidato en el guard ni confiar en su stdout.'
target: scripts/trusted_ci.py
language: python
signature: 'def prepare_bundle(repo_root, trusted_ref, bundle_dir) -> dict:'
test_command: 'python -m unittest tests/test_ci_trusted_execution.py'
budget:
  cyclomatic_max: 18
  nesting_max: 4
tests: tests/test_ci_trusted_execution.py
tests_sha256: 'ab92d87f830893997223cca9f5f53cc4b9ec3aa3ef583a2aff9a81ff18f74a79'
touch_only: ['scripts/trusted_ci.py', 'scripts/guard_pr_baseline.py', 'scripts/run_test_suite.py', 'scripts/validate_test_commands.py', '.github/workflows/validate.yml']
deps_allowed: ['stdlib']
forbids: ['network', 'llm']
---

## Intent
Aplicar la [frontera confiable](../ci-audit-remediation.md), complementando
[trusted-pr-gate](trusted-pr-gate.md) y [suite](ci-suite-processes.md).

## Interface
- CLI: python -I trusted_ci.py prepare --repo-root DIR --trusted-ref SHA
  --bundle-dir DIR; referencia hexadecimal completa, commit existente, bundle
  externo al checkout, creacion exclusiva. Extrae solo los seis archivos exactos
  enumerados en la arquitectura; devuelve manifiesto de paths y hashes desde Git.
- CLI desde el bundle: suite --repo-root DIR --start-directory tests
  --pattern test_*.py --workers N --report-json PATH; y commands --repo-root DIR
  --contracts-dir knowledge/contracts --timeout S --deduplicate --workers N
  --report-json PATH. Alternativa --report-dir DIR crea un nombre unico y
  exclusivo por invocacion, para usar comandos identicos en ambas pasadas.
  Reporte nuevo obligatorio, falla si el path explicito ya existe.
- El launcher devuelve 0 solo con proceso exitoso y reporte estructurado nuevo,
  inventario no vacio y contabilidad completa. commands incluye results no vacios,
  un resultado por contrato y sus veredictos. stdout no sustituye al reporte.
- commands redirige invocaciones Python reconocidas de scripts/run_test_suite.py
  al runner del bundle, con aislamiento; no vuelve a arrancar el control del
  candidato. Los comandos arbitrarios conservan su semantica de exit code,
  sin prometer que un comando aprobado pero vacuo pruebe comportamiento.
- La CLI local del runner tambien evita imports suplantados en su arranque;
  los hijos de control conservan aislamiento y cargan helpers del bundle exacto.

## Invariants
Cumplir el [protocolo](../ci-audit-remediation.md). El guard confiable rechaza
modificaciones a los seis archivos y altas/cambios de modulos o paquetes que
suplanten nombres stdlib/bundle en raiz o scripts. No ejecuta el candidato.
SHA invalido, archivo faltante, bundle interno/symlink hacia checkout o reporte
ausente/corrupto/reutilizado fallan. No se hereda PYTHONPATH/user site al control.
Cada pasada usa reporte y ejecucion independientes, mismo comando y parametros.

## Examples
- scripts/argparse.py nuevo intenta exit0: guard lo rechaza; bundle ejecuta
  el oraculo real, cuyo defecto sigue siendo FAIL.
- Candidato modifica run_test_suite.py despues de materializar el bundle:
  ese cambio no sustituye al runner externo y el guard lo rechaza.
- Oracle con os._exit(0): falta evidencia y el launcher falla.

## Do / Don't
- DO: probar Git e interpretes reales con paths Unicode/espacios y controles sanos.
- DON'T: extraer el bundle desde HEAD candidato automaticamente en un PR.

## Tests
tests/test_ci_trusted_execution.py prueba bundle real desde Git, rechazo del
guard sin efectos, sombras, PYTHONPATH/sitecustomize, fallos verdaderos, evidencia
faltante y dos invocaciones independientes. Las adaptaciones de workflow quedan
en los oraculos existentes, conservando todas sus comprobaciones de cobertura.

## Constraints
PARAR y reportar si se necesita aprobar un runtime, cambiar una proteccion remota
o publicar para verificar CI. Solo stdlib/Git; permisos/pins/jobs sin cambios.
No se afirma sandbox ni Nivel2. Baseline humano obligatorio antes de implementar.
