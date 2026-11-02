---
type: 'Concept'
title: 'Inventario de inicializacion para el objetivo de gobierno'
description: 'Ajuste de inventario explicito para retirar la spec propia de KDD al instanciar un proyecto nuevo.'
tags: ['governance', 'initialization', 'quality']
---

# Extension necesaria para integrar KG-1

El [objetivo de gobierno](kdd-governance-closure.md) agrego CONTRACT-34 como
spec abierta. No es un cierre historico ni un nuevo par de legacy. La
[inicializacion](contracts/init-project.md) elimina solo rutas exactas
revisadas; su inventario anterior contiene los 33 pares cerrados de KDD.

El CI de [PR 148](https://github.com/MauricioPerera/KDD/pull/148), candidato
25e7aab0376ff545c51ea77d5dab3f3681586db1, encontro dos fallos en init-project:
el oraculo espera 33 specs y la copia inicializada conserva CONTRACT-34.
El discover posterior rechaza esa spec ajena en el proyecto nuevo.
Run: [41236928099](https://github.com/MauricioPerera/KDD/actions/runs/41236928099).

La propuesta agrega exclusivamente
specs/CONTRACT-34-kdd-governance-closure.md al inventario de limpieza.
Mantiene los 33 reportes historicos y los 33 digests de completion-legacy
sin cambios. No agrega un reporte de cierre de CONTRACT-34 ni autoriza glob:
una spec o un reporte propios de otro numero se conservan byte por byte.
Si falta la ruta nueva, el precheck debe abortar antes de borrar archivos.

La revision cambia el conteo del oraculo de inicializacion a 34 specs y
agrega una asercion de pertenencia de la ruta exacta. Conserva todas las
demas aserciones y agrega cinco contramuestras de copias reales en el
[contrato de compatibilidad](contracts/governance-initialization.md).

Baseline aprobado: 4e698f52f27a970a0be83c7db9854a687bf0f803, posterior a la
aprobacion de los dos modulos de tareas. El inventario se implemento en
4d968eafd33cf76f28f97f1d7d78bddf62b758a4 y paso el
[CI dual-OS 41239179528](https://github.com/MauricioPerera/KDD/actions/runs/41239179528)
con dos pasadas completas. Se conserva la
[aprobacion de calidad](quality-approval.md) y el historial de la fase roja.
