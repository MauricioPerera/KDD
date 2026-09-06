---
type: 'Task Contract'
title: 'Aprobacion integrada de calidad'
description: 'Detectar cambios de contrato y test respecto de un commit aprobado.'
tags: ['ccdd', 'security']
task: verify-quality
intent: 'Comparar contrato y oraculo contra una referencia independiente.'
target: scripts/verify_quality.py
language: python
signature: 'def main():'
test_command: 'python -m unittest tests/test_verify_quality.py'
budget:
  cyclomatic_max: 12
  nesting_max: 4
tests: 'tests/test_verify_quality.py'
tests_sha256: '7a45563015e79e991cfa8ebbeb4edbb10bf1015d5e2b3d5b28dbd2e7288140fd'
touch_only: ['scripts/verify_quality.py']
deps_allowed: ['stdlib', 'vendored-codex-security']
forbids: ['llm']
---

## Intent
Aplicar la [validacion](../validacion.md) a la evidencia local del tablero.

## Interface
`validate_baseline(contract, approved_ref, repo_root)` devuelve diferencias o falla si la referencia es invalida.

## Invariants
- Re-sellar contrato y test no evade una referencia aprobada distinta.
- No modificar el repositorio ni la referencia.
- Normalizar LF igual que el validador de contratos.

## Examples
- Mismos archivos aprobados -> cero diferencias.
- Test y hash modificados -> dos diferencias.

## Do / Don't
- DO: resolver git mediante argumentos, sin shell.
- DON'T: elegir automaticamente HEAD como referencia aprobada.

## Tests
Oraculo sellado antes de implementar.

## Constraints
- PARAR y reportar si no existe el commit aprobado.

## Politica de aprobacion integrada
CLI: python scripts/verify_quality.py --repo-root DIR --policy quality.json --approved-ref SHA. Los tres argumentos son explicitos; repo-root puede tener default '.', los otros dos son obligatorios. No elegir HEAD automaticamente.
Politica JSON del commit aprobado: protected (lista no vacia de oraculos), implementation y pm (listas de rutas exactas relativas), required_kinds (lista no vacia incluye functional y adversarial; ui cuando aplique), checks (lista no vacia de {name, kind, argv: lista strings no vacia, timeout: entero positivo <=3600}). Rechazar esquema malformado, nombres duplicados, tipos falsos y categorias requeridas sin comprobacion.
Leer politica del objeto Git aprobado y comparar tambien la copia de trabajo; comparar cada protected con Git, LF normalizado. Rechazar rutas absolutas, '..', backslash, NUL y symlinks fuera del repo; listas de permisos sin glob. Protected nunca puede ser modificable aunque tambien figure en permisos.
Perimetro real: diff contra approved-ref incluye staged, unstaged, committed y archivos sin seguimiento no ignorados. Solo implementation y pm pueden diferir. Comprobar integridad/perimetro antes y despues de ejecutar checks, para detectar efectos del propio comando. No confiar en reportes previos.
Ejecutar checks con argv sin shell, cwd=repo-root, timeout por check, dos vueltas. Propagar fallo, timeout o comando ausente como rechazo; no imprimir PASS global hasta terminar. Functional/adversarial/ui son declaraciones revisadas, no prueba automatica de que el comando sea un oraculo fuerte. El ejecutor y eleccion del commit son base de confianza.
El script debe ser ASCII y stdlib. Tu perimetro unico es scripts/verify_quality.py. Tests y este contrato son del PM y no se modifican.
