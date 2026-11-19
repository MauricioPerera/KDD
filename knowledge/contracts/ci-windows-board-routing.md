---
type: 'Task Contract'
title: 'Repartir los contratos y las suites sobre dos runners Windows existentes'
description: 'Separar el gate y las dos pasadas nativas conservando Board, post-init, cobertura y el check requerido.'
tags: ['ci', 'performance', 'windows', 'integration']
task: ci-windows-board-routing
intent: 'Acortar la ruta critica Windows conservando el trabajo y comprobando la evidencia de ambos productores.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate, board, require_windows'
test_command: 'python -m unittest tests.test_ci_windows_board_routing'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_ci_windows_board_routing.py
tests_sha256: 'e2f555798f39c6529ba18028188b1e3a8fdad166eff3d897be03a20794c0106e'
oracle_files: ['tests/test_ci_windows_board_routing.py', 'tests/__init__.py']
budget:
  cyclomatic_max: 12
  nesting_max: 4
touch_only: ['.github/workflows/validate.yml']
deps_allowed: ['stdlib', 'git', 'PyYAML']
forbids: ['llm']
---

## Intent

Aplicar el [contrato de recibos](ci-windows-board-receipts.md) y mantener
el [plazo comun de post-init](postinit-windows-common-deadline.md) con
un reparto nativo que reutiliza el runner Windows de Board.

## Interface

Conservar ambos vectores os con ubuntu-latest y windows-latest.
Solo en el evento nativo del validate.yml de MauricioPerera/KDD
(push en main o pull_request, sin modo reusable), excluir la fila
Windows anterior de validate y board. En validate agregar las filas
Windows win_contracts y win_suite mediante include. La condicion es
la misma que habilita las particiones post-init independientes.

win_contracts ejecuta los comandos de los contratos y el oraculo
Board, con el nombre requerido board (windows-latest). En pasos
Run Windows Board typecheck y Run Windows Board tests mantener
npm run typecheck y npm test bajo tools/kdd-board. win_suite
usa el nombre Windows validation work y realiza las dos pasadas
y el resto de sus controles tal como el perfil anterior.

Los productores mantienen los mismos comandos y workers. Los pasos
de suites, cobertura y Pages excluyen solo win_contracts. El gate
de comandos y su reporte init excluyen solo win_suite. La
comprobacion de post-init permanece al terminar las suites y
excluye solo win_contracts. El workflow publicado conserva los
controles de proteccion, pins, permisos y el perfil Ubuntu.

El paso Upload Windows validation receipt tiene id windows-receipt,
sube un recibo por rol con error ante ausencia y overwrite false.
Los outputs win_contract_id, win_contract_digest, win_suite_id y
win_suite_digest salen de ese paso solo para el rol correspondiente.
El job require_windows usa needs de validate, condicion always()
y el alcance nativo. En este alcance se llama validate (windows-latest).
En otros casos su nombre inactivo no coincide con un check requerido.
Su primer guard Check Windows validation producers exige success,
IDs distintos y ambos digests antes de verificar los recibos.
El paso Download Windows validation artifacts usa el pin existente
de download-artifact, ambos IDs de needs, skip-decompress y
digest-mismatch error. Verify Windows validation receipts coteja
el digest revisado de su driver antes de ejecutarlo de forma externa
al checkout con python -I. Se ejecuta antes de publicar tiempos unidos.

Los diagnosticos parciales conservan el formato del exportador
existente y un nombre por rol. El job final publica los diagnosticos
Windows completos con el nombre historico del intento. Ubuntu
mantiene su nombre normal y las evidencias de Pages conservan sus
inventarios originales y nombres por plataforma.

## Invariants

- No aumentar el numero de runners Windows. Se admite un job Ubuntu
  corto para unir evidencia. Medir su cola y trabajo como parte del
  tiempo necesario para obtener el check Windows requerido.
- Cada rol prueba el mismo SHA y runtime. No responsabilizar al
  reporte de diagnostico de la aprobacion funcional.
- Mantener ambos SO, ambas pasadas consecutivas, cobertura solo
  en la primera, cuatro workers de contratos y seis de suite Windows,
  init-project exclusivo y evidencia del plazo comun de post-init.
- Los dos roles Windows no publican el mismo nombre de artefacto.
  Ningun fallo de productor ni un recibo obsoleto se vuelve verde.
- Reutilizables y ejecuciones ajenas conservan su flujo y sus
  nombres sin activar la union ni mover Board Windows.

## Examples

- En modo nativo hay dos productores Windows y dos Ubuntu, ademas
  de las dos particiones post-init y la union Ubuntu.
- Un consumidor reutilizable sigue ejecutando validate y Board en
  ambos SO con su propia politica.
- Una union con producer result skipped falla aunque haya outputs
  conservados de un intento anterior.

## Do / Don't

- DO preservar el mismo vetado de archivos, el guard de PR y los
  contratos congelados con un baseline humano del cambio.
- DON'T medir solo el job que conserva los tests cuando se mueve
  parte del trabajo a otro runner. Medir hasta la aprobacion real.

## Tests

Comprobar la matriz y los guards del workflow real con PyYAML.
Ejecutar el guard de procedencia en Bash real. Las pruebas existentes
de post-init, cobertura, exclusividad y diagnosticos conservan sus
controles y admiten solo el nuevo reparto explicitamente contratado.

## Constraints

PARAR y reportar si se necesita publicar, modificar una proteccion
o aprobar un runtime. El baseline de oraculos y la revision del
arbol protegido se aprueban por separado. Aceptar el cambio solo
tras tres muestras comparables del mismo SHA y ahorro reproducible
frente al tiempo previo del check Windows completo.
