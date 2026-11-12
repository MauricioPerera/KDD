---
type: 'Concept'
title: 'Correcciones prioritarias de la auditoria EGM'
description: 'Contratos de cierre instrumentado, identidad del guard y aislamiento de la accion compuesta.'
tags: ['review', 'quality', 'ci', 'tasks']
---

# Correcciones prioritarias de la auditoria EGM

La auditoria de `144168d` reprodujo tres fallos prioritarios en copias Git
descartables. La implementacion se organiza por las interfaces afectadas.

| Garantia | Contrato | Evidencia de cierre |
| --- | --- | --- |
| Ejecucion real en tareas Git y Board | [Oraculos de tarea](contracts/task-oracle-execution-proof.md) | Cero casos y salida Python temprana bloqueados, cierres genuinos con recibo instrumentado y lectura de v1. |
| Identidad de la revision del PR | [Guard ligado al evento](contracts/trusted-pr-event-binding.md) | Merge real con ambos padres exactos, pruebas de refs movidos y revision protegida intacta. |
| Primer CI de adopcion por accion compuesta | [Checkout aislado](contracts/composite-quality-checkout.md) | Dos rondas de calidad en consumidor limpio y rechazo de cambios ajenos. |

La revision de riesgo se vincula al commit exacto de contratos y oraculos.
Los ajustes de fixtures del guard representan el payload nuevo y conservan las
pruebas anteriores de routing y revision externa. Ubuntu y Windows conservan
la cobertura y las dos pasadas de la suite. La medicion de post-init mantiene
su criterio independiente en [el protocolo vigente](postinit-windows-runtime.md).
