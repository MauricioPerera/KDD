---
type: 'Concept'
title: 'Margen pendiente del post-init tras las pruebas Git agrupadas'
description: 'Evidencia de main dab7bbb y siguiente alcance sujeto a revision antes de implementar.'
tags: ['ci', 'windows', 'git', 'performance']
---

# Estado comprobado

PR #168 conserva sus dos commits en main dab7bbbc3f40fbc8ae2165a3701c546b22d470b7.
Los tres intentos completos del [run 42442053586](https://github.com/MauricioPerera/KDD/actions/runs/42442053586)
pasaron funcionalmente en Ubuntu y Windows, con dos pasadas de 2.135 IDs por
sistema, 2.031 casos y 186 modulos de post-init, SDK 8/8 y Board 86/86.
Pages paso en los tres y main quedo limpio y sincronizado.

| Intento | Post-init Windows | Post-init Ubuntu | Windows <480 s |
| --- | ---: | ---: | --- |
| 1 | 340,0226381 s | 170,845599621 s | Si |
| 2 | 492,7425478 s | 173,493338078 s | No |
| 3 | 243,7861419 s | 169,055285499 s | Si |

El [objetivo](postinit-proof-cost.md) sigue abierto. No se descarta el intento 2
ni se usa una mediana o resultados de PR para sustituir el criterio de main.

# Diagnostico y siguiente contrato

El perfil opcional conserva 178 prioridades frente a 186 modulos actuales;
ocho quedan sin prioridad. El modulo nuevo test_task_proof_batches termina
ultimo en los dos primeros intentos: 13,9034 y 20,5844 s. Reproducir sus costes
con ocho workers y ordenar por el promedio medido simula un ahorro de 6,3505
y 9,6385 s. El segundo comando entero aun quedaria alrededor de 483,10 s.
La simulacion mantiene constantes las duraciones y no demuestra ahorro remoto.

Se descarta el experimento local CREATE_NO_WINDOW: sus medianas originales
18,19 / 19,80 ms son menores que los 35,25 ms de la variante. No se aplica.

El [nuevo contrato](contracts/task-perimeter-stage-batch.md) propone agrupar
lecturas de historia y cambios dentro de la etapa de perimetro, manteniendo
el camino original para grafos no reconocidos. El caso lineal de tres commits
usa actualmente diez procesos; la meta de esta etapa es como maximo dos.
La auditoria completa existente pasa de un techo 48 a 44, sin duplicar su caso.

El [perfil medido](postinit-module-order.md) puede actualizarse bajo su
contrato ya vigente, usando las tres mediciones completas del mismo SHA y
los costes de los casos nuevos, conservando todos los jobs y las fuentes.
Ambos cambios requieren regresion y nueva comprobacion remota; ninguno por
si solo autoriza declarar resuelto el plazo.

# Revision y limites

Definir y sellar los contratos y las pruebas primero. Presentar su commit
segun [quality-approval](quality-approval.md) antes de implementar. La propuesta
conserva los IDs, metodos y aserciones anteriores; solo estrecha el
literal del presupuesto 48 a 44 y actualiza los dos sellos compartidos.

Tras revisar: implementar, ejecutar los 19 gates y las dos suites por SO,
conservar inventarios y errores, medir el efecto neto y presentar el resultado
concreto antes de publicar un nuevo PR o registrar otro arbol. El runtime,
workflow, workers, timeout 600, limite seguro 62 y protecciones siguen intactos.
La autorizacion de fusion de PR #168 no incluye otra fusion ni excepcion.
