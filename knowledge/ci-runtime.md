---
type: 'Concept'
title: 'Reducir el tiempo total del CI sin reducir su cobertura'
description: 'Protocolo de paralelismo acotado, inventario de pruebas y mediciones comparables del CI completo.'
tags: ['ci', 'performance', 'verification']
---

# Resultado requerido

Reducir el tiempo del CI completo de KDD conservando las garantias de
[validacion](validacion.md), la [aprobacion externa](quality-approval.md),
la matriz Ubuntu/Windows de validate y board, Python3.11, Node24, los
19 gates y las dos pasadas completas, consecutivas e independientes.
Los contratos son [suite por procesos](contracts/ci-suite-processes.md) y
[comandos concurrentes](contracts/ci-command-workers.md).

## Frontera de la optimizacion

El runner de suite descubre los mismos casos que unittest discover y
comprueba que cada ID planificado se ejecuto exactamente una vez por pasada.
Paraleliza modulos completos en procesos separados, nunca tests en hilos del
mismo interprete: hay fixtures que cambian cwd, sys.path y os.environ.
No modifica aserciones, decoradores skip, datos, cobertura ni timeouts de
los tests existentes. No sustituye pilotos reales por mocks. Los hooks
de modulo/clase y el orden de casos dentro de cada modulo se conservan.
Las dos pasadas usan exactamente el mismo comando, entorno y paralelismo;
la segunda empieza solo despues de que termine correctamente la primera.
El nuevo ejecutable scripts/run_test_suite.py entra en PROTECTED_FILES
del guard confiable de main, igual que validate_test_commands.py; se prueba
con dos commits reales que sustituirlo es rechazado sin ejecutar el candidato.

El gate de comandos conserva una ejecucion real por comando unico y el
veredicto de cada contrato. El paralelismo es optativo; el valor por defecto
de su API y CLI sigue siendo1, compatible con consumidores que tienen
comandos dependientes o escriben archivos compartidos. Ningun resultado se
reutiliza entre invocaciones, commits, SO, pasadas ni directorios.

En el workflow, inputs string `suite_workers` y `contract_workers`, default
'1', permiten optar por concurrencia. El [perfil nativo por SO](ci-windows-suite-concurrency.md)
extiende el default de suite Windows a seis; Ubuntu y el lote de contratos
conservan cuatro. Proyectos inicializados y callers reutilizables conservan1
por defecto. Esta extension requiere su baseline antes de modificar el workflow. El fallback comprueba tambien
!inputs.reusable_execution, conservando1 en callers sin valor explicito.
Un valor invalido falla antes de
ejecutar pruebas. No se interpolan esos inputs como codigo de shell: pasan
por variables de entorno y argumentos entre comillas.

La integracion post-apply sigue ejecutando toda la infraestructura restante
en una copia real, una vez en el test_command de init-project. Esa copia
auditada usa el [perfil post-apply](contracts/init-post-apply-profile.md):
seis procesos en Windows y cuatro en Ubuntu. La seleccion es una hipotesis
de rendimiento hasta disponer de mediciones comparables. Las dos pasadas generales
conservan la unica exclusion previa KDD_SKIP_INIT_POST_APPLY_SUITE=1.
Ningun skip nuevo se acepta como optimizacion.

## Evidencia de cobertura y fallos

Cada invocacion produce un reporte JSON versionado que contiene IDs
descubiertos/ejecutados, resultados, skips con motivo, procesos y duracion.
La salida del test es informativa; el veredicto combina exit code y reporte
estructurado completo. Faltantes, IDs duplicados/ajenos, reporte ausente o
corrupto, crash, discovery fallida y proceso que sale0 sin ejecutar tests
hacen fallar el runner. Una suite vacia falla. expectedFailure y skip
conservan la semantica unittest y siguen visibles; unexpectedSuccess falla.

Los oraculos nuevos incluyen barreras entre procesos reales, limites de
concurrencia observados mediante intervalos, fixtures de modulo/clase,
segunda invocacion, fallos, ausencia de reporte e inventarios adulterados.
No deciden concurrencia por un umbral de segundos de una maquina compartida.
Para demostrar conservacion se compara el inventario anterior con el nuevo:
los1102 IDs previos permanecen, mas los casos nuevos aprobados. Los cambios
de cuatro oraculos de integracion son reemplazos del comando que comprueban
o ejecutan; se conservan sus casos y todas sus aserciones. Salvo la revision
del fixture Git descrita abajo, el resto de los archivos de pruebas permanece
byte a byte (normalizando LF).

## Medicion antes y despues

Antes: runs40073508632 (PR) y40094563794 (main), revisiones885abe8 y26cc3c1
con arboles Git identicos. Registrar ambos, sin seleccionar el mas lento:
validate Ubuntu202/199s, Windows1898/2167s; board Ubuntu19/19s,
Windows97/92s. Cuatro jobs por run, suite1102 dos veces por SO, board40.
El informe conserva metadatos, tiempos de pasos, version y hash de pruebas.

Despues: al menos dos ejecuciones exitosas de la misma revision candidata
en Actions con los cuatro jobs y los inventarios completos. Registrar
fallos y reintentos tambien. Comparar medianas de la ruta critica (desde
el primer job iniciado hasta el ultimo terminado) y de la suma de segundos
de los cuatro jobs; distinguir cola, tiempo de cada SO y Pages. No llamar
"ahorro total" al ahorro de un microbenchmark, ni a repartir mas runners
si sube la suma de tiempos. No agregar jobs/shards remotos ni cambiar los
cuatro nombres requeridos por la proteccion de main.

Cierre: ambas medianas del CI de validacion deben bajar, Ubuntu y Windows
deben conservar su inventario, dos pasadas y cero fallos, y board40 o mas
casos con cero skips. Objetivo practico: al menos25% en la ruta critica;
si no se alcanza, analizar las muestras antes de declarar la optimizacion
terminada. Los tiempos locales se comparan en el mismo host, interprete,
checkout y conjunto de pruebas, en serie; se reportan aparte. El inventario
y los hashes deciden equivalencia, no una cifra de conteo sin IDs.

## Revision y alcance

La segunda muestra del PR123 detecto una carrera de limpieza de un fixture:
Git puede dejar mantenimiento automatico desacoplado escribiendo en objects.
El [ciclo de vida Git](contracts/ci-git-fixture-lifecycle.md) limita su arreglo
a dos opciones locales del helper TaskProject: mantenimiento en primer plano,
sin apagarlo ni ignorar errores. El rechazo original se conserva; despues
del nuevo baseline revisado se requieren dos muestras verdes del mismo head.

Contratos/oraculos primero, fase roja y baseline de commit revisable antes
de implementar. Actualizar los sellos de ci-execution-deduplication,
ci-node24-actions, bootstrap-product-quality-ci e init-project solo por los
cambios de oraculo mostrados al revisor. Los specs y reportes historicos
cerrados conservan sus digests; esta extension reemplaza el mecanismo de
ejecucion, mantiene sus garantias y no altera cierres historicos.

Perimetro de implementacion: scripts/run_test_suite.py,
scripts/validate_test_commands.py, scripts/guard_pr_baseline.py (solo agregar
el nuevo runner a PROTECTED_FILES) y .github/workflows/validate.yml.
Documentacion: este nodo, contratos afectados, index y validacion.
No modificar politicas de producto, baselines remotos ni protecciones para
obtener verde. Cualquier cambio de oraculo adicional requiere otra revision.
La publicacion para medir Actions sigue el baseline humano aprobado.
trusted-pr-gate puede seguir bloqueando el workflow; su resultado se declara
por separado y cualquier excepcion de fusion requiere autorizacion puntual.
Los budgets son declarativos; no se afirma Nivel2.
