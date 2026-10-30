---
type: 'Architecture'
title: 'Sintaxis de todos los workflows antes de fusionar'
description: 'Control local con actionlint fijado, inventario completo y ejecucion temprana en el CI existente.'
tags: ['ci', 'workflows', 'syntax', 'integration']
---

# Problema y alcance

El [build de Pages en PR](pages-pr-validation.md) comprueba el publisher,
pero no interpreta el YAML de un workflow que no se ejecuta en ese evento.
Main 45c7c81 fallo antes de crear jobs de Pages: un run sin comillas contenia
`--only-binary=:all:`, cuyo colon seguido de espacio rompia el YAML.
El PR129 corrigio solo su representacion a bloque literal. Este control debe
rechazar esa regresion durante el PR, incluidos workflows de despliegue.

El [validador](contracts/workflow-syntax.md) usa actionlint 1.7.12, herramienta
local oficial, para sintaxis YAML, estructura y expresiones de GitHub Actions.
El [cableado](contracts/workflow-syntax-ci.md) lo ejecuta en ambos validate
existentes. Es un control del workflow de CI; el catalogo compartido conserva
sus [19 gates](validacion.md), cuatro jobs y dos suites completas por SO.

## Herramienta revisada

`tools/workflow-syntax/actionlint.json` fija version, repositorio, URL exacta,
archivo y SHA256 de archivo/binario por plataforma. Los paquetes de Windows,
Linux y macOS amd64/arm64 proceden de la release oficial v1.7.12. Ambos hashes
se comprobaron contra el archivo de checksums y metadatos de GitHub antes de
preparar el baseline. CI verifica el paquete antes de extraer un unico
ejecutable regular y verifica sus bytes antes de ejecutarlo, tambien en cache.
No se ejecuta un instalador descargado, una version latest ni un binario
tomado de PATH sin verificar. El cache guarda herramientas, nunca veredictos.

`install --cache-dir DIR [--archive FILE]` usa
`DIR/1.7.12/PLATFORM/{ARCHIVE,EXECUTABLE}`. Sin DIR usa el temporal del sistema
`kdd-actionlint`. Un archivo oficial predescargado permite instalacion offline.
Cache incompleto, enlace o hash incompatible falla; no se repara en silencio.
El destino es externo al checkout del tooling. Las descargas tienen timeout
de 30 s y limite de 64 MiB; errores de red/integridad no son SKIP.

Con `--github-env FILE --github-path FILE`, ambos obligatorios juntos,
install exporta solo tras exito KDD_ACTIONLINT_BINARY y KDD_ACTIONLINT_ARCHIVE
y agrega el directorio verificado a PATH. Esos archivos deben ser externos al
checkout, sin enlaces; no se aceptan saltos de linea en valores exportados.
La suite y sus copias inicializadas heredan esa herramienta para las pruebas
de integracion, que no necesitan red. Una actualizacion del tooling incluye
el nuevo script y manifest; su ausencia es un error, no una omision silenciosa.

## Inventario y veredicto

`check --repo-root DIR [--actionlint FILE]` inspecciona todos los hijos directos
de `.github/workflows` cuyo sufijo sea `.yml` o `.yaml`, ordenados por ruta.
Incluye archivos nuevos locales; en CI corresponden al checkout del PR/push.
No filtra por diff, nombre, evento, rama ni si el workflow se ejecutara.
Directorio ausente, inventario vacio, entrada no regular o enlace que escape
del proyecto falla antes de ejecutar la herramienta. No modifica los YAML.

El binario se obtiene del argumento, KDD_ACTIONLINT_BINARY, PATH o el cache
predeterminado, y siempre debe coincidir con el manifest del tooling. Check
no descarga paquetes. Invoca una vez el binario real, sin shell, con todas
las rutas explicitas, cwd del proyecto, timeout de 120 s y contencion del
[arbol de procesos](contracts/process-tree-timeout.md).

La configuracion se fuerza a un archivo externo nuevo `{}`. No se heredan
`.github/actionlint.y{a,}ml`, ignores ni opciones del candidato. No hay reglas
suprimidas. Se desactivan solo shellcheck/pyflakes: el control interpreta el
workflow, no ejecuta ni valida sus scripts run, acciones o servicios remotos.
Esas comprobaciones siguen en sus propios contratos y tests.

La salida JSON incluye ok, code, files, version, binary, diagnostics y
tool_exit_code. Cada diagnostico conserva filepath, line, column, kind y
message del motor real. PASS requiere inventario no vacio, exit 0 y lista
de diagnosticos vacia. Salida no JSON, exit inesperado, crash o timeout falla.
Codigos: WORKFLOW_SYNTAX_PASS; WORKFLOW_SYNTAX para errores de workflows;
WORKFLOW_SYNTAX_INPUT para inventario invalido; WORKFLOW_SYNTAX_TOOL para
ausencia, integridad, instalacion o ejecucion de herramienta. No hay fallback
a comparar strings ni un PASS inferido de stdout.

## Integracion en PR y bootstrap

Tras Check approved contract and oracle baseline, y antes de Node, publisher,
test_command y suites, validate ejecuta Install pinned workflow checker y
Validate all GitHub Actions workflows. Ambos usan shell python y bloques
literales; se ejecutan en Ubuntu/Windows sin condiciones por archivos/eventos.
RUNNER_TEMP aloja el cache; GITHUB_ENV/PATH transmiten la herramienta revisada.
Se mantienen permisos, pins oficiales, referencias y concurrencia existentes.

No se agrega job, tercera suite, filtro, continue-on-error ni permiso write.
El workflow reutilizable requiere el tooling compatible igual que los demas
helpers. La copia inicializada conserva script, manifest y oraculos; su suite
puede usar el binario heredado aun sin node_modules de Board.
El guard de main agrega script y manifest a PROTECTED_FILES, sin cambiar el
runtime confiable de seis archivos ni las protecciones remotas.

## Pruebas y limite de confianza

Procesos nuevos, Git real y binarios oficiales verificados en Windows/Ubuntu.
Controles independientes: workflows actuales sanos, YAML regresivo real,
formas valida literal/quoted y expresion invalida. Las integraciones cubren
ambos sufijos, archivo futuro, deploy no disparado por PR, configuracion que
intenta ocultar errores, cwd ajeno, archivos intactos, comando no ejecutado,
instalacion offline/cache y hashes invalidos. Se ejecutan los cuerpos Python
reales de los dos pasos en una fixture, con cache oficial prevalidado; no se
presenta esa prueba local como un run autenticado de GitHub.

Dos commits por cada ruta nueva demuestran que el guard rechaza su cambio
sin ejecutar el candidato. Se conservan los 1207 IDs y todos los oraculos
previos. Contratos/oraculos y manifest primero; baseline humano antes de
implementar conforme a [calidad](quality-approval.md). Publicacion, referencias
remotas y excepciones de fusion requieren su autorizacion correspondiente.
La confianza incluye Git, el SO, manifest/validador revisados y el motor
fijado. El checksum no es sandbox ni autentica la decision humana; tampoco
promete conocer validaciones futuras del servidor de GitHub.

Fuentes primarias: [sintaxis GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[release fijada](https://github.com/rhysd/actionlint/releases/tag/v1.7.12),
[uso y salida JSON](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/usage.md),
[configuracion](https://github.com/rhysd/actionlint/blob/v1.7.12/docs/config.md).
