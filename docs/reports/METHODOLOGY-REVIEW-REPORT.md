# Revisión y pruebas antes de actualizar KDD

Revisión local de los cambios completada. Se corrigieron defectos reproducidos durante la revisión y la corrida final mantuvo el código estable. Este es el resultado histórico anterior a la publicación y a la integración con el main de octubre de 2026. Sus conteos no acreditan el árbol integrado. Los logs locales se conservan fuera del repositorio; el JSON consolidado incluye comandos, resultados y hashes.

## Hallazgos corregidos

| Hallazgo | Resultado y regresión |
|---|---|
| La normalización de saltos de línea permitía modificar fixtures binarios protegidos. | Baseline, guard de PR y aceptación comparan bytes exactos para archivos `-text` en los atributos del SHA aprobado y para contenido con NUL. El candidato no puede reclasificarlos alterando sus atributos. Cuatro regresiones suplementarias cubren los tres puntos de entrada y NUL; los casos vulnerables fallaron antes de la corrección. |
| El Board aceptaba un resumen unittest fabricado seguido de `os._exit(0)` como prueba verificada. | La ejecución Python usa el recorder instrumentado mediante un bridge confiable. El oráculo primario congelado comprueba resumen falso, ejecución real, cero casos y omisiones. Se comprobó además redacción de secretos y timeout. |
| Las evidencias Python persistidas del verificador anterior podían conservar PASS tras actualizar. | El informe instrumentado declara su versión de runner. Las evidencias Python anteriores se degradan a SKIP y una tarea done vuelve a ready al recargar. La regresión suplementaria falló antes del cambio y ahora comprueba migración y persistencia de un resultado nuevo. |
| Un nuevo import impedía ejecutar verify_quality.py como script autónomo en una copia mínima. | El preflight reprodujo ModuleNotFoundError en la integración de init. El comparador binario del ejecutor permanece autocontenido; la prueba de workflow existente pasa sin cambiar su oráculo ni exigir archivos nuevos a ese uso histórico. La salida del fallo queda en review-preflight-before-standalone-fix.json. |
| Cambios recientes introducían excesos de complejidad/argumentos en verify-quality, run-profile y test-command-gate. | Se extrajeron helpers manteniendo las interfaces utilizadas. Dos pruebas de presupuesto cubren esos contratos. La comparación con HEAD no detecta nuevos excesos y elimina uno existente en validate_policy. |

## Evidencia final

Los comandos, directorios, duraciones y logs están en [review-final-results.json](methodology-review-2026-09-30/review-completion-evidence.json). El manifiesto [review-source-manifest.json](methodology-review-2026-09-30/review-source-manifest.json) comprueba que los archivos del repositorio no cambiaron durante la validación final.

El Board aprueba 31 pruebas, sin skips, y `tsc --noEmit`. Los 63 contratos pasan la validación estructural. El preflight completo conserva explícitamente el SKIP de la capa opcional de seguridad por evidencia ausente; ese estado no equivale a una comprobación de seguridad aprobada.

| Verificación | Exit | Duración | Resumen observado |
|---|---|---|---|
| preflight | 0 | 489.15 s | Summary: 19/20; Skipped: 1 (optional evidence absent, not verified) |
| suite | 0 | 209.18 s | Ran 1036 tests in 208.024s; OK (skipped=1) |
| budget-oracle-inventory | 0 | 0.17 s |  |
| budget-oracle-execution | 0 | 0.15 s |  |
| budget-contract-acceptance | 0 | 0.16 s |  |
| budget-methodology-onboarding | 0 | 0.13 s |  |
| budget-verify-quality | 0 | 0.16 s |  |
| documentation | 0 | 0.75 s |  |
| seals | 0 | 0.21 s |  |
| diff | 0 | 0.07 s |  |
| clean-final-suite | 0 | 202.13 s | Ran 946 tests in 201.553s; OK (skipped=27) |
| clean-final-contracts | 0 | 262.46 s | Summary: infrastructure PASS=51 FAIL=0 SKIP=0; Summary: product PASS=4 FAIL=0 SKIP=0 |

La copia personalizada usa el venv ya instalado en la comprobación de onboarding y recibe únicamente los archivos cambiados; conserva las eliminaciones de ejemplos hechas por init. Sus omisiones se registran en el log. `KDD_SKIP_INIT_POST_APPLY_SUITE=1` evita repetir la integración pesada dentro de las suites posteriores; el preflight final la ejecuta sin esa omisión. Los comandos retenidos se registran en [review-final-clean-timings.json](methodology-review-2026-09-30/review-completion-evidence.json).

Los cuatro oráculos primarios de metodología y el nuevo oráculo primario del Board conservan sus hashes congelados. Se añadieron regresiones suplementarias inventariadas. Las modificaciones del Board en esta revisión corresponden al runner y al formato/validación de su evidencia; los otros archivos del Board registrados antes de la revisión mantienen sus hashes. Los envelopes locales con salida real pasan validate_attestation.

## Deuda heredada fuera del alcance

El usuario eligió cerrar la revisión de los cambios y documentar la deuda histórica. La medición global conserva **49 excesos en 22 contratos**, frente a 50 en HEAD: **cero nuevos y uno resuelto**. Por ello no se afirma que la validación global estricta de presupuestos esté verde. Los presupuestos Python revisados sí pasan; esta medición no acredita los presupuestos TypeScript del Board.

La comparación completa se conserva en [review-budget-comparison.json](methodology-review-2026-09-30/review-budget-comparison.json). Distribución:

| Contrato | Excesos heredados |
|---|---|
| assemble-context.md | 4 |
| attestation-gate.md | 2 |
| benchmark-gates.md | 2 |
| changelog-gate.md | 1 |
| check-agent-wiring.md | 1 |
| check-graph.md | 1 |
| commit-message-gate.md | 2 |
| diagram-gate.md | 5 |
| evidence-hardening.md | 1 |
| forbids-audit.md | 3 |
| lint-ascii.md | 3 |
| pages-build.md | 2 |
| perimeter-gate.md | 1 |
| rules-gate.md | 2 |
| seal-audit.md | 1 |
| skills-gate.md | 2 |
| ux-page-gate.md | 1 |
| validate-article.md | 2 |
| validate-okf.md | 4 |
| validate-payment-limit.md | 2 |
| validate-rules.md | 6 |
| validate-specs.md | 1 |

Los valores, funciones y topes exactos se enumeran al final de este informe. Corregirlos requiere un trabajo posterior con su propio alcance y pruebas.

## Migración y límites

- Para fixtures binarios sin NUL, declarar `-text` en los atributos aprobados antes de congelar el inventario. El entorno debe soportar `git check-attr --source`; un fallo de la herramienta bloquea la verificación.
- Volver a ejecutar las tareas Python del Board cuyos informes antiguos quedaron en SKIP después de actualizar.
- Los runners y oráculos aprobados forman parte de la confianza; no son un sandbox para código hostil. El marcador del runner no es una firma criptográfica y la escritura del almacenamiento local se considera confiable.
- El conteo de pruebas, su ejecución instrumentada y dos corridas no prueban cobertura semántica ni ausencia universal de intermitencias. La calidad de los asserts y la completitud del inventario requieren revisión.
- La aprobación independiente del SHA queda `NOT_EVALUATED` y la CI remota `NOT_RUN`. Esta revisión local no atribuye ninguno de esos resultados.
- Las corridas interrumpidas por cambios y el preflight intermedio fallido no cuentan como evidencia de cierre. El resultado final corresponde al árbol estable y registra las salidas reales de los gates.

La evidencia consolidada está en [review-completion-evidence.json](methodology-review-2026-09-30/review-completion-evidence.json). La publicación fue autorizada por el usuario el 2026-10-29. La validación de integración se documenta por separado.

## Detalle de la deuda heredada

```text
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:_validate_contract: cyclomatic_max=39 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:_assemble_okf_nodes: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] assemble-context.md:assemble: cyclomatic_max=28 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] assemble-context.md:assemble: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] attestation-gate.md:validate_report: cyclomatic_max=19 excede cyclomatic_max=16
ERROR [BUDGET_NESTING] attestation-gate.md:validate_report: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] benchmark-gates.md:main: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] benchmark-gates.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] changelog-gate.md:validate_changelog: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] check-agent-wiring.md:check_agent_wiring: cyclomatic_max=27 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] check-graph.md:find_graph_cycles: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] commit-message-gate.md:main: cyclomatic_max=13 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] commit-message-gate.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:parse_gantt: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_flowchart: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_gantt: cyclomatic_max=15 excede cyclomatic_max=14
ERROR [BUDGET_CYCLOMATIC] diagram-gate.md:_validate_journey: cyclomatic_max=17 excede cyclomatic_max=14
ERROR [BUDGET_NESTING] diagram-gate.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] evidence-hardening.md:main: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] forbids-audit.md:audit_contract: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] forbids-audit.md:main: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_NESTING] forbids-audit.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_NESTING] lint-ascii.md:_find_docstrings: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] lint-ascii.md:_lint_file: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] lint-ascii.md:_lint_file: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_PARAMS] pages-build.md:update_landing: params_max=5 excede params_max=4
ERROR [BUDGET_CYCLOMATIC] pages-build.md:build_pages: cyclomatic_max=13 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] perimeter-gate.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] rules-gate.md:_validate_golden_forma: cyclomatic_max=20 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] rules-gate.md:validate_rules: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] seal-audit.md:main: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] skills-gate.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] skills-gate.md:validate_skills: cyclomatic_max=27 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] ux-page-gate.md:_check_contrast: cyclomatic_max=17 excede cyclomatic_max=12
ERROR [BUDGET_CYCLOMATIC] validate-article.md:validate_article: cyclomatic_max=34 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-article.md:validate_article: nesting_max=6 excede nesting_max=3
ERROR [BUDGET_CYCLOMATIC] validate-okf.md:_parse_block: cyclomatic_max=11 excede cyclomatic_max=10
ERROR [BUDGET_CYCLOMATIC] validate-okf.md:_validate_frontmatter: cyclomatic_max=16 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-okf.md:_validate_frontmatter: nesting_max=6 excede nesting_max=4
ERROR [BUDGET_NESTING] validate-okf.md:_reachable_from_index: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-payment-limit.md:validate_payment_limit: cyclomatic_max=13 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-payment-limit.md:validate_payment_limit: nesting_max=4 excede nesting_max=3
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:_check_type: cyclomatic_max=12 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:_check_type: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:_check_bounds: cyclomatic_max=15 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:_check_bounds: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-rules.md:evaluate: cyclomatic_max=38 excede cyclomatic_max=10
ERROR [BUDGET_NESTING] validate-rules.md:evaluate: nesting_max=5 excede nesting_max=4
ERROR [BUDGET_CYCLOMATIC] validate-specs.md:validate_file: cyclomatic_max=13 excede cyclomatic_max=10
```
