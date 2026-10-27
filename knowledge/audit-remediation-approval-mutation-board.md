---
type: 'Architecture'
title: 'Aprobaciones inmutables, mutacion controlada y formatos de Board'
description: 'Contratos previos para el P1 y dos P2 adicionales y una optimizacion acotada de lecturas de main.'
tags: ['quality', 'git', 'verification', 'performance']
---

# Alcance y orden

Continuacion autorizada de la auditoria de main b041a674. El PR136 se integra
con sus cinco commits originales antes de este trabajo. La base de esta
propuesta es ffd7ef8d8989b9bcdecd8ee907f2a4f6f643c470. Las pruebas preceden
a la implementacion y requieren el baseline de [revision humana](quality-approval.md).

Contratos: [identidad de aprobacion](contracts/task-approval-identity.md),
[controles de mutacion](contracts/mutation-control-evidence.md),
[formatos de Board](contracts/board-sha-formats.md) y
[lecturas frescas de main](contracts/task-main-read-budget.md).

# Aprobacion de tareas

approved_ref identifica un commit real completo del formato nativo. La forma
40/64-hex no prueba esa identidad: una rama de 64 hex en SHA-1 o de 40 hex en
SHA-256 sigue siendo movil. Resolver y comparar identidad exacta antes de
aceptar o auditar la aprobacion; rechazar aliases, abreviaciones, tags, trees
y objetos ausentes. No convertir una ref movil en aprobacion implicitamente.
Los OIDs de commits SHA-1/SHA-256 reales conservan su flujo completo.

El coordinador debe rechazar antes de publicar estados o ramas. La misma
comprobacion protege snapshots y registros persistidos, incluidos ready,
in_progress y done. No reparar registros anteriores eligiendo otro baseline.
Conservar la auditoria completa de historia y los modos regulares de Git.

# Mutacion con controles

Conservar la API y claves actuales del [auditor](contracts/mutation-audit.md).
Antes de mutar, ejecutar el original sin mutar en una copia externa y un
control de copia fiel independiente. No ejecutar oraculos en el working tree
real del usuario. Una
preparacion, importacion o ejecucion fallida de esos controles produce FAIL,
cero detecciones y ningun mutante ejecutado. El resultado agrega controles
con stage original/copy, status PASS/INCONCLUSIVE y exit_code o timeout.
--strict debe fallar ante controles fallidos; el CLI los presenta explicitamente.

La copia conserva las dependencias del proyecto, incluidos helpers de .agents;
excluye solo .git, caches Python y .agents/logs regenerables. El oraculo y su
sello no cambian. Una copia que pierde una dependencia no mide al mutante.
Con controles verdes, conservar DETECTED/SURVIVED/INCONCLUSIVE para cada
operador, timeout y conteos. El resultado no infiere causa semantica universal
de cualquier stderr. Usar contencion existente para las ejecuciones propias,
sin modificar [process_tree](contracts/process-tree-timeout.md) ni afirmar sandbox.

# Board y formatos Git

Store, HTTP, WebMCP y formularios conservan los SHA completos de 40 o 64
caracteres. La aprobacion contextual corresponde al coordinador; la UI no
elige HEAD. Una respuesta de commit de 64 caracteres permite confirmar y
refrescar exactamente igual que una de 40; una respuesta invalida no confirma.
Pruebas con Git real de ambos formatos, flujo completo y evidencia, HTTP
autenticado y WebMCP. El formulario usa DOM controlado, sin presentarlo como
una prueba de navegador real.

# Optimizacion acotada de Windows

Mantener la semantica de _clean_main: raiz exacta, rama main, indice y working
tree limpios, untracked completos y HEAD esperado fresco en cada invocacion.
No cachear estos datos entre comprobaciones ni ocultar cambios al codigo,
oraculos o estados. Consultar raiz y status porcelain v2 con branch permite
obtener la informacion en dos procesos Git reales por llamada en vez de cuatro.
El limite de dos se prueba con Trace2; no se usan segundos fragiles como assert.

Medir el mismo flujo sintetico de dos tareas y las mismas operaciones antes
y despues, en el mismo host/interprete, sin otra prueba nativa competidora.
Registrar procesos, comprobaciones de main y tiempo. Medir despues dos runs
verdes del mismo head en CI y comparar las muestras, diferenciando cantidad
de casos, cola y SO. No convertir ese microbenchmark en ahorro causal del job.

Medicion previa de esta base: dos tareas con bloqueo/reanudacion, 19 commits
y auditoria historica sin findings, 533 procesos Git por SO. Las 30
comprobaciones de main consumen 120 procesos: 20,703 s de 95,813 s totales
en Windows y 3,810 s de 12,166 s en Ubuntu/WSL. El presupuesto propuesto
reduce esas consultas a 60; el coste neto de las correcciones y el tiempo
posterior siguen pendientes. Son muestras locales, no estimaciones de CI.
El [CI del merge base](https://github.com/MauricioPerera/KDD/actions/runs/40447304734)
registra 6:56 para validate Ubuntu y 32:14 para validate Windows, con ambas
pasadas de 1483 IDs. Esta muestra y la del PR136 se conservan por separado.

Se mantienen Ubuntu/Windows, dos pasadas consecutivas con sus IDs exactos,
los 19 gates, limites, SDK real y Board. Oraculos previos y sus aserciones no
cambian. El bundle revisado de seis archivos, workflows, locks, variables y
protecciones quedan fuera del cambio; publicar para medir exige autorizacion.

# Cierre documental

Actualizar [cierre operativo](operational-closure.md) con referencias y
evidencia de OP-2/OP-4 y onboarding integrado. OP-3 sigue parcial hasta evaluar
sus metricas, no se marca por un CI verde. Conservar fallos y rechecks originales.
