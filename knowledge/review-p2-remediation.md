---
type: 'Architecture'
title: 'Cache del fixture y consultas historicas independientes del checkout'
description: 'Corregir los dos P2 de revision preservando oraculos, escrituras protegidas e inventario dual de CI.'
tags: ['review', 'bootstrap', 'git', 'integration']
---

# Alcance

Base: main 725319f6. Los dos comentarios afectan al
[arranque frio](bootstrap-safety.md) y la
[trazabilidad](requirements-traceability.md). Se definen
[resolucion del fixture](contracts/bootstrap-fixture-cache.md) y
[metadatos versionados](contracts/task-committed-artifacts.md).

## Archivo oficial del fixture

La preparacion documentada instala actionlint en la cache predeterminada, pero
reviewed_archive no la consulta cuando no hay variables ni binario en PATH.
El archivo offline se resuelve con esta precedencia:

1. KDD_ACTIONLINT_ARCHIVE explicito.
2. Archivo vecino al binario seleccionado por KDD_ACTIONLINT_BINARY o PATH.
3. Archivo en la cache predeterminada del instalador, version y plataforma fijadas.

Un origen seleccionado ausente o corrupto falla; no se oculta usando otro.
Se conserva el hash oficial, la copia aislada y la ausencia de red.
Los casos instalan bytes oficiales con el instalador real, sin exports ni
cambios de PATH; el flujo de guia ejecuta los 27 oraculos de sintaxis.
Solo ese recorrido completo es propio de la plantilla. Los controles de
seleccion y corrupcion tambien aplican a una copia inicializada.

## Dos fronteras para las rutas

Snapshots y rangos leen el arbol Git de sus referencias resueltas. No dependen
de archivos ausentes, aliases, ediciones, symlinks o junctions del checkout.
Se conservan firmas y resultados de validate_snapshot, validate_range y build_trace.

contract_metadata conserva por defecto la proteccion del checkout para ready,
start y finish. Una opcion interna explicita de lectura versionada permite a
validate_tasks prescindir de resolver fisicamente esas rutas. Esa opcion exige
sintaxis relativa y existencia/modo regular de contrato, oraculo y target en
las revisiones pertinentes, incluidos los artefactos aprobados. Solo se admiten
100644/100755 de tipo blob; un payload valido con modo 120000 se rechaza.
Se conservan aprobacion, sellos y auditoria de cada transicion y diario importado.

En una tarea done la revision efectiva es verified_ref: la validacion historica
no exige que el target actual conserve su contenido. La vigencia corresponde a
la proyeccion existente. No se siguen enlaces Git ni se aceptan rutas de escape.
Un target ausente en Git no se valida por existir en el checkout.

El coordinador mantiene safe_path, main limpio, lock y runner reconocido. Una
consulta no ejecuta producto u oraculo, no materializa un checkout ni escribe
archivos para leer. No se duplica el validador en traceability_git.
Un reporte historico valido no aprueba el checkout actual: verify_quality
conserva por separado sus comprobaciones de integridad y perimetro fisico.

## Evidencia y revision

Las pruebas completan una tarea con Git/coordinador/oraculo reales y consultan
desde otro checkout. Usan symlinks POSIX y junctions Windows en temporales
propios, canarios externos, indice y referencias antes/despues. Crean modos
120000 mediante el indice Git sin privilegios para symlinks de archivo.
Los controles adversariales conservan errores de historia/evidencia aunque
haya aliases, y el modo de escritura conserva su rechazo de rutas inseguras.

Se preservan los 1316 IDs y todas las aserciones anteriores. La unica adaptacion
prevista de oraculo es reviewed_archive y el import de tempfile: requiere nuevo
sello y SHA revisado. Se registra primero la fase roja en ambos sistemas.
El baseline propuesto incluira esa correccion del propio fixture y las pruebas
nuevas; los lectores se implementaran tras la aprobacion explicita de
[quality-approval](quality-approval.md). No se elige HEAD como aprobacion.

Ubuntu/Windows, las dos pasadas, los 19 gates, workflows, manifest de actionlint,
runtime y protecciones permanecen intactos. Ningun caso nuevo se omite en el CI
de la plantilla; se conserva la inaplicabilidad documentada en copias inicializadas.

## Perimetro

Produccion: scripts/task_git.py y scripts/validate_tasks.py. No se cambia el
modelo Task. La adaptacion del fixture y sus sellos se revisa con los contratos
y oraculos. Los helpers de pruebas viven dentro de archivos de oraculo sellados.
La garantia cubre las rutas de metadatos indicadas, sin inferir semantica de
producto, dependencias transitivas o identidad de una aprobacion.
