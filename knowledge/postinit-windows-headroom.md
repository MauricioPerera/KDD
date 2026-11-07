---
type: 'Concept'
title: 'Reducir trabajo de preparacion del post-init Windows'
description: 'Eliminar procesos auxiliares de fixtures y conservar Git directo hasta verificar tres workflows completos bajo 480 segundos.'
tags: ['ci', 'windows', 'performance', 'integration']
---

# Objetivo y criterio de cierre

Completar el comando real de [init-project](contracts/init-project.md) en
**menos de 480 segundos en cada uno de tres workflows completos consecutivos
del mismo SHA final**. Conservar Ubuntu/Windows, las dos suites generales,
los 2.118 IDs anteriores, sus metodos y aserciones, los SKIP aplicables,
los 600 segundos operativos y el presupuesto seguro de 62 procesos Git.
Los casos nuevos se suman al inventario; no sustituir comprobaciones existentes.

Una muestra fallida interrumpe la secuencia y se conserva. No seleccionar tres
resultados favorables, promediar un incumplimiento ni confundir la duracion de
la suite interna con la del comando completo. Registrar tambien ambos jobs
de validacion, Board, SDK y el workflow para detectar desplazamientos de coste.

## Partida verificable

Las tres ejecuciones de `92f2df2a419220199bc9bde71996fd902c7fd7a4`, del run
[42327643094](https://github.com/MauricioPerera/KDD/actions/runs/42327643094),
pasaron funcionalmente. El comando Windows midio **448,813609 / 491,516650 /
465,170813 s**: el criterio de rendimiento sigue abierto. Ubuntu midio
171,965535 / 149,839777 / 167,209470 s. Las cuatro suites generales por
intento conservaron los mismos 2.118 IDs y las dos pasadas por sistema.

La muestra Windows lenta acumulo 3.818,335559 segundos de modulos con ocho
workers; su suite interna tardo 486,352212 s. Reordenar solamente los mismos
jobs ofrece poco margen. Se necesita reducir trabajo real.

## Cambios acotados

- [Preparacion local de fixtures](contracts/postinit-fixture-config.md): usar
  `configure_git` existente para los ajustes constantes de repositorios
  temporales propios. Conservar cada Git init/clone, historia, cierre,
  ejecucion del oraculo, evidencia, metodo y asercion. Mantener las pruebas
  dedicadas de mantenimiento automatico con su modo explicito.
- [Conservar Git directo](contracts/validation-native-git-path.md): no
  sustituir el ejecutable directo ya seleccionado por el workflow con el
  lanzador `Git/cmd`. No iniciar Git para preparar PATH ni cambiar su version,
  configuracion global, entornos de otros procesos o el workflow.

Estos ahorros locales no acreditan por si solos 480 segundos. Comparar la
propuesta con el original antes/despues/original, conservando configuracion,
historia, inventario y resultados. Si las tres muestras finales no cumplen,
el objetivo sigue abierto; no ampliar limites para declararlo terminado.

## Revision y publicacion

La [politica de calidad](quality-approval.md) exige revisar el commit concreto
de contratos y oraculos antes de adoptar los cambios. Presentar juntos el
diff de los fixtures congelados, sus sellos y una comparacion AST que conserve
todos los metodos de prueba y sus aserciones. No modificar otros oraculos.

Despues de la revision: completar las dos suites por sistema, los 19 gates,
post-init real, SDK y Board; registrar el arbol final preservando las entradas
existentes del registro y publicar un PR para las tres mediciones completas.
No fusionar ni cambiar protecciones. El runtime confiable de seis archivos
permanece intacto; cualquier cambio posterior exige otra revision especifica.
