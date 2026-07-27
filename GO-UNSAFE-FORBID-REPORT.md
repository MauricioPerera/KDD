# GO-UNSAFE-FORBID-REPORT

## Resumen

Agregue el par `('unsafe', 'go')` a `_VERIFIERS` en `scripts/audit_forbids.py`,
con su funcion `_audit_unsafe_go`, analogo de `_audit_unsafe_rust` pero para Go.
Toque SOLO `scripts/audit_forbids.py` y `tests/test_audit_forbids.py` (como pide
la spec). NO toque ningun `knowledge/contracts/*.md`.

Funciones anadidas (nombres exactos, llamadas por el oraculo):
- `go_strip_noise(src) -> str`: quita comentarios de linea (`//`), comentarios de
  bloque (`/* */`, no anidables) y literales string RAW (backtick). **NO** quita
  los strings con comillas dobles (ver trade-off 1).
- `go_has_unsafe_import(src) -> bool`: True si el fuente importa el paquete
  `"unsafe"`, anclado al import (linea unica o bloque agrupado, con o sin alias
  `u`/`_`/`.`). No usa `\bunsafe\b` sobre todo el archivo (evita falsos
  positivos con `isUnsafe`/`unsafePool`).
- `go_denies_unsafe(target_path, repo_root) -> bool`: **siempre False**, con
  docstring explicando que Go no tiene mecanismo de compilador para prohibir el
  paquete `unsafe` a nivel proyecto. Punto de extension explicito.
- `_audit_unsafe_go(target, repo_root)`: si `go_denies_unsafe` (siempre False
  hoy, pero se llama igual que en Rust por consistencia) -> `[]`; si
  `go_has_unsafe_import` -> `[(FORBID_UNSAFE_PRESENT, ...)]`; si no ->
  `[(FORBID_UNSAFE_UNENFORCED, ...)]` con mensaje honesto sobre la ausencia de
  mecanismo en Go (no inventa un comando análogo al `unsafe_code = "deny"` de
  Rust).

Actualice el docstring del modulo y el del test file para reflejar dos
verificadores y que Go es deliberadamente distinto (verificacion de PRESENCIA,
nunca de enforcement).

## Salida real de la definicion de hecho

### 1. `python -m unittest tests.test_audit_forbids -v`

```
Ran 56 tests in 0.514s

OK
```

Los 19 tests de Rust existentes siguen en verde, MAS 37 tests nuevos de Go
(GoHasUnsafeImport: 14, GoDeniesUnsafe: 1, GoAuditFindings: 7, GoMainCli: 3, y
el resto de afinacion). Todos en verde. No rompi ningun test de Rust.

### 2. `python -m unittest discover -s tests -p "test_*.py"`

```
Ran N tests ... FAILED (failures=1)
```

Falla 1 test: `tests.test_init_project.TestInitProject.test_gates_verdes_post_apply_en_copia`.
La suite NO esta toda en verde. **Causa: el blocker de abajo (punto 3), no el
codigo de Go.** El test copia el proyecto y corre `validate_contracts` sobre la
copia; ese gate falla por el `tests_sha256` sellado de `forbids-audit.md` (ver
bloqueador). Sin ese bloque, todos los tests (incluidos los 56 del oraculo
forbids) pasan.

### 3. `python scripts/preflight.py`

```
validate_contracts: FAIL
validate_specs: PASS
validate_okf: PASS
lint_ascii: PASS
validate_rules: PASS
validate_skills: PASS
validate_changelog: PASS
validate_ux_page: PASS
validate_diagrams: PASS
validate_test_commands: FAIL
scan_secrets: PASS
validate_attestation: PASS
Summary: 10/12
```

**No es 12/12.** Arbol limpio (sin mis cambios, verificado con `git stash`):
12/12. Mis cambios rompen 2 gates. El conteo de gates de Nivel 1 no cambio (no
agregue ni quite gates); los 2 fallos son downstream de un solo problema.

### 4. `python scripts/lint_ascii.py scripts`

```
OK: todos los scripts son ASCII-conformes

Archivos salteados (# ascii-lint: skip-file): export_gate_contract.py

Resumen: 0 error(es) en 26 archivo(s)
```

0 errores. Mi codigo nuevo en `scripts/audit_forbids.py` es ASCII puro en los
literales string (los comentarios SI pueden llevar tildes, por convencion del
repo; mis literales string no llevan).

## Bloqueador (por que pare)

El contrato `knowledge/contracts/forbids-audit.md` (linea 16) sella el
`tests_sha256` de `tests/test_audit_forbids.py`:

```yaml
tests: "tests/test_audit_forbids.py"
tests_sha256: "fe9e43a3c4ff84e68227a97bd216ecf72a98965558bdfcfda821baa1d0c1283f"
```

La spec me pidio anadir tests a `tests/test_audit_forbids.py` (hecho, 56 en
verde). Eso cambio el hash del archivo. `validate_contracts` lo detecta:

```
ERROR [FM_TESTS_FROZEN] knowledge/contracts\forbids-audit.md: archivo
'tests/test_audit_forbids.py': hash esperado
fe9e43a3c4ff84e68227a97bd216ecf72a98965558bdfcfda821baa1d0c1283f, hash actual
22a71647ad72d1838b6a3518e02c14fdbfed2cb84a437a4773275520fddf369c
```

Cascada: `validate_contracts` FAIL -> `test_init_project` FAIL (corre
validate_contracts sobre una copia) -> `validate_test_commands` FAIL (corre el
test_command de init-project, que es `python -m unittest
tests/test_init_project.py`) -> preflight 10/12. Todo brota de UN solo sello
mismatch.

La spec decia: "no hace falta re-sellar ningun `tests_sha256` de contrato para
esta tarea -- no estas tocando ningun `knowledge/contracts/*.md` existente ni
agregando uno nuevo". Ese supuesto es **falso**: `forbids-audit.md` (un
contrato existente) sella exactamente el test file que la spec me mando a
extender.

La unica via a preflight 12/12 + suite verde es re-sellar `tests_sha256` en
`forbids-audit.md` al nuevo hash canonico (LF-normalizado):

```
22a71647ad72d1838b6a3518e02c14fdbfed2cb84a437a4773275520fddf369c
```

(calculado con `python scripts/validate_contracts.py --hash
tests/test_audit_forbids.py`, el comando que el propio gate sugiere).

Pero la spec prohibe explicitamente tocar cualquier `knowledge/contracts/*.md`
existente. Re-sellar contradice esa instruccion; no re-sellar rompe la
definicion de hecho 2 y 3. Es una contradiccion interna de la spec que el
usuario debe resolver. **No force el workaround** (re-sellar) sin aprobacion,
cumpliendo el ABORTAR-SI de "PARAR y reportar el detalle en vez de forzar un
workaround". Pregunte al usuario; rechazo la pregunta; por eso dejo el bloqueo
documentado y NO toco el contrato.

## Trade-offs

### 1. `go_strip_noise` NO quita los strings con comillas dobles (desviacion
   deliberada de la descripcion literal de la spec)

La spec describia `go_strip_noise` quitando "literales string con comillas
dobles (con escapes `\"`)" Y despues `go_has_unsafe_import` detectando `import
"unsafe"` "post `go_strip_noise`". Esas dos instrucciones son incompatibles: la
ruta de un import Go ES un literal con comillas dobles (`import "unsafe"`);
quitarlo dejaria `import ` sin el nombre del paquete, justo lo que hay que
detectar. En el bloque agrupado, `"unsafe"` desapareceria y no se sabria cual
paquete era.

Resolucion: `go_strip_noise` quita comentarios (linea + bloque) y raw strings
(backtick), pero **preserva** los strings con comillas dobles. Es seguro para
la deteccion anclada porque:
- Los strings con comillas dobles NO pueden spansar lineas en Go (los raw
  strings si). Solo algo que spansa lineas puede fingir una linea `import ...`
  dentro de un literal. Eso es exactamente lo que `go_strip_noise` quita
  (comentarios y raw strings).
- La deteccion se ancla a `^\s*import` (inicio de linea). Un string con comillas
  dobles cualquiera (que NO es un import) no empieza con `import`, asi que no
  matchea. Verificado con un test: `var s = "import \"unsafe\""` no cuenta.

Esto es la diferencia clave con Rust: en Rust `strip_noise` SI quita strings
porque `unsafe` es una keyword (no vive dentro de comillas); en Go la diana de
deteccion (`"unsafe"`) vive dentro de comillas dobles, hay que preservarlas.

La spec decia "post `go_strip_noise`" y eso se cumple: `go_has_unsafe_import`
si opera sobre la salida de `go_strip_noise`. La unica desviacion es que
`go_strip_noise` no quita los strings con comillas dobles, por la razon de
arriba. Lo documente en el docstring de `go_strip_noise` y en el docstring del
modulo.

### 2. Deteccion del import agrupado

El bloque agrupado se parsea con `re.finditer(r'^\s*import\s*\((.*?)\)', ...,
re.S | re.M)` (no greedy hasta el primer `)`). Aceptado como limitacion
(coherente con la filosofia de mini-parser del repo, igual que
`_sections`/`strip_noise` de Rust): un import path con comillas dobles que
contenga `)` (extremadamente raro, invalido en la practica para el paquete
`unsafe`) podria cerrar el bloque antes de tiempo. No se invento un parser Go
completo; no hace falta para detectar el import de `"unsafe"`.

### 3. Alias de import

El patron de alias cubre identificador (`u`, `unsafeAlias`), `_` (blank import)
y `.` (dot import), que son las 3 formas validas en Go. La spec menciona solo
`u` y `_`; anadi `.` por correccion (no cuesta nada y `import . "unsafe"` es
valido).

## Estado final

- `scripts/audit_forbids.py`: verificador Go implementado y registrado.
- `tests/test_audit_forbids.py`: 56 tests en verde (19 Rust + 37 Go).
- `knowledge/contracts/*.md`: NO tocados (cumple la instruccion explicita de la
  spec; por eso preflight queda 10/12, ver bloqueador).
- Pendiente de decision del usuario: re-sellar `tests_sha256` en
  `forbids-audit.md` (hash `22a71647...`) para llegar a 12/12, o aceptar
  preflight 10/12.