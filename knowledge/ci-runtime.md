---
type: 'Concept'
title: 'Reducir el tiempo total del CI sin reducir su cobertura'
description: 'Protocolo de paralelismo acotado, inventario de pruebas y mediciones comparables del CI completo.'
tags: ['ci', 'performance', 'verification']
---

# Resultado requerido

Reducir el tiempo del CI conservando los 19 gates, la aprobación externa, la
matriz Ubuntu y Windows y las dos pasadas completas. [Validación](validacion.md)
y [protocolo original](../docs/reports/ARCHIVO-VALIDACION.md#resultado-requerido).

## Frontera de la optimizacion

La suite ejecuta módulos completos en procesos aislados y comprueba cada ID.
El gate de comandos ejecuta cada comando único y conserva el veredicto de cada
contrato. [Suite](contracts/ci-suite-processes.md) y
[comandos](contracts/ci-command-workers.md) fijan las garantías vigentes.
[Diseño y alcance original](../docs/reports/ARCHIVO-VALIDACION.md#frontera-de-la-optimizacion).

## Evidencia de cobertura y fallos

El veredicto combina exit code e inventario estructurado. Los IDs faltantes,
duplicados o ajenos, los reportes inválidos y las suites vacías hacen fallar
el runner. Los skips conservan su motivo.
[Controles originales](../docs/reports/ARCHIVO-VALIDACION.md#evidencia-de-cobertura-y-fallos).

## Medicion antes y despues

La comparación conserva muestras del mismo SHA, los inventarios por sistema,
las dos pasadas, los fallos y los reintentos.
[Tiempos, umbral y criterio de cierre](../docs/reports/ARCHIVO-VALIDACION.md#medicion-antes-y-despues).

## Revision y alcance

Los contratos y sus oráculos se revisan antes de la implementación. El
[archivo conserva el alcance exacto y la revisión del fixture Git](../docs/reports/ARCHIVO-VALIDACION.md#revision-y-alcance).
