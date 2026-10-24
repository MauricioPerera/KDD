---
type: 'Architecture'
title: 'Correccion de confianza y fiabilidad del CI'
description: 'Fronteras de confianza, procesos y compatibilidad para cerrar los cuatro hallazgos prioritarios de main.'
tags: ['ci', 'security', 'verification']
---

# Alcance y orden

Cerrar el P1 y los tres P2 observados en main 538ff64. Los contratos son
[ejecucion confiable](contracts/ci-trusted-execution.md),
[cancelacion de procesos](contracts/process-tree-timeout.md),
[compatibilidad unittest](contracts/ci-unittest-fixtures.md) y
[perfil de ejecucion](contracts/gate-execution-profile.md).
Se conservan las reglas de [calidad](quality-approval.md),
[validacion](validacion.md) y [tiempo total](ci-runtime.md).

## Raiz confiable

Un verificador protegido no debe importar modulos desde el checkout candidato
antes de decidir que codigo ejecutar. El workflow materializa un bundle de
archivos exactos desde un SHA de runtime confiable, fuera del checkout, y lo
arranca con Python aislado (-I). Ese bundle contiene trusted_ci.py,
run_test_suite.py, validate_test_commands.py, validate_contracts.py,
process_tree.py y execution_profile.py. Sus interpretes de control y workers
arrancan aislados; solo estos ultimos cargan deliberadamente los tests/producto.
Se conserva acceso al cwd y a los helpers locales necesarios para las pruebas.

En PR nativo, el runtime por defecto es el base SHA; en push protegido, el SHA
del push. Un override KDD_TRUSTED_RUNTIME_REF requiere un SHA completo revisado
y configurado fuera del PR; no se infiere del head del candidato. Los callers
reutilizables declaran su referencia de runtime revisada cuando el default no
aplique. Un runtime antiguo/incompleto falla con diagnostico: no se sustituye
silenciosamente por archivos del candidato. La primera migracion de este
workflow necesitara una referencia de runtime revisada antes de publicarse;
esta tarea no autoriza cambios de proteccion ni variables remotas.

El guard de main protege los nuevos archivos y rechaza altas/cambios de modulos
que suplanten nombres de stdlib o del bundle en las raices de importacion del
verificador. Lee Git como datos: nunca ejecuta el PR. La salida informativa no
acredita pruebas; el launcher requiere reportes nuevos, completos y coherentes
por invocacion. Las dos pasadas no comparten reportes ni resultados.

Esto protege la frontera de arranque e integridad del verificador. Los tests
siguen siendo codigo ejecutable sin sandbox: no se promete resistir a codigo
que controla el SO, el interprete, el bundle confiable o sus credenciales.

## Cancelacion y limites

Un timeout no esta terminado hasta cancelar y esperar el arbol contenido.
La pertenencia al grupo POSIX o Job Object Windows debe establecerse antes
de permitir que el comando objetivo cree descendientes. Si no puede establecerse
esa contencion se falla antes de ejecutar el objetivo. No se usa una carrera de
enumeracion de PIDs ni se matan procesos ajenos. El drenaje/limpieza tiene una
gracia acotada y no convierte timeout en PASS. No se garantiza contener procesos
que escapan deliberadamente de la contencion del SO; no es un sandbox.

El perfil comparte timeout por comando (600 s), limite agregado (1800 s), workers
(1 por defecto) y deduplicacion (true). Gates simples conservan 120 s. KDD nativo
mantiene su opt-in de cuatro workers en CI; no se propaga por nombre de carpeta
ni por entorno heredado a consumidores. El limite agregado es explicito y no
infinito; puede ajustarse sin falsificar resultados. Preflight y MCP lo exponen.

## Compatibilidad e inventario

Los skips de fixtures tienen identidad y alcance propios; no ejecutan los casos
que bloquean. El reporte conserva por separado IDs ejecutados, IDs omitidos por
fixture y sus resultados de fixture con motivo. La union disjunta cubre el
inventario descubierto. Fallos de fixture hacen fallar la suite. No se rellena
executed_ids ni tests_run con casos que no recibieron startTest.

load_tests se ejecuta en su modulo/paquete de origen, conserva orden, hooks y
FunctionTestCase; no se reconstruye suponiendo que todo case.id() sea importable.
La redescubierta de un worker coteja su inventario con el plan; divergencia,
duplicados, abortos y reportes incompletos fallan. No hay fallback que oculte
errores. Se conserva aislamiento por procesos y el limite de workers.

## Revision y aceptacion

Contratos y oraculos primero, fase roja con procesos/Git reales en temporales,
baseline de commit revisado antes de implementar. Se conservan los 1129 IDs
actuales y sus aserciones; solo se adaptan expectativas que codifican el comando
del workflow o los limites obsoletos. El diff de esas adaptaciones forma parte
de la revision, no se resellan pruebas para obtener verde.

Ejecutar integraciones con Python 3.11 y la matriz Ubuntu/Windows en CI, las dos
pasadas completas consecutivas e identicas, los 19 gates y Board. No anadir
skips, filtros, caches de resultados ni continue-on-error. No tocar cierres
historicos ni politicas de productos. Las mediciones de la auditoria se conservan
como antes; se reporta el coste nuevo sin exigir que arreglar seguridad sea gratis.
El informe local vive en .agents/logs/ci-audit-remediation-REPORT.md.
