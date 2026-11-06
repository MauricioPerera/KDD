---
type: 'Concept'
title: 'Propuesta de temporales del CI Windows'
description: 'Hipotesis de I/O que conserva pruebas y requiere medicion remota antes de aceptar resultados.'
tags: ['ci', 'windows', 'performance', 'evidence']
---

# Evidencia y alcance

El [contrato](contracts/windows-ci-test-temp.md) cambia unicamente la ubicacion
de los temporales del CI nativo Windows de KDD. No modifica la semantica de
lectura de Git ni evita comprobaciones. El runtime revisado sigue siendo
74d357f7099651b9b39dc8088f725183a672ec94.

El head b977892 pasa los cuatro jobs funcionales y las dos suites por OS con
2110 IDs exactos. Init Windows mide 568.9987731 s; post-init 559.7547453 s y
job 2911 s. Se conserva este FAIL de rendimiento, sin repetir por suerte.
La suma de tiempos por modulo es 4429.0846615 s, /8=553.6355827 s: hay poco
margen de cola ociosa. El objetivo 480 s no se alcanza cambiando solo el orden.

Los logs de ese run muestran fixtures y caches de Python en
C:/Users/runneradmin/AppData/Local/Temp, mientras el checkout y RUNNER_TEMP
usan D:. Es ubicacion observada, no una medicion comparativa de discos.
La hipotesis es usar un hijo privado de RUNNER_TEMP mediante las variables
estandar, sin una unidad fija, cache persistente, otro runner ni mas procesos.
No se afirma que la hipotesis cumpla 480 s antes de medir el comando entero.

## Estado de implementacion al 6 de noviembre de 2026

El baseline d221236bdcfdc3d82e353fd7cf644c97c2a0c7c4 y el diff exacto del
workflow fueron aprobados. La implementacion fe73f58a83fba7592fd76f87d36ac50e4d8534f7
agrega un paso de 31 lineas; no cambia lectores Git, runtime u oraculos previos.
Este corte precede su publicacion. PR161 conservaba 38 commits publicados
con head b977892; los resultados posteriores se registran en el PR.

Pasan las tres integraciones reales y actionlint. El inventario conserva
2110 IDs y agrega tres, total 2113, sin editar los 190 archivos Python previos.
En el perfil local con SDK configurado pasan los 185 contratos por OS.
Init Windows mide 408.2287113 s y Ubuntu 177.3177953 s, con 2009 casos post-init
y 101/102 SKIP respectivamente. Estas muestras locales no prueban el objetivo
remoto ni aislan causalmente una mejora frente al entorno anterior.

Ambos OS pasaron sus dos suites de 2113 IDs exactos, con los mismos motivos
de SKIP: Windows 9 /Ubuntu 10. Windows tardo 383.823/432.663 s y Ubuntu
163.795/138.713 s. El controlador Windows anterior quedo inactivo despues
de los contratos; su reporte parcial se conserva y no cuenta como completo.
La reconciliacion usa sus 21 pasos previos terminados y dos suites nuevas
del mismo codigo, SDK y runtime, identificando ambas fuentes.
SDK paso ocho casos genuinos y Board 86/86 por OS, sin SKIP en esos controles.
El primer perfil local omitia KDD_MCP_SDK_PYTHON y agregaba tres SKIP; sus
resultados se conservan y quedan excluidos de la aceptacion de cobertura.

Falta publicar el arbol final preservando el registro y los commits, y medir
las tres ejecuciones remotas.
No hay muestras aceptadas de rendimiento para esta propuesta. El
[estado general](estado-actual-kdd.md) conserva la distincion main/PR/local.

## Aplicabilidad y confianza

El paso inline queda en el workflow protegido; no se agrega un ejecutable
de preparacion mutable fuera del bundle confiable. Se aplica solo al modo
nativo KDD Windows. Ubuntu y consumidores reutilizables conservan su entorno.
El inicializador conserva ese bloque del workflow. Las pruebas ejecutan el
bloque real tambien en copias inicializadas sin .git; no dependen de ejemplos
ni agregan SKIP. Su ejecucion manual verifica el codigo en ambos OS; la
condicion del job mantiene el entorno del consumidor fuera del modo nativo.

## Protocolo de cierre

Primero revisar baseline de contrato/oraculo y diff exacto del paso.
Despues aplicar exclusivamente ese paso y verificar Node/Python/Git reales,
errores de ubicacion/escritura, acciones existentes, inventarios y ambas
suites por OS. Conservar los 2110 IDs previos, sus aserciones y SKIP. Registrar
el arbol final autorizado sin retirar las 55 entradas anteriores.

Medir el CI del mismo head final. Se requieren tres workflows completos
consecutivos, con cuatro jobs funcionales PASS, inventarios exactos e
init Windows <480 s en cada uno. No sustituirlos por microbenchmarks locales.
Si falla, conservar la muestra y continuar el objetivo. No fusionar ni
cambiar protecciones o runtime sin su autorizacion correspondiente.
