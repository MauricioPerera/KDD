---
type: 'Concept'
title: 'Validación de contratos (niveles 1 y 2)'
description: 'Valida contratos y oráculos, mide presupuestos y conserva evidencia de ejecución.'
tags: ['ccdd', 'validacion', 'gate', 'reference']
---

# Validación de contratos — nodo canónico

La [especificación OKF](OKF-SPEC.md) define los nodos y su enlazado. Aquí se indica qué verifica cada ruta y dónde consultar la evidencia.

## Nivel 1 — Incluido y obligatorio (local + CI)

El [catálogo de 19 gates](../docs/reports/ARCHIVO-VALIDACION.md#catalogo-de-gates-y-controles-locales) detalla los comandos. `validate_contracts.py` valida el esquema, `touch_only` y el sello `tests_sha256`. `validate_test_commands.py` ejecuta cada contrato con su plazo individual. La validación de [behavior](behavior-contract-spec.md) comprueba el esquema y ofrece ejecución optativa.

Los perfiles `standard` y `strict` validan contratos y oráculos contra un `--approved-ref` completo antes de ejecutar la suite y los comandos. El CI nativo selecciona un baseline por árbol desde `KDD_APPROVAL_REGISTRY`. El workflow reutilizable admite `approval_registry` o las entradas explícitas `approved_baseline_ref` y `quality_approved_ref`. Una aprobación ausente bloquea. El gate independiente `trusted-pr-gate` lee el merge desde código de la base. El [registro externo](approval-registry.md) explica los modos y la [ejecución confiable](ci-audit-remediation.md) describe el runtime aislado y su revisión.

CI ejecuta Ubuntu y Windows con dos pasadas de la suite y cobertura en la primera. La repetición aporta evidencia de repetibilidad. El [post-init de Windows](postinit-windows-runtime.md) se verifica con su ventana común de 600 s y se omite en las pasadas generales con `KDD_SKIP_INIT_POST_APPLY_SUITE=1`. [Pages](pages-ci-inventory.md) coteja el inventario del CI con discovery para el mismo SHA. Un `SKIP` indica evidencia ausente.

El CI nativo fija el auditor diferencial de Python por SHA y registra los hashes de sus módulos. El recibo enumera rutas y exclusiones. En las funciones medidas incluye valores AST, topes efectivos y `within_budget` calculado por el programa. `regression_status: PASS` admite deuda histórica estable o reducida. Un presupuesto obligatorio exige medida efectiva y pertenencia al rango según [controles requeridos](required-controls.md). Consulta el [recibo](contracts/changed-budget-receipt.md), el [origen del auditor](contracts/changed-budget-ci-source.md) y el [detalle de perímetro, dependencias y presupuestos](../docs/reports/ARCHIVO-VALIDACION.md#auditoria-del-cambio-y-controles-de-codigo).

## Preflight — diagnóstico local opt-in (NO es un gate)

[Guía y uso](contracts/preflight.md). Sus 20 comprobaciones incluyen la atestación local.

## Recetas de arreglo por rule-id (`scripts/rule_hints.py`)

[Guía y uso](../docs/reports/ARCHIVO-VALIDACION.md#recetas-de-arreglo-por-rule-id-scriptsrule_hintspy).

## Auditor de seals débiles — diagnóstico opt-in (NO es un gate)

[Guía y uso](contracts/seal-audit.md).

## Auditor de `forbids` — diagnóstico opt-in (NO es un gate)

[Guía y uso](contracts/forbids-audit.md).

## Prueba local de regresión

[Uso y evidencia de la comparación con un oráculo sellado](../docs/reports/PRUEBA-LOCAL-REGRESION.md).

## Nivel 2 — Opcional (si el entorno del agente lo tiene)

CCDD ofrece [integración nativa para funciones Python](native-level2.md) y el MCP `ccdd-complexity` con `lint_task_contract` y `run_integration_gate`. Si la política exige Nivel 2, su ausencia o fallo bloquea la verificación.

### Gate multi-lenguaje

CCDD mide las gramáticas que tiene instaladas. Su parser genérico de firma avisa con `tc-signature-generic` cuando solo puede comprobar aridad. Ejecuta el `test_command` declarado desde el directorio del target. Usa `scan_dependencies` para imports Python. Los macros y DSL opacos quedan fuera de las métricas. En el ejemplo Rust, cuatro `if` anidados dan ciclomática 5 y profundidad 4. Dentro de `view!` el anfitrión mide 1 y 0. El [benchmark](https://github.com/MauricioPerera/ccdd-gate/blob/main/BENCHMARKS.md#4-costo-de-rust-vs-python-en-el-gate-reproducible) mide por separado parser, compilación y lint. KDD dispone también del [auditor de cambios optativo](contracts/change-contract-audit.md) para presupuestos y dependencias de Python, JS/TS, Go y Rust.

### Export para el gate

`scripts/export_gate_contract.py` prepara el contrato ASCII para MCP y reescribe las rutas de target y tests relativas al export. Por defecto guarda `<task>.gate.md` en la raíz. El [adaptador nativo](native-level2.md) usa su propio export temporal y ejecuta desde la raíz del proyecto.

## Precedencia del budget

La validación estructural comprueba las claves y los valores. Los medidores aplican topes aprobados según su perfil. Con una política CCDD firmada, sus topes prevalecen. El perfil nativo identifica su política por commit y topes explícitos.

## Ciclo de vida del contrato

1. **draft** tras redactar el contrato.
2. **validated** tras validar estructura y sello, y lint del gate si aplica.
3. **implemented** tras pasar `test_command`.
4. **verified** tras conservar salidas reales en `.agents/logs/<task>-REPORT.md`. El [control de atestación](contracts/attestation-gate.md) valida la identidad y los hashes de esos reportes locales cuando incluyen un envelope.

## Aprobacion de calidad del proyecto

La [política de calidad](quality-approval.md) define los oráculos funcionales, adversariales y de interfaz, el perímetro y la referencia aprobada. Se integra con los gates aplicables del proyecto.

## Diagnostico reproducible de comandos

`python scripts/validation_runtime.py contracts --timings-json tiempos.json` guarda duración, alcance y estado por contrato. El [diagnóstico](contracts/validation-diagnostics.md) explica Git nativo en Windows y la relación entre los plazos individuales y el global de preflight.

## Aceptacion y muestras ejecutables

[Acceptance](acceptance.md) exige SHA, inventario, matriz por obligación, `oracle_files` y `test_runner` instrumentado. `python scripts/validate_documentation_examples.py` comprueba los ejemplos del [quickstart](quickstart.md) y también corre en CI.

El plazo de contrato por defecto es 180 s. `test_timeout` declara de 1 a 3600 s. `--timeout` fija el valor para los contratos sin plazo propio. El [contrato de init-project](contracts/init-project.md) declara 600 s. Preflight por contrato conserva su valor histórico de 120 s salvo plazo declarado.
