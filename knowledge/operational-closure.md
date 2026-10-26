---
type: 'Concept'
title: 'Objetivo de cierre operativo de KDD'
description: 'Cerrar los pendientes de integracion, aprobaciones, rendimiento Windows, cobertura MCP y documentacion identificados tras PR134.'
tags: ['planning', 'quality', 'ci']
---

# Objetivo

Completar los pendientes identificados, con contratos y oraculos definidos
antes de implementar. Conservar Ubuntu/Windows, los casos y aserciones
existentes y dos pasadas completas de la suite. El cierre exige evidencia
por criterio; un CI verde no convierte un resultado inconcluso en PASS.

Este objetivo fue solicitado por el usuario el 26 de octubre de 2026.
Complementa la [validacion](validacion.md), la
[aprobacion de calidad](quality-approval.md) y los
[limites de confianza](verification-guarantees.md).

# Criterios de cierre y orden de trabajo

- [x] **OP-1: integrar PR134.** Conservar el commit original
  `034c9f3e93fc56e04f899c0cc3d993126e698fc6`, verificar CI y Pages para el
  merge y dejar main limpio y sincronizado. Fusionado en
  `fbfd60b16190301be25e641c0479057334f0c37e`.
  El [CI de main](https://github.com/MauricioPerera/KDD/actions/runs/40278730755)
  verifica dos pasadas de 1349 IDs por SO y 40 pruebas de Board por SO.
  [Pages](https://github.com/MauricioPerera/KDD/actions/runs/40280452511)
  vincula sus inventarios al mismo merge; la respuesta publica es HTTP 200
  y muestra 1349 casos del inventario. Las protecciones se conservan.

- [ ] **OP-2: aislar las referencias aprobadas.** Una aprobacion para un PR
  no debe invalidar main ni otro PR. Probar main y dos propuestas distintas
  con Git real, referencias externas revisadas y ausencia de interferencia.
  Rechazar referencias ausentes, ambiguas o invalidas; no elegir HEAD como
  aprobacion automatica ni ejecutar codigo del PR desde el guard confiable.
  Conservar los controles del workflow reutilizable y del bootstrap,
  incluido quality/product.json obligatorio en los proyectos inicializados.

- [ ] **OP-3: mejorar coste y estabilidad de Windows.** Medir antes/despues
  el trabajo costoso de integracion y el job completo, indicando las muestras
  y la variacion del entorno. Resolver la sobrecarga observada alrededor de
  init-project sin ampliar sus 600 s, eliminar pruebas o aprobar un timeout
  inconcluso. Las dos pasadas, los IDs anteriores y las aserciones permanecen.
  El contrato de optimizacion fijara la metrica concreta tras perfilar el caso;
  no se atribuye una variacion de host al cambio de codigo sin evidencia.

- [ ] **OP-4: verificar el adaptador MCP opcional.** Ejecutar sus ocho
  pruebas reales de protocolo en Ubuntu y Windows con SDK fijado y entorno
  aislado. Un SDK ausente/incompatible, cero tests o un SKIP no acreditan ese
  check. Conservar el perfil sin SDK para los consumidores que no lo usan y
  las dos pasadas generales. El [alcance del servidor](mcp-server.md)
  distingue el protocolo en memoria de un transporte stdio real.

- [ ] **OP-5: actualizar las instrucciones de desarrollo.** Corregir el
  nombre de presupuesto obsoleto del ejemplo de la skill y alinear la
  plantilla de PR con el runner aprobado, la doble pasada y el inventario.
  Documentar la operacion de las nuevas aprobaciones y la preparacion MCP.
  Enlazar la [fuente normativa](validacion.md) para evitar duplicaciones.

# Protocolo de ejecucion

Para cada cambio de codigo: contrato, integraciones reales, fase roja,
baseline revisable y aprobacion humana del SHA antes de adoptar el oraculo.
Las actualizaciones de runtime requieren su propia referencia revisada.
Conservar fallos, rechecks e inventarios originales junto con los resultados
posteriores; no fabricar un batch verde a partir de una ejecucion fallida.

Publicar mediante PR y verificar el CI del head exacto. Cualquier excepcion
a trusted-pr-gate o modificacion de protecciones requiere autorizacion
especifica posterior sobre un cambio concreto. Este objetivo no concede
una excepcion general a esos controles.

El objetivo permanece activo hasta cerrar OP-1 a OP-5 con sus evidencias.
