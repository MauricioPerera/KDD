---
type: 'Concept'
title: 'Contexto entregado y aprendizaje enlazado a versiones'
description: 'Identificar fuentes y fragmentos reales, exigir contexto requerido y verificar relaciones de aprendizaje aprobadas.'
tags: ['governance', 'context', 'learning', 'provenance']
---

# KG-5: propuesta antes de implementar

Desarrolla el [objetivo](kdd-governance-closure.md), despues de los
[controles requeridos](required-controls.md). Los contratos de
[contexto](contracts/context-delivery-manifest.md),
[aprendizaje](contracts/learning-traceability.md) y
[compatibilidad del cierre](contracts/governance-report-initialization.md)
fijan las garantias mecanicas. Esta propuesta necesita revision propia y el
CI dual-OS 2x de KG-4 antes de implementar.

## Contexto: fuente y entrega

Conservar assemble, los providers, prioridades, presupuesto y todos los campos
anteriores. Agregar manifest con schema_version=1, context_sha256 y sources.
Cada fuente realmente recuperada tiene slot, origin, path, git_commit,
source_sha256, source_hash_method, raw_sha256, status y delivered_span/hash.
Los estados son full, truncated u omitted. Una fuente opcional omitida conserva
su identidad de origen; no recibe span ni hash de entrega. selected sigue
significando recuperado, no entregado completo.

source_sha256 identifica el texto UTF-8 con LF normalizado y declara
source_hash_method=sha256-utf8-lf. raw_sha256 identifica los bytes fisicos de
archivo. Runtime tiene path=null, raw_sha256=null y git_commit=null. Una lectura
de disco tambien tiene git_commit=null: no deducir un commit a partir del nombre
del repo o de HEAD. El hash identifica la version observada, no una firma humana.

Los spans [inicio,fin) son indices de caracteres de context, excluyen las
cabeceras de slot y usan su fragmento UTF-8 para delivered_sha256.
context_sha256 usa todo context, incluidas cabeceras y separadores. Para
okf_nodes, registrar cada ruta recuperada, tambien nodos cortados u omitidos;
rutas completas distinguen nombres repetidos. Mantener el ranking anterior.
El reporte/CLI incluye una linea CONTEXT_MANIFEST con exactamente ese JSON.

required es booleano y vale false por defecto. Un slot requerido ausente,
vacio por falta de seleccion, omitido o truncado aborta con CONTEXT_REQUIRED
y conserva resultado parcial con guardrails.abort=true. No aumentar presupuesto
para obtenerlo. expected_sha256 opcional para static fija el hash de texto
esperado; formato invalido se rechaza, version distinta bloquea. No inferir
una aprobacion del contenido a partir de ese pin.

Conservar el punto de lectura _read_file y observar entradas reales. Releer
identidades al terminar detecta cambios persistentes durante el ensamblaje:
una fuente requerida cambiada bloquea; su recibo no acredita una version
estable. No es un snapshot atomico ni deteccion de cambios transitorios
hostiles entre lecturas. Tampoco demuestra que un modelo recibio la respuesta
del API, la leyo, la comprendio o aplico sus reglas.

## Aprendizaje: enlaces declarados y aceptacion externa

El nuevo validate_learning.py es de solo lectura y usa Git real. Su placeholder
actual contiene solo un docstring: no implementa ninguna garantia.
CLI: --repo-root, --ledger, --approved-ref, --observed-ref (HEAD por defecto),
--require-accepted y --require-execution. approved_ref es OID completo canonico
externo, nunca HEAD o alias automatico. observed_ref se resuelve una sola vez.
El runner y la seleccion de la referencia requieren control externo; este
lector no autentica a quien escribio una cadena approved_by.

Ledger JSON: schema_version=1, entries. Cada entry tiene id unico, status
accepted|draft|legacy. accepted exige finding, decision y tests no vacios;
cada referencia tiene exactamente path, ref y sha256. path es relativa exacta
sin escape, glob, symlink o gitlink. ref es OID canonico de commit antecesor
de la aprobacion y del commit observado. sha256 usa LF normalizado y se verifica
contra un blob Git regular; nunca usar una correccion del checkout para suplirlo.
El path debe conservar el mismo contenido en observed_ref; de otro modo es
LEARNING_STALE. El checkout, indice y referencias permanecen intactos.

La entrada accepted completa debe estar identica en el ledger de approved_ref.
Una promocion o sustitucion hecha solo por el candidato es LEARNING_APPROVAL.
El lector verifica la referencia suministrada, no la identidad humana ni la
correccion semantica de esa aceptacion. Finding/decision son artefactos de
conocimiento; los nodos nuevos usan Concept, sin inventar tipos OKF adicionales.

La salida JSON determinista contiene schema_version=1, status PASS|PENDING|FAIL,
complete, approved_ref, observed_ref, accepted_count, entries y findings.
Los enlaces a tests declaran reference_verified=true y execution_observed=false.
No importar ni ejecutar producto. Exigir prueba de ejecucion sin mecanismo de
procedencia soportado produce LEARNING_UNSUPPORTED. Un hash de test no prueba
que se ejecuto ni que cubra adecuadamente el hallazgo.

Entradas draft incompletas son PENDING; legacy es LEGACY_UNVERIFIED sin inventar
enlaces o aprobaciones. complete=false y ausencia de garantia se mantienen
visibles. --require-accepted exige cobertura aceptada completa, no un inventario
vacio o pendiente. Una politica que requiere esta garantia debe proteger ledger,
runner, decision y tests, y declarar el CLI con referencias explicitas como
check obligatorio de [calidad](quality-approval.md), que lo ejecuta dos veces.
El lector aislado no se presenta como gate obligatorio de todos los proyectos.

El ledger propuesto `knowledge/governance-learning.json` incluye dos respuestas KG-1/KG-2
para revision en este baseline: hallazgos registrados, decisiones y oraculos
existentes versionados. Declararlas accepted aqui propone su aceptacion; solo
la aprobacion humana de este baseline proporciona la referencia externa que
permite validarlas. No se certifican retrospectivamente ejecuciones anteriores.

## Compatibilidad exacta para el cierre

Un probe en copia temporal confirmo que init_project elimina la spec 34 pero
preserva el eventual docs/reports/CONTRACT-34-REPORT.md. Ese huerfano impediria
la inicializacion despues del cierre real. Agregar solo esa ruta como limpieza
opcional explicita: si esta presente, planificarla una vez y retirarla con la
spec; si falta, no bloquear ni inventar un cierre. Incluirla en la transaccion
y precheck antes de escribir o borrar; no permitir directorios o aliases.
Nunca descubrir permisos por glob ni eliminar reportes ajenos.

Esta extension propone revisar tres expectativas exactas del oraculo anterior
test_init_project: conjunto eliminado con el reporte opcional, conteo 33 mas
su presencia exacta y pertenencia historica que contempla solo esa ruta.
Conserva IDs, metodos y demas aserciones. Su contrato actualiza exclusivamente
el sello por ese diff revisado; los 33 pares historicos y digests siguen intactos.
No crear el reporte real hasta tener el cierre y evidencia requeridos.

Produccion propuesta: assemble_context.py, nuevo validate_learning.py e
init_project.py. Conservar budgets vigentes de contexto/inicializador y
12/4/150/5 para el nuevo lector. Otra fuente, oraculo, dependencia, aumento de
limites o cambio de workflow/protecciones necesita una nueva propuesta.

La revision humana decide obligatoriedad y pertinencia del contexto, coherencia
de hallazgos/decisiones/tests, riesgos, comprension y generalizacion. El codigo
solo demuestra las identidades, relaciones y comportamientos que observa.

## Extension separada: JSON companero de cierre

La revision del contrato completion-evidence confirmo que el cierre nuevo exige
ademas docs/reports/CONTRACT-34-EVIDENCE.json. Un probe real en copia temporal
mostro que ese archivo conserva la identidad KDD despues de inicializar otro
repositorio. El baseline d10ae37136da409df99c5010986efad78f878df6 aprobo solo
el reporte Markdown. El [contrato de extension](contracts/governance-evidence-initialization.md)
propone esta segunda ruta exacta opcional con seis oraculos nuevos, sin tocar
ningun test previo ni ampliar otra fuente. Necesita revision propia antes de
implementar; todas las aprobaciones anteriores siguen vigentes.
