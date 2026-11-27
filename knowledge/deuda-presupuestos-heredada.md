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

## Corte de integracion del 2026-11-02

El main `01b264f4c38e88b15eef698b1d8792f4f7cac2c5` y el codigo integrado `a53a3337879bc05596332ee6e5b5a6edfdd69429` registran 72 excesos cada uno: cero nuevos o agravados, cero resueltos y tres mediciones reducidas que siguen superando el tope. Los cortes anteriores son historicos y no se suman a este total. No se elevaron limites. Ver [inventario exacto](../docs/reports/pr144-readiness-2026-11-02/budget-comparison.json) y [validacion y bloqueos del PR](../docs/reports/PR144-VALIDATION-REPORT.md).

## Tratamiento posterior

1. Reproducir la medicion sobre el SHA que vaya a corregirse: `python scripts/validate_budgets.py`.
2. Definir un contrato y regresiones por grupo de funciones; conservar los oraculos aprobados.
3. Reducir complejidad, anidamiento, lineas o argumentos preservando comportamiento. Un cambio de topes requiere justificacion explicita.
4. Comparar contra la misma base y registrar los hallazgos resueltos y nuevos.

La [validacion](validacion.md) distingue este diagnostico de los gates obligatorios y la [aceptacion](acceptance.md) exige cobertura explicita de la obligacion budget. Un SKIP o un lenguaje sin medidor no acredita esa obligacion. El detalle tecnico del reporte y su JSON se publican bajo docs/reports/METHODOLOGY-REVIEW-REPORT.md y docs/reports/methodology-review-2026-09-30/.

## Inventario historico exacto

Las 49 mediciones originales están en el [inventario archivado](../docs/reports/ARCHIVO-VALIDACION.md#inventario-historico-de-49-excesos-python).
