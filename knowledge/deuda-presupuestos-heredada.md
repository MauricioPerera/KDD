---
type: 'Concept'
title: 'Deuda de presupuestos heredada de la revision metodologica'
description: 'Inventario historico de 49 excesos Python, alcance acordado y criterio para tratarlos por separado.'
tags: ['quality', 'budget', 'debt']
---

# Deuda heredada de presupuestos

La revision metodologica conservaba **49 excesos Python en 22 contratos**, frente a 50 en el commit `224f722ba263e36f6aa4180a52b83fe41bc8d78e`: cero excesos nuevos y uno resuelto. El usuario eligio documentar esta deuda y cerrar la revision de los cambios. No se elevan limites ni se excluyen hallazgos para obtener un resultado verde.

Es una medicion historica del arbol revisado en septiembre de 2026. El main remoto avanzo desde entonces: estos 49 hallazgos no son una afirmacion sobre el total actual. La publicacion autorizada el 2026-10-29 conserva la evidencia y registra la integracion por separado.

## Corte de integracion del 2026-10-29

La integracion con main `1df365d2307a7058876bc609e09fb4af8c9c9ca9` compara 100 excesos heredados contra 98 actuales: cero hallazgos nuevos o agravados, dos resueltos y tres reducidos que todavia superan el tope. Los 49 anteriores se conservan como historia, no se suman a este total. El JSON completo de este corte esta en docs/reports/methodology-review-2026-10-29/integration-budget-comparison.json.

La regresion suplementaria de presupuestos compara funcion, medicion y tope contra el inventario de ese main, protegido en oracle_files. Permite conservar o reducir la deuda entrante; no permite hallazgos nuevos, mediciones peores ni topes elevados. No modifica los oraculos primarios congelados ni declara verde la comprobacion global estricta.

## Tratamiento posterior

1. Reproducir la medicion sobre el SHA que vaya a corregirse: `python scripts/validate_budgets.py`.
2. Definir un contrato y regresiones por grupo de funciones; conservar los oraculos aprobados.
3. Reducir complejidad, anidamiento, lineas o argumentos preservando comportamiento. Un cambio de topes requiere justificacion explicita.
4. Comparar contra la misma base y registrar los hallazgos resueltos y nuevos.

La [validacion](validacion.md) distingue este diagnostico de los gates obligatorios y la [aceptacion](acceptance.md) exige cobertura explicita de la obligacion budget. Un SKIP o un lenguaje sin medidor no acredita esa obligacion. El detalle tecnico del reporte y su JSON se publican bajo docs/reports/METHODOLOGY-REVIEW-REPORT.md y docs/reports/methodology-review-2026-09-30/.

## Inventario historico exacto

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
