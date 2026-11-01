---
type: 'Task Contract'
title: 'Entorno aislado de discovery de Pages para PR'
description: 'Ejecutar discovery en un venv nuevo con los instaladores Python del despliegue.'
tags: ['ci', 'pages', 'integration']
task: pages-pr-deploy-environment
intent: 'Reproducir dependencias Python del despliegue durante la validacion del PR.'
target: scripts/pages_pr_discovery.py
signature: 'python scripts/pages_pr_discovery.py --repo-root DIR --venv-dir DIR'
test_command: 'python -m unittest tests.test_pages_pr_deploy_parity'
budget:
  cyclomatic_max: 20
  nesting_max: 4
tests: 'tests/test_pages_pr_deploy_parity.py'
tests_sha256: '0004a7f5e91f8d06f9d9714ab0a81a2a4482d3945ebd1acc3bf9018e0de725a9'
touch_only: ['scripts/pages_pr_discovery.py']
deps_allowed: ['stdlib', 'PyYAML', 'pip', 'Git']
forbids: ['llm']
---

## Intent
Aplicar el [protocolo de paridad de discovery](../pages-pr-deploy-parity.md).

## Interface
CLI con `--repo-root` y `--venv-dir`. Devuelve en stdout JSON con `ok`, `tests`
e `ids` cuando el discovery estricto termina con exito. Cualquier fallo usa
salida no cero y diagnostico en stderr. La ruta del venv debe ser nueva y
estar fuera del checkout; no se reutiliza ni elimina una ruta existente.

## Invariants
Leer los instaladores Python reales del despliegue en orden y ejecutarlos en
un venv nuevo, sin shell ni paquetes heredados. Rechazar pasos condicionales,
fallos y sintaxis que no se pueda reproducir. Ejecutar discovery real estricto,
sin ejecutar casos; no aceptar IDs ausentes, duplicados o imports fallidos.
No modificar workflow de despliegue, runtime confiable ni protecciones.

## Examples
- Dependencia presente solo en el interprete padre: discovery aislado falla.
- Instalador del despliegue instala wheel local: discovery aislado pasa.
- Instalador fallido o condicional no soportado: error antes de PASS.

## Do / Don't
- DO: probar procesos y pip reales sin red con un wheel sintetico.
- DON'T: reutilizar el venv del job ni ejecutar una suite para contar IDs.

## Tests
`tests/test_pages_pr_deploy_parity.py` prueba venv, pip y discovery reales,
incluyendo paquete faltante, wheel local, fallos y rutas existentes.

## Constraints
Baseline humano antes de implementar. PARAR y reportar si se requiere cambiar
un oraculo anterior, runtime aprobado o proteccion remota.