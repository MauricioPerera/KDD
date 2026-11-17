---
type: 'Concept'
title: 'Diagnostico de tiempos antes de repartir las suites de CI'
description: 'Publicar una proyeccion de duraciones existentes sin alterar pruebas ni atribuirle aceptacion.'
tags: ['ci', 'performance', 'diagnostics']
---

# Primera entrega

La investigacion del 17 de noviembre encontro una mediana de 14:38 para
Ubuntu y 41:24 para Windows en cinco CI completos del dia anterior. Los
jobs esperaron entre uno y tres segundos desde su creacion. En el ultimo
[main medido](https://github.com/MauricioPerera/KDD/actions/runs/43913368575),
contratos y dos suites consumieron 694 de 755 segundos en Ubuntu y 1742 de
1834 en Windows. El reparto de [post-init](postinit-windows-runtime.md)
ya termina antes y no es la ruta critica de ese run.

El siguiente paso es hacer visibles las duraciones por modulo y contrato
que el [runtime existente](contracts/ci-trusted-execution.md) ya guarda. Publicar
solo la proyeccion definida en el [contrato](contracts/ci-timing-diagnostics.md),
no los reportes crudos que contienen salidas arbitrarias del producto.
No instalar dependencias, cambiar runtime, workers, jobs o permisos.

# Forma y limites del diagnostico

Un documento kdd-ci-timings contiene schema_version, kind, identity,
complete, missing y sources. identity identifica run, intento, checkout
GITHUB_SHA, plataforma y runtime esperado. Cada source identifica el hash
SHA-256 de los bytes leidos, tipo commands/suite, recorded_ok, duracion
total de suite (null en comandos) y sus filas permitidas.

La identidad es la etiqueta proporcionada por el job, no autenticacion
criptografica del origen: los reportes existentes solo incluyen runtime,
no run o SHA. Usar directorios nuevos propios del job, sin caches de
recibos. No inferir un numero de pasada por orden alfabetico de UUID,
mtime o duracion: las dos suites se identifican por source_sha256. La
instrumentacion de cobertura permanece en la primera pasada existente.

recorded_ok y exit_code transcriben el reporte; no verifican de nuevo
el oraculo ni conceden aceptacion. La proyeccion es un diagnostico, nunca
un sustituto de los [inventarios](pages-ci-inventory.md), cobertura,
gates o [aprobaciones](quality-approval.md). Una suma de comandos
concurrentes no es tiempo de pared. Las filas compartidas conservan su
representante y duracion cero; no cuentan como ahorro entre intentos.

Si no hubo reportes por un fallo previo, publicar complete false y la
lista missing, sin convertirlo en pipeline aprobado. Si existe un archivo
ambiguo o corrupto, fallar sin publicar un documento parcial. Rechazar
versiones desconocidas, runtime distinto, duraciones invalidas, duplicados
y rutas ajenas al checkout. Ignorar campos ajenos al esquema de salida,
sin copiar stdout/stderr, error libre, comandos, IDs arbitrarios o entorno.

# Secuencia posterior

1. Obtener el [baseline revisado](baseline-risk-review.md) del contrato y
   oraculos; implementar solo el exportador y dos pasos aditivos del CI.
2. Publicar tres CI completos del mismo candidato con tiempos comparables.
   Conservar SHA, runtime, inventarios y muestras fallidas. Comparar
   distribucion por modulo, por fase y minutos totales de runner.
3. Con esos datos, preparar un contrato separado para particiones de las
   suites ordinarias, dos pasadas por particion y reconciliacion exacta
   de IDs y cobertura. Medir antes de prometer una reduccion.
4. Evaluar por separado contratos en jobs paralelos y fixtures costosos.
   El pipeline ya usa seis workers de suite en Windows y cuatro en Ubuntu,
   cuatro de contratos y deduplicacion. Aumentarlos sin medir saturacion
   no acredita una mejora. Las caches de descargas tienen menor potencial.

Este candidato es de contrato y pruebas: no publica todavia metricas y no
afirma ahorro. No retira Windows, pasadas, pruebas, SKIP aplicables o checks.
