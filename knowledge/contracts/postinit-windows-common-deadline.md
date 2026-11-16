---
type: 'Task Contract'
title: 'Plazo comun y evidencia de las particiones Windows'
description: 'Exigir dos recibos del intento exacto y medir la ventana conjunta con los tiempos de GitHub.'
tags: ['ci', 'windows', 'bootstrap', 'evidence']
task: postinit-windows-common-deadline
intent: 'Integrar las dos particiones en el check Windows obligatorio dentro de 600 segundos comunes.'
target: .github/workflows/validate.yml
language: yaml
signature: 'Verify Windows post-init partitions'
test_command: 'python -m unittest tests.test_ci_postinit_shards'
test_runner: python-unittest
budget:
  cyclomatic_max: 14
  nesting_max: 4
  params_max: 4
tests: tests/test_ci_postinit_shards.py
tests_sha256: '763cd35fbc775185277ca648b36da39c38b45023beebc8b83c46fa95030873a4'
oracle_files: ['tests/test_ci_postinit_shards.py', 'tests/test_fixture_preparation.py', 'tests/__init__.py', 'scripts/init_project.py', 'scripts/bootstrap_transaction.py', 'scripts/run_test_suite.py', 'scripts/process_tree.py', 'scripts/validate_contracts.py', 'scripts/validate_okf.py']
touch_only: ['.github/workflows/validate.yml', 'scripts/ci_postinit_shards.py']
deps_allowed: ['stdlib', 'GitHub Actions']
forbids: ['llm']
---

## Intent

Aplicar [las particiones](postinit-windows-partitions.md) a la validacion nativa
de Windows. La prueba de aceptacion en GitHub conserva el mismo SHA, intentos
atribuibles y las dos pasadas ordinarias con cobertura en la primera. El
[recibo de duracion existente](postinit-command-timing.md) sigue midiendo el
comando al que corresponde. Publicar la ventana conjunta en un registro
`KDD_POSTINIT_WINDOW` distinto.

## Interface

El workflow agrega el job matriz `postinit_windows`, con dos instancias
`Windows post-init (0)` y `Windows post-init (1)`. Corre en windows-latest
solo en el validate.yml nativo de MauricioPerera/KDD, para pull_request y
push a main. Comparte el SHA candidato, baseline aprobado, runtime, Python
3.11, Git nativo, entorno temporal privado, Node 24 y dependencias fijadas
del Windows original. Cada instancia mide el comando completo de su copia
en el paso `Run post-init shard`, con 600 s por proceso y resultado real.
Conservar el diagnostico de modulo donde hay timeout, identificado por particion.

Publicar un recibo de exito nuevo por job con el nombre
`kdd-postinit-shard-RUN-ATTEMPT-N`, archivo `receipt.json`. Limite 1 MiB.
Campos exactos: schema_version (1), run_id, run_attempt, head_sha, tree,
runtime_ref, shard (0 o 1), inventory (las dos listas de IDs del discovery),
expected_ids, executed_ids, fixture_omitted_ids y ok (true).
Los IDs son cadenas no vacias, unicas y ordenadas, de longitud acotada.
El worker solo publica este recibo al reconciliar reporte y veredicto exitoso.
El diagnostico parcial usa un artefacto separado.

El job obligatorio existente validate (windows-latest) usa
`KDD_SKIP_INIT_POST_APPLY_SUITE=1` en sus comandos de contrato exclusivamente
para este perfil nativo. Ejecuta ahi las demas pruebas de init. El paso
`Verify Windows post-init partitions` es obligatorio en ese mismo perfil y
ocurre despues de las dos pasadas y antes de exportar evidencia de Pages.
La puerta usa el ref/commit exacto del checkout y el recurso de jobs del
intento actual. Descarga solo nombres exactos del run y del intento, mediante
permisos de lectura vigentes. El verificador crea una copia inicializada
independiente y obtiene su inventario, sin lanzar otra pasada de la suite.
Salida 0 solo con evidencia completa dentro de la ventana.
El paso usa `ci_postinit_shards.py collect --repo-root .`. El colector
consulta unicamente el repositorio del workflow y el run/intento declarado,
con espera acotada si el check existente alcanza el paso antes de los jobs.
El workflow protegido fija el SHA-256 del driver como literal local de cada
paso y ejecuta los bytes comprobados desde un temporal externo. Antes de
ejecutar codigo candidato, resuelve Git y GitHub CLI desde el temporal del
runner y fuera del checkout. Guarda las rutas absolutas en outputs del paso.
El shell literal de Windows invoca Python desde el output del setup fijado,
recibido por el entorno del paso. El
verificador no consulta el PATH del checkout para resolver esos ejecutables.
Git no recibe el token. GitHub CLI recibe el token solo para API y descarga
del host github.com, sin configuracion ni PATH del candidato. El discovery
se lanza por separado desde una copia de
`git archive HEAD` con init real y sin el oraculo recursivo. No se le
heredan tokens ni los archivos de escritura de comandos GitHub. Su salida
no puede emitir el marcador del veredicto oficial.
El lector `read_receipt_archive(raw)` acepta una sola entrada regular
`receipt.json` acotada a 1 MiB, con JSON estricto sin claves duplicadas.
El colector consulta jobs y artifacts del run usando el intento y los dos
nombres exactos. Rechaza listados incompletos, duplicados, expirados y
descargas que no coinciden con el digest del artifact. La descarga usa el
cliente GitHub CLI con sus redirecciones a URLs firmadas.

`collect(root, identity, request)` permite reproducir la API con datos
de prueba. `request` recibe rutas relativas de la API y devuelve bytes.
La CLI real usa los mismos pasos y falla si no produce el veredicto
completo. Fallar tambien si el discovery termina sin su inventario validado.

Funcion verificable `verify(receipts, jobs, expected, identity)`.
Receipts son dos documentos del esquema anterior. Jobs es la respuesta
`{"jobs":[...]}` de GitHub para el intento exacto. Expected contiene las dos
listas canonicas de IDs del discovery independiente. Identity define
run_id, run_attempt, head_sha, tree y runtime_ref, mas jobs_head_sha.
En un PR el checkout usa el merge sintetico de GitHub; jobs_head_sha
identifica el head del PR segun el evento. En push ambos son el mismo SHA.
El run y el intento de las filas de API deben ser los actuales, incluso
cuando el endpoint tambien devuelve filas de una ejecucion anterior.
El resultado establece
`wall_bound_seconds` y cantidades para las dos particiones.

## Invariants

- Exigir las dos particiones y dos jobs exactos, con el mismo run, intento,
  SHA de checkout, arbol y runtime. Exigir un paso conocido completado con
  exito por job. Rechazar resultados fallidos, cancelados, ambiguos, obsoletos
  o de otro candidato. Rechazar rutas con alias, links y datos invalidos.
- Las dos copias acreditan discovery de todo el inventario, el asignado
  esperado y el ejecutado o reconciliado. Ambas listas canonicas son
  disjuntas. Comparar con el discovery independiente del propio checkout.
- Usar los tiempos started_at y completed_at del paso medido desde GitHub,
  en UTC normalizado. Restar el inicio mas temprano del fin mas tardio y
  agregar un segundo por la precision de los tiempos. El limite comun es
  600 s incluyendo el desfase de arranque del comando. Rechazar intervalos
  vacios, invertidos, ambiguos o por encima. Dos tiempos individuales bajo
  600 s son insuficientes.
- Conservar las dos pasadas Ubuntu y Windows, el runtime confiable y la
  cobertura en la primera. Mantener el orden y los gates existentes de
  Ubuntu y callers. No convertir evidencia parcial en verde ni aprobar
  con artifacts de intentos anteriores.
- El reporte de `init-project` del check nativo Windows es el resultado del
  comando ordinario cuando solo ejecuta las pruebas locales de init. El
  plazo oficial del post-init nativo Windows sale del registro conjunto.

## Examples

- Los pasos duran 401 s y 403 s y comienzan con 5 s de desfase. La cota
  es 409 s y el inventario completo pasa.
- Cada paso tarda 400 s y el segundo arranca 210 s despues del primero.
  La cota comun excede 600 s y falla aunque ambos jobs pasaron.
- Los recibos omiten el mismo ID, presentan intentos mezclados o una
  particion repetida. El check obligatorio falla.

## Do / Don't

Comprobar el inventario y la ventana con fuentes distintas. La medicion
local sirve para diseñar el reparto. El CI alojado confirma su resultado.

## Tests

Ejecutar el verificador con recibos emitidos por dos procesos reales, una
tercera copia con init y tiempos GitHub reproducidos por la API de prueba.
Cubrir ids perdidos o repetidos,
suplantacion de Git desde el checkout y CLI con host explicito,
intent/versiones ajenos, jobs fallidos y desfase. Verificar en el YAML el
alcance, dos jobs, descarga exacta, bloqueo de Pages y suites localizadas.
Mantener el resultado de los dos timeouts y medir en GitHub el nuevo SHA.

## Constraints

PARAR y reportar si cambia el perimetro, el runtime, los permisos, las
protecciones o el limite de 600 s. Aprobar primero el baseline y revisar
los cambios protegidos del workflow y oraculos preexistentes.
