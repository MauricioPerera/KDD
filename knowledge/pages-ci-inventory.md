---
type: 'Architecture'
title: 'Inventario verificable del CI en Pages'
description: 'Publicar el inventario de cuatro pasadas reales del mismo run y commit, y abortar ante discovery incompleto o evidencia incompatible.'
tags: ['ci', 'pages', 'verification']
---

# Garantia y origen de datos

El contador publico representa **IDs del inventario de CI**, no pruebas sin
skips ni una medida de cobertura. El CI mantiene Ubuntu/Windows y dos pasadas
consecutivas por SO. No se reejecutan las suites para calcular la cifra.
La [suite](contracts/ci-suite-processes.md) y el [runtime revisado](contracts/ci-trusted-execution.md)
siguen produciendo los reportes reales; sus seis archivos no cambian.

El defecto anterior contaba un _FailedTest como un caso al fallar el import de
tree_sitter: 38 casos se convertian en uno. El codigo de salida de imprimir un
conteo no demostraba discovery sano. La correccion tiene dos controles:

1. Discovery en un interprete nuevo: rechazar loader.errors, _FailedTest,
   inventario vacio e IDs duplicados. No ejecutar casos ni simular imports.
2. Para publicar desde main, exigir los inventarios exportados de las dos
   pasadas reales por SO, del run, intento, SHA y runtime revisado exactos.
   Comparar sus IDs con el discovery local completo antes de crear el output.

El [lector/exportador](contracts/pages-inventory.md) ejecuta esos controles;
el [workflow](contracts/pages-inventory-ci.md) fija la procedencia.

# Transporte y esquema

Tras las dos suites, cada job validate nativo de push a main exporta un solo
inventory.json desde los dos reportes frescos de kdd-suite-reports. Los valida
con las reglas existentes de run_test_suite.validate_report, exige ok=true,
runtime revisado coincidente, inventarios identicos y hashes de reportes
distintos. Falta, corrupcion, fallo o replay de un reporte abortan el export.
Export y verificacion de CI rechazan cambios rastreados respecto de HEAD;
el preview local puede trabajar sobre una propuesta todavia sin commit.
La salida debe ser nueva, fuera del checkout; no copiar stdout/stderr, rutas
temporales ni logs al manifest. No cambia los reportes ni el runner confiable.

Esquema v1 obligatorio del manifest:

```json
{
  "schema_version": 1,
  "repository": "MauricioPerera/KDD",
  "workflow_path": ".github/workflows/validate.yml",
  "run_id": 123,
  "run_attempt": 1,
  "head_sha": "<40 hex>",
  "platform": "ubuntu-latest",
  "trusted_runtime_ref": "<40 hex>",
  "ids": ["test_feature.T.test_example"],
  "ids_sha256": "<sha256 de IDs ordenados unidos por LF y LF final>",
  "passes": [
    {"report_sha256": "<64 hex>", "tests_run": 1, "skipped_count": 0,
     "fixture_omitted_count": 0, "duration_seconds": 0.1},
    {"report_sha256": "<otro sha256>", "tests_run": 1, "skipped_count": 0,
     "fixture_omitted_count": 0, "duration_seconds": 0.1}
  ]
}
```

Los enteros no aceptan bool; las duraciones son finitas y no negativas.
IDs no vacios, unicos, ordenados y sin sentinelas de import fallido. El conteo
de ejecuciones y omisiones debe explicar el inventario; los skips se declaran
segun el reporte real. No se convierten omisiones en pruebas pasadas.

Artifact por plataforma: kdd-ci-inventory-RUN_ID-RUN_ATTEMPT-PLATFORM, con solo
inventory.json, retention-days=7, if-no-files-found=error y overwrite=false.
El export/upload corre exclusivamente en el KDD nativo, push de main; no en
PR ni consumidores reutilizables. No agrega jobs, matrices ni permisos write.

Pages descarga ambos nombres exactos del workflow_run.id y run_attempt que
disparo el evento, en directorios ubuntu-latest y windows-latest separados.
No selecciona latest, glob ni otro intento. actions:read permite esa lectura;
los permisos de publicacion y la condicion de main exitoso se conservan.
Instala requirements-change-audit.txt antes del discovery estricto.

# Comprobaciones antes de publicar

El build recibe ci_inventory con directory, run_attempt y trusted_runtime_ref.
El run_id procede de ci_run_url y el SHA de git rev-parse HEAD; esa identidad
**no es una aprobacion de baseline**. Se exige el runtime proporcionado por la
configuracion revisada, conforme a [aprobacion](quality-approval.md).

Ambos manifests deben concordar en repositorio, workflow, run, intento, SHA,
runtime, IDs y digest. Cada uno contiene dos pasadas; sus cuatro hashes deben
ser distintos. Los directorios y platform deben corresponder sin duplicaciones.
Se exige igualdad exacta de IDs con el discovery local, no solo la cantidad.
Cualquier incompatibilidad produce exit no cero antes de mkdir(output),
publisher o upload. Evidencia ausente/expirada no activa un fallback.

En PR, el build real anterior a las suites conserva su CLI y usa discovery
estricto como **preview**: no existe aun evidencia de ese run terminado y no
se publica su bundle. El resultado incluye inventory_source=discovery-preview.
El despliegue usa inventory_source=ci-verified. El contador se etiqueta como
inventario de CI en en/es/pt; no afirma cobertura ni numero de pruebas pasadas.

# Integracion y limites

Acciones oficiales fijadas por SHA revisado, Node24:
- upload-artifact v7.0.2: cf430e030ddbb5b0abf93d22962f4752f3646cd9.
- download-artifact v8.0.2: 9000827ccba6bdab643e8b6fd33ac0654aef8333.

Referencias primarias: [upload](https://github.com/actions/upload-artifact/releases/tag/v7.0.2)
y [download](https://github.com/actions/download-artifact/releases/tag/v8.0.2).
El lector es stdlib local; no consulta GitHub ni necesita tokens. La confianza
en la procedencia depende del workflow revisado, del evento y de los artifacts
inmutables/digest comprobado por la accion; el JSON no es una firma ni sandbox.
No se descargan bundles HTML de PR ni se ejecuta contenido del artifact.

Las integraciones usan Git e interpretes reales, cuatro pasadas reales de la
suite en un proyecto minimo y archivos exportados; las etiquetas de SO en la
fixture son datos, no una emulacion de Windows/Ubuntu. La matriz real verifica
ambos entornos. Los controles de import/syntax/load_tests y replay deben fallar
por su causa pertinente. Ningun oraculo se adapta despues sin otra revision.
