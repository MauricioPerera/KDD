# Validacion del PR #144 — 2026-11-02

Se integro main `01b264f4c38e88b15eef698b1d8792f4f7cac2c5` y se corrigio la incompatibilidad entre la seleccion del interprete activo y la revision de contramuestras. Las dos suites locales completas pasan. **La fusion sigue bloqueada:** el gate local de comandos conserva un timeout de inicializacion y el CI del PR exige una referencia revisada externa.

El codigo comprobado es [`a53a3337879bc05596332ee6e5b5a6edfdd69429`](https://github.com/MauricioPerera/KDD/commit/a53a3337879bc05596332ee6e5b5a6edfdd69429). Los archivos versionados conservaron sus hashes durante las ejecuciones. La publicacion posterior agrega documentacion y recibos; no representa otra corrida sobre un SHA distinto.

## Correcciones revisadas

- Se conservaron los nuevos controles de gobierno, revision de oraculos y restricciones requeridas de main al resolver los conflictos de integracion.
- La revision de contramuestras valida el comando declarado antes de vincular sus alias genericos al interprete activo. Mantiene las restricciones del comando y evita rechazar el ejecutable absoluto elegido por el runtime.
- La aceptacion usa la firma actual de `verify_quality.integrity`, conservando la comparacion binaria aprobada del inventario.
- Los siete oraculos primarios de esta revision conservan sus hashes. La regresion especifica paso 45 casos; las dos suites incluyen las pruebas afectadas.

## Resultados locales

Entorno: Windows AMD64, Python 3.11.15 aislado, temporales fuera de otro repositorio Git y SDK MCP en un entorno externo con dependencias fijadas y hashes verificados. Las suites usan el bundle externo revisado `57cb3e706b4eec756e98647e71f445dbfc6d6841`, con seis workers y su manifiesto conservado.

| Comprobacion | Resultado |
|---|---|
| Contratos estructurales | 165 archivos, cero errores |
| Comandos de contrato, limite 600 s | 164 PASS, 1 TIMEOUT; 155 ejecuciones y 10 resultados compartidos |
| Suite general 1 | 2.013 casos esperados/ejecutados; 0 fallos, 0 errores; 1.112,691 s |
| Suite general 2 | Los mismos 2.013 IDs; 0 fallos, 0 errores; 1.068,760 s |
| Fixtures de ambas suites | Cero omisiones y cero fixtures omitidos por SKIP |
| SDK MCP independiente | 8 casos reales, cero SKIP |
| Board | 86 pruebas, cero fallos y cero SKIP |
| TypeScript | `tsc --noEmit`, exit 0 |
| Workflows | Los tres workflows, actionlint 1.7.12, exit 0 |
| Inicializacion diagnostica | 16 pruebas, cero fallos y cero SKIP, 845,951 s |
| Atestacion local y escaneo de secretos de src | Exit 0 |
| Otros validadores de Nivel 1 | Exit 0; las capas opcionales sin datos conservan INFO |

Cada suite general registra nueve SKIP: ocho casos MCP, acreditados por el reporte SDK independiente con los mismos IDs, y la duplicacion del test pesado de inicializacion, ejecutado por separado. Ningun SKIP se cuenta como un caso aprobado. Las dos corridas comprueban repetibilidad basica, no ausencia de pruebas inestables.

El digest del inventario esperado y ejecutado de ambas suites es `95db896bee287c52a87d913a2538516d54f90bf5330f004cdb954c5d7db0eac6`. Los recibos incluyen los IDs, resultados de fixtures y hashes de los reportes completos y logs locales. No se publican los stdout extensos de las pruebas.

## Timeout que permanece abierto

La ejecucion completa de comandos termino con 149 PASS de infraestructura, 15 PASS de producto y un TIMEOUT de infraestructura: `init-project.md`, tras 600,033 s. Se repitio el intento de inicializacion con el binario nativo de la misma instalacion Git; no completo dentro del plazo. Se interrumpio la repeticion de los otros comandos ya comprobados, sin atribuirle un resultado verde.

El comando `python -m unittest tests.test_init_project`, ejecutado despues como diagnostico funcional separado del gate, completo sus 16 pruebas en 845,951 s. Esto distingue el resultado funcional del incumplimiento del plazo local; **no convierte en PASS el gate de 600 s**. No se modificaron su limite, las pruebas congeladas ni los presupuestos. `validation.json` conserva `all_required_passed: false` y el exit 1 real del gate.

Como referencia, el [CI Windows del main integrado](https://github.com/MauricioPerera/KDD/actions/runs/41362426808/job/125021320829) aprobo inicializacion y dos suites de 1.954 casos en 574,331 y 562,675 s. Es otro arbol y otro entorno: no acredita este PR ni explica por si solo la diferencia de rendimiento. Falta observar su propio CI con las referencias revisadas.

## Deuda heredada

Frente al main integrado: **72 excesos en la base y 72 actuales, cero nuevos o agravados, cero resueltos y tres mediciones reducidas**. Los cortes anteriores de 49 y 98 se conservan como historia. No se elevaron topes. Ver [comparacion exacta](pr144-readiness-2026-11-02/budget-comparison.json) y [tratamiento de la deuda](../../knowledge/deuda-presupuestos-heredada.md).

## Condiciones para fusionar

El [PR #144](https://github.com/MauricioPerera/KDD/pull/144) tiene Board aprobado en Linux y Windows para el codigo comprobado. `validate` en ambos sistemas y `trusted-pr-gate` rechazaron ese arbol con `APPROVAL_UNKNOWN_TREE`, antes de ejecutar su validacion completa. No se ha modificado el registro externo ni la proteccion de main.

La [politica del registro](../../knowledge/approval-registry.md) exige una referencia elegida por la persona revisora y una excepcion especifica para los archivos protegidos. El inventario obtenido del guard de main identifica estos seis cambios:

- `.github/workflows/validate.yml`
- `scripts/guard_pr_baseline.py`
- `scripts/trusted_ci.py`
- `scripts/validate_baseline.py`
- `scripts/validate_contracts.py`
- `scripts/validate_test_commands.py`

Pendiente: revision externa del SHA, admision del arbol final conforme a esa politica, autorizacion especifica de los seis cambios protegidos y CI requerido verde en ambos sistemas, incluida inicializacion dentro de su plazo. Este informe no declara aceptacion independiente ni disponibilidad inmediata para fusionar.

## Evidencia

- [Comandos, exits, duraciones y hashes](pr144-readiness-2026-11-02/validation.json).
- [Suite 1](pr144-readiness-2026-11-02/suite-1.json) y [suite 2](pr144-readiness-2026-11-02/suite-2.json).
- [Resultados de los 165 contratos](pr144-readiness-2026-11-02/command-timings.json).
- [SDK](pr144-readiness-2026-11-02/sdk.json), [oraculos conservados](pr144-readiness-2026-11-02/frozen-oracles.json) y [runtime externo](pr144-readiness-2026-11-02/trusted-runtime.json).
- [Arbol y archivos protegidos](pr144-readiness-2026-11-02/governance.json), [referencia CI de main](pr144-readiness-2026-11-02/main-ci-reference.json) y [regresion de integracion](pr144-readiness-2026-11-02/regressions.json).
