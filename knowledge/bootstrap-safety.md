---
type: 'Architecture'
title: 'Bootstrap confinado, recuperable y reproducible sin cache'
description: 'Criterios para resolver escapes por enlaces, inicializacion parcial y dependencia heredada de actionlint.'
tags: ['bootstrap', 'filesystem', 'integration', 'quality']
---

# Alcance y contratos

La auditoria de main 6f2168d reprodujo escritura/borrado fuera de repo_dir por
symlinks, junctions y hardlinks; fallo de guia despues de limpiar; 27 fallos de
arranque por actionlint ausente. Los contratos separan
[perimetro fisico](contracts/bootstrap-filesystem-boundary.md),
[transaccion](contracts/bootstrap-transaction.md) y
[preparacion sin cache](contracts/bootstrap-cold-start.md).
Los [contratos existentes](contracts/init-project.md) conservan API e identidad,
manifiestos exactos, procedencia de scans y
[calidad obligatoria del proyecto](bootstrap-product-quality-ci.md).

## Perimetro

repo_dir se resuelve una vez como raiz fisica explicita. Un alias de la propia
raiz puede seleccionarse; por debajo de ella, ningun componente de una ruta
gestionada puede ser symlink, junction u otro reparse point. Solo se aceptan
archivos regulares con un unico hardlink en destinos gestionados existentes.
El preflight completo ocurre antes de borrar o reescribir. Un destino ausente
permitido para la guia debe tener ancestros seguros. Las rutas gestionadas
son MANIFEST, los scans de muestra exactos, los archivos reescritos y la guia.
No se descubre un nuevo inventario destructivo mediante glob. Los archivos
y enlaces propios fuera del plan se conservan.

La comprobacion de resolve por si sola no detecta hardlinks. El rechazo de
alias preexistentes y el reemplazo seguro de contenido evitan truncar otro
nombre del mismo inode. No se afirma confinamiento frente a un actor que
reescriba concurrentemente el filesystem o frente a codigo hostil en el host.

## Transaccion compartida

scripts/bootstrap_transaction.py expone
filesystem_transaction(repo_dir, paths), un context manager stdlib. paths son
nombres relativos exactos de archivos que el llamador de confianza modificara.
Antes de yield valida y captura las preimagenes. La API no es un sandbox para
callbacks arbitrarios. Las regiones anidadas de la misma raiz incorporan sus
rutas a una sola unidad de rollback; otras raices se rechazan.

init_project registra su manifiesto y reescrituras; bootstrap_project registra
la guia y delega una sola vez en init_project con su firma actual. Un fallo
recuperable propaga el error original despues de restaurar bytes, permisos y
mtime de los archivos del plan y retirar archivos/directorios nuevos propios
que queden vacios. No se borran cambios ajenos al plan. No quedan temporales.
Si la restauracion falla se informa explicitamente; no se devuelve PASS.
No se promete atomicidad frente a corte electrico, SIGKILL o fallo permanente
del dispositivo. No se ignoran errores de IO ni se usan sleeps/reintentos.

El preflight comprueba tambien KDD-START-HERE.md antes de invocar limpieza.
Dry-run valida el mismo perimetro y no escribe. Un fallo permite corregir
su causa y reintentar sobre la copia original conservada.

## Arranque frio

Quickstart y guia generada preparan el actionlint fijado mediante
python scripts/validate_workflows.py install, antes de suite/perfil. El cache
predeterminado permanece externo. Se explica el --archive oficial offline,
la comprobacion de hashes y el fallo explicito de instalacion. El bootstrap
no descarga ni ejecuta instaladores y conserva forbids de red/subprocess.
minimal mantiene su interfaz sin SHA; standard/strict mantienen la aprobacion
explicita. No cambian workflows, referencias aprobadas ni protecciones remotas.

La integracion fria inicializa una copia real y un Git nuevo. Elimina las
variables KDD_ACTIONLINT_*, retira actionlint de PATH y usa temporales vacios.
Ejecuta el comando real extraido de la guia con un archivo oficial verificado
como entrada offline, comprueba bytes instalados y ejecuta los 27 controles
reales de sintaxis en la copia. No hereda un binario/cache ni consulta la red.
No presenta ese control dirigido como otra suite completa del proyecto.

## Evidencia y cobertura

Pruebas de archivos, enlaces y procesos reales. Ubuntu usa symlinks; Windows
usa junctions sin exigir privilegio de crear symlinks de archivo. Hardlinks
y fallos IO son reales en ambos. La matriz de casos declara esas diferencias
sin omitir los tests de main. Los nuevos tests de inicializacion son aplicables
a la plantilla; una copia ya inicializada declara esa inaplicabilidad igual que
los controles de bootstrap anteriores. No es un SKIP por dependencia ausente.

Se conservan los 1240 IDs y todos los oraculos anteriores. Main sigue teniendo
19 gates, Ubuntu/Windows y las dos pasadas. La integracion post-apply completa
existente se conserva; los nuevos controles frios no la reemplazan.
Contratos, oraculos y dependencias de fixture primero; baseline humano segun
[aprobacion de calidad](quality-approval.md) antes de implementar. No se
resellan oraculos anteriores ni se reducen aserciones, umbrales o cobertura.
