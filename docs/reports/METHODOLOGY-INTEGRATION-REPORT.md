# Integracion de los cambios revisados con main — 2026-10-29

Los cambios se publican mediante el PR #144. Se integro main `1df365d2307a7058876bc609e09fb4af8c9c9ca9` conservando sus protecciones del vault, contexto Git, cancelacion de procesos y runtime confiable. Este informe sustituye los conteos historicos de septiembre para describir esta integracion; no atribuye aprobacion independiente ni CI verde al nuevo arbol.

## Cambios de integracion

- Inventario binario y ejecucion instrumentada coexisten con deduplicacion, deadlines y workers del main actual. La agrupacion distingue metadatos y plazos de ejecucion.
- El runtime externo incorpora los helpers instrumentados desde el commit revisado cuando estan presentes; conserva los bundles historicos. Una prueba real ejecuta el contrato instrumentado desde ese bundle.
- El guard de PR mantiene su uso autonomo con contratos historicos; el helper de inventario sigue siendo obligatorio para contratos con oracle_files. No se degrada una verificacion instrumentada por ausencia del helper.
- Las tareas JSON antiguas con campos minimos se leen sin reescribir su archivo. Los defaults son internos y su representacion historica se conserva; un estado done sin evidencia se presenta ready. Se agrego una regresion suplementaria que fallo antes de esta correccion.
- El Board clasifica timeout por el indicador killed aunque Node no incluya signal en el error, caso reproducido por la CI Linux. Se conserva la prueba primaria original.
- El setup de Node usa el pin revisado vigente de main, sin bajar su version. Los cinco oraculos primarios de esta revision conservan sus hashes.

## Presupuestos heredados

La medicion historica conserva 49 excesos frente a 50 en la base de septiembre. El main de octubre aporta 100 excesos y la integracion conserva 98: **cero nuevos o agravados, dos resueltos y tres reducidos aun por encima del tope**. No se elevaron topes para obtener estos resultados.

La regresion suplementaria ahora compara contra el inventario exacto del main entrante, protegido por oracle_files. Comprueba que no aparezcan funciones con exceso nuevas, mediciones peores ni topes modificados. No afirma que los presupuestos globales esten verdes. Ver [inventario completo](methodology-review-2026-10-29/integration-budget-comparison.json) y [tratamiento de la deuda](../../knowledge/deuda-presupuestos-heredada.md).

## Validacion observada

| Comprobacion final | Resultado |
|---|---|
| Regresiones afectadas por integracion y fixtures | 58 casos, OK |
| Board completo | 79 pruebas aprobadas, cero skips |
| TypeScript | tsc --noEmit PASS |
| Contratos | 137, cero errores |
| Nodos OKF | 216, cero errores |
| Workflows | actionlint PASS en los tres workflows |
| Escaneo de secretos | src sin findings |

La primera suite completa sobre `7a61dd824d072fe371fb3c041fc09fa806a0592d` inventario 1.720 casos y ejecuto 1.711 en 844 segundos, con seis fallos, un error de fixture y cuatro skips. No se considera una suite aprobada. Nueve casos quedaron omitidos por el fixture offline de actionlint no preparado en el directorio temporal seleccionado.

Se corrigieron la compatibilidad de tareas minimas, el pin de Node y el import del guard autonomo, y se preparo el archivo/binario offline verificado en el temporal elegido. Las 58 regresiones finales repiten esos controles y los nueve casos del fixture, mas inventario binario, runtime externo y calidad. La suite completa no se repitio despues; no se declara verde para el arbol final.

Persiste un fallo local del test de mutacion historico: el proceso hijo carga `C:/Python314/Lib/site-packages/src/__init__.py`, por lo que no importa src.app de su fixture. Se capturo el ImportError del control original; no se cuenta como mutacion detectada. El auditor, process_tree y su test son identicos a main. No se alteraron los paquetes globales ni se omitio la prueba para simular verde.

Los cuatro skips de la primera corrida corresponden a la integracion pesada de init, evitada para no duplicar la suite anidada, y a tres pruebas SDK sin KDD_MCP_SDK_PYTHON configurado. No equivalen a comprobaciones aprobadas. Las dos pasadas por SO con runtime externo revisado siguen pendientes.

## Estado remoto y siguiente condicion

La rama codex/reviewed-methodology-and-debt y el [PR #144](https://github.com/MauricioPerera/KDD/pull/144) estan publicados. Main esta protegido y exige validate y board en Linux/Windows, mas trusted-pr-gate. El registro externo no contiene una entrada revisada para el nuevo arbol: trusted-pr-gate y validate rechazaron la primera publicacion con APPROVAL_UNKNOWN_TREE. No se modifico el registro para autoaprobar el trabajo ni se eludieron las protecciones.

El PR permanece en borrador hasta que una revision independiente admita el arbol conforme a [approval-registry](../../knowledge/approval-registry.md), se ejecuten los checks requeridos y se cierre la validacion restante. No se fusiono main. Las rutas locales de los JSON describen el entorno real de ejecucion; los logs completos se conservan fuera del repositorio.

La evidencia consolidada incluye comandos, duraciones, fallos previos y hashes en [integration-evidence.json](methodology-review-2026-10-29/integration-evidence.json).
