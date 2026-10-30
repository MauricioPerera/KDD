# KDD Pages

La fuente de [GitHub Pages](https://mauricioperera.github.io/KDD/) vive en `site/`.
El [estado fechado](../knowledge/estado-actual-kdd.md) distingue el main
publicado de la mejora local del contador. Esta guia describe el builder y
los workflows de la rama que incorpora esa mejora.

## Flujo de PR y despliegue

| Momento | Comprobacion | Resultado |
| --- | --- | --- |
| PR nativo de KDD, Ubuntu/Windows | Publisher real, discovery estricto, `publish --check` y validacion bajo `/KDD/`, antes de las suites. | Preview: `inventory_source=discovery-preview`. No despliega ni acredita suites terminadas. |
| Push nativo a main, por SO | Dos pasadas completas con el runtime revisado; export de sus reportes JSON. | Un manifest por SO, ligado al run, intento, SHA y runtime exactos. |
| `deploy-pages`, tras CI satisfactorio de ese push | Checkout del SHA que disparo el evento, descarga de ambos manifests, discovery local y cotejo exacto de IDs. | `inventory_source=ci-verified`; reconstruccion y despliegue en `github-pages`. |

La cifra de portada representa **IDs del inventario del CI**, incluidos los
skips declarados. No mide cobertura ni equivale a pruebas pasadas. Cada
manifest resume dos pasadas; no se ejecuta la suite otra vez para contar.
Los [contratos y esquema](../knowledge/pages-ci-inventory.md) son la
referencia normativa; el [build de PR](../knowledge/pages-pr-validation.md)
explica la separacion de permisos. No se despliega el HTML producido por un PR.

## Preview local

Usa Python 3.11, Git y Node 24, desde la raiz del repositorio. Instala tambien
los parsers fijados: los imports de discovery los necesitan aunque no se
ejecuten los casos.

```sh
python -m pip install --only-binary=:all: -r requirements-change-audit.txt
npm ci --prefix site --ignore-scripts --no-audit --no-fund
python -m unittest tests/test_pages_build.py
python site/build.py --output ../kdd-pages-preview --ci-run-url https://github.com/MauricioPerera/KDD/actions/runs/40141077949
```

El destino debe ser nuevo y estar fuera del checkout; cambia la carpeta
hermana del ejemplo si ya existe. Los comandos no requieren continuaciones
de linea y sirven tambien en PowerShell. El run del ejemplo es historico:
en preview la URL solo aporta contexto, no demuestra que ese run haya
validado tus cambios locales.

El builder admite cambios rastreados sin commit en preview. Copia fuentes
publicas rastreadas por Git, genera conocimiento y skills, comprueba el
publisher y valida el bundle mediante un servidor temporal bajo `/KDD/`.
Los archivos nuevos sin agregar al indice no entran en esa copia. El JSON
final incluye `tests`, `ids_sha256`, `inventory_source`, `gates`, `reports`
y el destino. Los gates y reportes se cuentan desde el mismo checkout;
los reportes historicos mantienen su identificacion como tales.

Para comprobar solo discovery, sin construir el sitio:

```sh
python site/ci_inventory.py inspect --repo-root . --ci-run-url https://github.com/MauricioPerera/KDD/actions/runs/40141077949
```

## Reproducir la verificacion con manifests

El CI exporta desde los dos reportes reales nuevos de cada SO, despues de la
segunda pasada. `python site/ci_inventory.py export --help` muestra la CLI;
usa los metadatos de esa ejecucion y la referencia de runtime ya revisada.
El export y el build verificado exigen archivos rastreados limpios respecto
a `HEAD`. El export no crea una aprobacion ni autentica por si solo un run.

Cada artifact se llama
`kdd-ci-inventory-RUN_ID-RUN_ATTEMPT-PLATFORM`, contiene `inventory.json` y
se conserva siete dias. Pages descarga ambos nombres exactos del run que
disparo `workflow_run`, con comprobacion de digest. Organiza los manifests
asi para reproducir el cotejo:

```text
inventarios/
  ubuntu-latest/inventory.json
  windows-latest/inventory.json
```

Usa un checkout limpio del `head_sha` de esos manifests. Sustituye `RUN_ID`,
`INTENTO` y `RUNTIME_SHA_REVISADO` por sus valores reales, con el runtime
previamente aprobado en la configuracion externa:

```sh
python site/build.py --output ../kdd-pages-verificado --ci-run-url https://github.com/MauricioPerera/KDD/actions/runs/RUN_ID --ci-inventory-dir ../inventarios --ci-run-attempt INTENTO --ci-trusted-runtime-ref RUNTIME_SHA_REVISADO
```

Los argumentos `--ci-inventory-dir`, `--ci-run-attempt` y
`--ci-trusted-runtime-ref` deben proporcionarse juntos. El resultado debe
indicar `ci-verified`. El cotejo requiere el mismo inventario por IDs en las
cuatro pasadas y en discovery local; la igualdad del total no basta.
Una fixture local con metadatos sinteticos prueba la integracion, pero no
acredita procedencia de GitHub.

## Diagnostico de fallos

| Señal | Comprobar |
| --- | --- |
| `PAGES_DISCOVERY` | Import/sintaxis/`load_tests`, dependencias fijadas, IDs vacios o duplicados. Corrige la causa; un `_FailedTest` no cuenta como prueba descubierta. |
| `PAGES_CI_INVENTORY` | Ambos manifests, identidad run/intento/SHA/runtime, hashes de cuatro reportes distintos, inventarios coincidentes y checkout limpio. |
| Artifact ausente o expirado | Los dos SO deben exportar en el mismo intento. Una repeticion parcial puede dejarlo incompleto; ejecuta el CI completo y usa ese intento. No combines intentos ni selecciones el ultimo run disponible. |
| Destino existente o dentro del checkout | Elige una carpeta nueva y externa. La herramienta no borra el destino. |
| Publisher o validacion `/KDD/` fallidos | Instalacion desde `site/package-lock.json`, Node 24, fuentes publicas y enlaces del bundle. Conserva el error real. |

Discovery y cotejo del inventario ocurren antes de crear el destino o lanzar
el publisher. Los fallos posteriores pueden dejar un bundle parcial; no lo
uses para desplegar. Para reportar un problema, incluye comando, SHA, run,
intento y diagnostico pertinente, sin tokens ni datos privados.

## Firma demostrativa e historial

El `demo_seed` en `llms-skills.json` reproduce una firma demostrativa. No es
una credencial de identidad para producción. Si se requiere atribución
criptográfica del editor, configurar una clave privada fuera del repositorio.

Después de migrar la configuración de Pages a GitHub Actions, `gh-pages`
permanece únicamente como historial de la publicación manual anterior.
