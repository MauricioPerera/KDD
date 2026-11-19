---
type: 'Task Contract'
title: 'Repartir los contratos y las suites sobre dos runners Windows existentes'
description: 'Separar el gate y las dos pasadas nativas conservando Board, post-init, cobertura y el check requerido.'
tags: ['ci', 'performance', 'windows', 'integration']
task: ci-windows-board-routing
intent: 'Acortar la ruta critica Windows conservando el trabajo y comprobando la evidencia de ambos productores.'
target: .github/workflows/validate.yml
language: yaml
signature: 'validate, board, validate_windows, require_windows'
test_command: 'python -m unittest tests.test_ci_windows_board_routing'
test_runner: python-unittest
test_scope: infrastructure
tests: tests/test_ci_windows_board_routing.py
tests_sha256: 'bee8ef8b5057a847f702028d47328db7543f421dfe3dc6e2528a9b8812eb09d2'
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
Windows anterior de validate y board. Validate mantiene el rol full
y el nombre explicito validate (matrix.os), que excluye la dimension
role del nombre del check. Asi conserva los contextos originales.
Un job validate_windows se habilita solo para esos eventos y contiene
exactamente las filas Windows win_contracts y win_suite. Las dos
matrices de validate usan fail-fast false. Validate_windows reutiliza
los pasos y el entorno de validate mediante aliases YAML. La condicion
es la misma que habilita las particiones post-init independientes.

win_contracts ejecuta los comandos de los contratos y el oraculo
Board, con el nombre requerido board (windows-latest). En pasos
Run Windows Board typecheck y Run Windows Board tests mantener
npm run typecheck y npm test bajo tools/kdd-board. win_suite
usa el nombre Windows validation work y realiza las dos pasadas
y el resto de sus controles tal como el perfil anterior.

Los productores mantienen los mismos comandos y workers. Los pasos
de suites, cobertura, Pages y aceptacion excluyen solo win_contracts.
El gate de comandos y su reporte init excluyen solo win_suite.
La comprobacion de post-init permanece al terminar las suites y excluye
solo win_contracts. El workflow conserva los controles de proteccion,
pins, permisos y el perfil Ubuntu. Full conserva los nombres previos
de artefactos y el check de Windows del flujo reutilizable.

El paso Upload Windows validation receipt tiene id windows-receipt,
sube un recibo por rol con error ante ausencia y overwrite false.
Los outputs win_contract_id, win_contract_digest, win_suite_id y
win_suite_digest salen de ese paso solo para el rol correspondiente.
Win_suite emite win_suite_inventory_sha256 desde discovery y
win_coverage_id y win_coverage_digest desde el upload de cobertura.
El job require_windows usa needs de validate_windows y condicion
always() con el alcance nativo. No depende del resultado de Ubuntu.
En este alcance se llama validate (windows-latest).
En otros casos su nombre inactivo no coincide con un check requerido.
Su primer guard Check Windows validation producers exige success,
IDs distintos y tres digests de artefactos antes de verificar los
recibos. Solo win_suite publica acceptance-windows-latest en el
flujo nativo, incluida la evidencia de una aceptacion fallida.
El paso Download Windows validation artifacts usa el pin existente
de download-artifact, los tres IDs de needs, skip-decompress true,
merge-multiple true y digest-mismatch error. Con estos dos flags los
tres ZIP mantienen sus bytes y nombres en un solo directorio.
Verify Windows validation receipts extrae
el blob del commit candidato exacto, sin reemplazos Git, a un
directorio temporal nuevo fuera del checkout. Compara el SHA-256
con el pin literal de la revision protegida y solo despues invoca
python -I sobre ese archivo. Los datos de contexto y needs entran
en el entorno, como datos y no como codigo Bash. El paso se ejecuta
antes de publicar los tiempos unidos. Guard, checkout, descarga y
verificacion carecen de continue-on-error y omisiones condicionales.

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
  La medicion acepta estrictamente menos de 600 s en cada muestra.
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
Ejecutar en Bash real el guard de procedencia y el discovery con dos
inventarios distintos. El wrapper usa Git real y un blob de prueba que
lee la identidad, los productores y las tres rutas descargadas.
Las pruebas existentes
de post-init, cobertura, exclusividad y diagnosticos conservan sus
controles y admiten solo el nuevo reparto explicitamente contratado.

## Constraints

PARAR y reportar si se necesita publicar, modificar una proteccion
o aprobar un runtime. El baseline de oraculos y la revision del
arbol protegido se aprueban por separado. Aceptar el cambio solo
tras tres muestras comparables del mismo SHA y ahorro reproducible
frente al tiempo previo del check Windows completo.
