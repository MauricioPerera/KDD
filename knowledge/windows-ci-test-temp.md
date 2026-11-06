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
