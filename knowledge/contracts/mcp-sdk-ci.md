---
type: 'Task Contract'
title: 'Verificacion estricta del SDK MCP real en CI'
description: 'Exigir SDK fijado, ocho IDs completos y cero SKIP en el perfil MCP configurado.'
tags: ['mcp', 'ci', 'integration']
task: mcp-sdk-ci
intent: 'Ejecutar los oraculos de protocolo existentes con SDK genuino y evidencia nueva.'
target: scripts/check_mcp_sdk.py
language: python
signature: 'def run_smoke(repo_root, *, report_path=None, expected_commit=None):'
test_command: 'python -m unittest tests/test_mcp_sdk_ci.py'
budget:
  cyclomatic_max: 16
  nesting_max: 4
tests: tests/test_mcp_sdk_ci.py
tests_sha256: '8e77f0379bf8faaed00f7d494a62487b2c57ce3b301c92dedcbefa0748e16b34'
touch_only: ['scripts/check_mcp_sdk.py', '.github/workflows/validate.yml', 'scripts/guard_pr_baseline.py']
deps_allowed: ['stdlib', 'mcp']
forbids: ['network', 'llm']
---

## Intent
Aplicar el [perfil SDK](../mcp-sdk-ci.md) con las garantias y limites del
[servidor](../mcp-server.md), conservando la aprobacion humana.

## Interface
run_smoke devuelve el reporte completo. validate_report(data, expected_ids,
expected_version) devuelve None en exito y rechaza omisiones, duplicados, skips
y SDK incorrecto mediante McpSdkError(ValueError). El CLI admite --repo-root, --report-json y
--expected-commit; solo exit 0 acredita los ocho casos. No sobrescribir reportes.
KDD_MCP_SDK_PYTHON identifica el venv preparado; el input reusable verify_mcp_sdk
es false por defecto y KDD nativo lo exige en ambos jobs validate.

## Invariants
Conservar los ocho metodos y todas sus aserciones. El manifiesto fija version,
hash del wheel, locks, oraculo y ocho IDs. Validarlo antes de ejecutar. Importar
SDK genuino externo antes de rutas del candidato; SDK ausente/incompatible no
es un SKIP satisfactorio. Reportar contexto Git real o None si no hay Git; el
commit exigido en CI debe coincidir. Mantener los 19 gates y las dos suites.
Proteger checker, manifiesto y locks en el guard confiable.

## Examples
- SDK 1.30.0 real: ocho casos de protocolo, cero fallos y cero SKIP.
- Sin SDK o con ocho casos omitidos: FAIL aunque unittest haya devuelto exit 0.
- Perfil sin SDK en un producto: no acredita MCP ni reemplaza quality/product.json.

## Do / Don't
- DO: conservar version, origen, IDs, resultados y hash del oraculo en evidencia nueva.
- DON'T: instalar latest, aceptar cero casos, ejecutar un SDK del proyecto o declarar stdio probado.

## Tests
El oraculo verifica locks y bytes congelados; usa procesos reales para probar
perfil sin SDK, errores del verificador, validacion estricta y el cuerpo del
workflow. Con KDD_MCP_SDK_PYTHON verifica los ocho casos genuinos; en CI nativo
esa configuracion es obligatoria. El perfil sin SDK declara esa aplicabilidad.

## Constraints
PARAR y reportar si se requiere actualizar oraculos, runtime o protecciones.
Los paquetes se preparan fuera de este verificador; no hay descargas en run_smoke.
