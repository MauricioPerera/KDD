---
type: 'Concept'
title: 'Reducir preparaciones repetidas del auditor de cambios'
description: 'Propuesta acotada de fixture tras medir el post-init completo en Windows.'
tags: ['ci', 'performance', 'git', 'quality']
---

# Evidencia y limite

El run 42123163369 de 1c96f0c pasa los cuatro jobs funcionales, pero init Windows
tarda 555,242 s, con 547,330 s de post-init. Conserva 2000 casos, 178 modulos y 101 SKIP.
La ocupacion medida de los ocho workers explica casi todo ese tiempo; otro
orden de modulos no aporta margen suficiente para el
[objetivo de 480 s](postinit-windows-runtime.md).

El control local de concurrencia 8 -> 6 -> 8 da 367,639 / 386,293 / 387,561 s. Los dos
primeros pasan 2000 casos; el tercero registra un PID activo en el control de
contencion de calidad. Se conserva ese fallo, cuya causa sigue inconclusa.
No acredita mejora ni permite adoptar seis workers. Mantener el perfil actual.

El primer coste real Windows es test_validate_change_contract: 174,291 s.
Un diagnostico aislado de sus 38 casos registra 1038 procesos Git. Repite 38 veces
una preparacion identica de ocho comandos; el cuerpo de los casos usa 734.
El coste de esas preparaciones se puede evitar sin modificar el auditor.

## Propuesta para revision

El [contrato](contracts/change-fixture-seed.md) define una base por clase y
copias fisicas privadas por caso. No agrega una cache persistente, servicios,
hardlinks, alternates ni configuracion global. Los 38 metodos de prueba y sus
38 aserciones conservan sus AST exactos. Una construccion manual de la fixture
mantiene la preparacion original, necesaria para los seis controles existentes
de mantenimiento y sus dos commits reales.

Tres integraciones nuevas comprueban preparacion unica, independencia de
archivos/indice/objetos/config/refs, limpieza ante una colision real y
recuperacion despues de un fallo de Git. La fase roja reproduce tres fallos
de asercion en Windows/Ubuntu sin errores ni SKIP. La propuesta pasa 47 casos
por sistema, incluidos los 38 anteriores y los seis de mantenimiento. Los tres
nuevos tambien pasan desde una copia realmente inicializada sin .git.

La comparacion local A-B-A, con cuatro CPU logicas, da 28,776 / 22,253 / 29,628 s
para los mismos 38 casos. Los procesos Git pasan 1038 -> 742: la preparacion
304 -> 8; el cuerpo conserva 734. Son mediciones de un modulo, no del comando
completo ni del CI. El coste de los tres controles nuevos tambien debe entrar
en la comparacion neta del post-init.

## Revision y aceptacion pendientes

La propuesta del fixture congelado y sus dos sellos requieren un baseline
revisado segun [quality-approval](quality-approval.md), antes de adoptarse.
Luego corresponde medir el post-init completo, completar la regresion y
continuar sobre los costes restantes si el margen sigue siendo insuficiente.
No atribuir a este cambio aislado una reduccion hasta 480 s.

Conservar los 2104 IDs anteriores; los tres nuevos elevan el inventario a 2107.
Permanecen Ubuntu/Windows, las dos suites, presupuesto Git 62, timeout 600 s,
runtime 74d357f, workflows y protecciones. El cierre sigue exigiendo tres
workflows completos y consecutivos del mismo head final bajo 480 s en Windows.
