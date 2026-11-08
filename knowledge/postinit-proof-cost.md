---
type: 'Concept'
title: 'Margen del post-init mediante pruebas Git de identidad y ascendencia'
description: 'Reducir procesos de las comprobaciones de tareas sin adelantar etapas ni reducir la auditoria.'
tags: ['ci', 'windows', 'git', 'performance']
---

# Objetivo y partida medida

Completar el comando entero de post-init Windows en **menos de 480 s en cada
uno de tres CI completos consecutivos del mismo SHA probado**. Mantener
Ubuntu/Windows, ambas suites, los 2.126 IDs anteriores, sus aserciones,
los SKIP aplicables, los workers y el timeout operativo de 600 s. Conservar
tambien el presupuesto seguro de 62 procesos de la auditoria anterior.

Las tres muestras de main 4b8b099dc9def58a2a2f377971425eae281e6a9e,
run [42422869860](https://github.com/MauricioPerera/KDD/actions/runs/42422869860),
intentos [1](https://github.com/MauricioPerera/KDD/actions/runs/42422869860/attempts/1),
[2](https://github.com/MauricioPerera/KDD/actions/runs/42422869860/attempts/2) y
[3](https://github.com/MauricioPerera/KDD/actions/runs/42422869860/attempts/3),
pasaron funcionalmente con 346,4837451 / 491,2734806 / 494,0385326 s de
post-init Windows. Las ultimas dos incumplen el objetivo; no se descartan.
Las cuatro listas de cada intento contienen los mismos 2.126 IDs. Cada
post-init conserva 2.022 casos y 185 modulos, sin fixtures omitidos.

El modulo test_task_committed_artifacts tarda 104,95 / 163,34 / 160,49 s.
Un perfil local de sus 19 casos, todos verdes, registra 1.545 procesos Git,
incluidos 298 rev-parse y 215 merge-base. La auditoria local de una tarea
realmente cerrada registra 53 procesos. Estos recuentos no acreditan ahorro
remoto ni identifican por si solos la causa de la variacion entre runners.

## Cambios propuestos y limites

- [Identidad del baseline y su ascendencia](contracts/task-approval-ancestor-proof.md):
  comprobar juntas ambas propiedades con una respuesta canonica de Git.
- [Cadena integrada de la tarea](contracts/task-evidence-chain-proof.md):
  comprobar base -> tip -> tested dentro de la etapa que ya pide esas dos
  relaciones y conservar el fallback serial cuando no se prueba el conjunto.

La segunda propuesta admite un recorrido Git auxiliar de hasta 2.048 commits.
Solo una cadena positiva demostrada por filas de commits realmente leidas
puede sustituir las consultas originales. Un recorrido truncado, ambiguo,
invalido, sin alguno de los endpoints o no soportado conserva las consultas
seriales y su primer error. No deducir False de un grafo incompleto ni
certificar un commit a partir de un OID que aparezca solo como padre.

Las pruebas positivas pueden ocupar exclusivamente la cache de operacion ya
existente, bajo la identidad del repositorio. Conservar sus decisiones para
pares calientes y refs moviles. No crear caches persistentes, lectores Git
persistentes ni resultados de validacion reutilizables. No leer por adelantado
contratos, tareas, artefactos, evidencia ni producto de otras etapas.

Los oraculos anteriores quedan intactos. Las integraciones nuevas cubren
coste real, identidades peladas, ramas divergentes, reemplazos, recuperacion
de objetos y grafos que superan el recorrido auxiliar, en ambos formatos
nativos. El flujo completo debe conservar snapshot, todas las transiciones,
perimetro, referencias originales y trazabilidad. Mantener los limites de
complejidad existentes, tambien para helpers nuevos.

## Protocolo de entrega y medicion

Definir y sellar los contratos y el oraculo; registrar fase roja y controles
en Windows y Ubuntu, tambien desde una copia inicializada sin .git. Presentar
el commit para la revision de [quality-approval](quality-approval.md) antes
de implementar. Comparar localmente original/propuesta/original con los mismos
casos, sin usar ese tiempo para aprobar el criterio remoto.

Completar los 19 gates y ambas suites por SO, SDK real, Board y Pages.
Conservar todos los IDs anteriores y sumar solo las regresiones nuevas.
Para medir en GitHub, registrar exclusivamente el arbol final revisado con
su baseline aprobado y conservar todas las entradas externas anteriores.
Mantener runtime, workflows y protecciones. Una publicacion o fusion que
requiera autorizacion adicional se presenta con el resultado concreto.

Medir tres intentos completos del mismo SHA real de checkout; registrar
head candidato, arbol, evento, run e intento. No mezclar SHA de merge de PR
y main ni presentar tres muestras de PR como tres de main. Un fallo funcional
o una duracion >=480 s rompe la secuencia. Conservar todos los intentos;
no repetir hasta obtener solo una seleccion favorable ni usar la mediana
para sustituir las tres mediciones individuales. El dato es KDD_INIT_TIMING
del comando entero, no la suite interna ni la duracion total del job.

La aceptacion final de esta optimizacion exige las tres muestras sobre el
SHA de entrega en main. El PR sirve para prevalidar la implementacion; sus
muestras no sustituyen las de main. La fusion se presenta para autorizacion
cuando exista una implementacion concreta y comprobada.

El objetivo sigue abierto hasta esa evidencia. Si el ahorro no basta,
continuar el diagnostico y someter cualquier ampliacion a otro contrato y
revision. Esta propuesta no autoriza ampliar timeouts, retirar pruebas,
alterar sus aserciones ni modificar controles remotos.
