---
type: 'Concept'
title: 'Revision breve proporcional al riesgo antes del baseline'
description: 'Revisar causa, oraculo y viabilidad sobre un candidato Git exacto antes de solicitar su aprobacion.'
tags: ['review', 'quality', 'baseline', 'risk']
---

# Problema y alcance

La [aprobacion de calidad](quality-approval.md) protege la referencia que el
revisor aprueba, pero no estructura la revision anterior a esa decision.
Un contrato puede describir una solucion innecesaria o tener un oraculo
insuficiente aunque sus campos y su sello sean validos.

Esta propuesta incorpora una revision corta antes de solicitar un nuevo
baseline. Adapta la separacion entre autor y lector del
[Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model/tree/e9e1f06aa4e26e95cd4ed37210a0632202c429e9),
en particular su comprobacion de causa, reutilizacion y complejidad posterior.
No importa el plugin ni convierte las consultas a modelos en un gate de CI.
Su primera instalacion necesita aprobar los dos contratos enlazados abajo.

# Flujo propuesto

1. Definir contratos y oraculos y crear un commit candidato, aun no aprobado.
2. Elegir el SHA completo de la base y del candidato. Ejecutar
   `python scripts/baseline_review.py --base-ref BASE --candidate-ref CANDIDATO`.
   Inspeccionar su diff, objetos y piso de riesgo; no usar HEAD como aprobacion.
3. Hacer una revision proporcionada a ese riesgo y guardar el registro JSON
   fuera del commit revisado, por ejemplo en `.agents/logs/`. El registro no
   puede incluirse a si mismo en el arbol al que se vincula.
4. Ejecutar `python scripts/quality_baseline.py --base-ref BASE --candidate-ref
   CANDIDATO --review ARCHIVO.json`. Solo un registro completo produce
   `review_ready: true`. Esto significa listo para solicitar revision humana,
   no baseline aprobado ni permiso para implementar.
5. Presentar el SHA candidato, el registro y su resultado al responsable.
   Solo su aprobacion externa permite registrar el baseline y continuar.
6. Un cambio posterior de cualquier byte o modo del candidato exige otro
   registro. Conservar los informes anteriores; no actualizar su identidad.

Los comandos de este flujo no crean commits, no actualizan referencias,
no ejecutan codigo del candidato y no escriben en el repositorio. Su JSON se
emite a stdout; el operador decide donde conservarlo. El modo historico
`quality_baseline.py --policy RUTA --approved-ref SHA` conserva exactamente
su API y salida; no acredita esta revision nueva. No se modifican el registro
externo, el runtime, workflows, las protecciones ni el catalogo de 19 gates.

# Riesgo y esfuerzo

El piso combina el diff real (sin detectar renombres) y factores declarados.
Se revisa la union de rutas borradas y agregadas; un renombre no oculta el origen.

| Nivel | Piso mecanico | Revision minima |
| --- | --- | --- |
| low | Solo Markdown ordinario y sin factores de mayor riesgo | Una persona o agente distinto del autor; tres perspectivas en una lectura breve. |
| medium | Codigo u otros archivos, contratos y pruebas nuevos; factores api, performance o dependencies | Al menos un revisor independiente: humano o agente con contexto fresco declarado. |
| high | Cambios de confianza, modos no regulares, modificacion/borrado de pruebas o contratos ya existentes; factores security, data-loss, concurrency o trust-boundary | Dos identidades independientes del autor; humanos o agentes con contexto fresco declarado. |

Rutas de confianza: `.github/`, `.agents/`, `ccdd/`, `quality/`, `quality.json`,
`acceptance.json` y los scripts `guard_pr_baseline.py`, `approval_registry.py`,
`quality_baseline.py`, `validate_baseline.py`, `verify_quality.py`,
`verify_acceptance.py`, `validation_runtime.py`, `validate_contracts.py`,
`run_test_suite.py` y `process_tree.py` bajo `scripts/`. Los documentos
`knowledge/quality-approval.md`, `knowledge/acceptance.md` y este protocolo
tambien son de confianza. En `tests/` y `knowledge/contracts/` una ruta con
objeto previo se considera existente, incluso al borrarla o renombrarla.
Solo modos 100644 y 100755 son regulares. Una ruta ordinaria que no termina
en `.md` tiene piso medium. Se puede elevar el nivel, nunca reducir el piso.

El autor declara los factores y justifica el nivel elegido. La heuristica de
rutas es un minimo, no un detector de riesgos semanticos: un cambio de negocio
puede tener riesgo alto sin un nombre especial. El responsable revisa tambien
la omision de factores y puede exigir una clasificacion mayor.

Todos los niveles cubren tres perspectivas, sin exigir documentos separados:

- `simplicity`: causa, alternativa mas simple y reutilizacion comprobada.
- `oracle`: requisito que protege cada prueba, casos adversariales pertinentes
  y limitaciones; distinguir integridad del sello de fuerza de la prueba.
- `implementation`: archivos, interfaces y plan de verificacion contra el
  codigo real. Una afirmacion de rendimiento necesita medir el comando completo.

Un mismo revisor puede cubrir varias perspectivas. El nivel alto exige dos
identidades realmente distintas, no dos etiquetas de la misma ejecucion.
No se exige un humano adicional al propietario para cambios ordinarios; el
responsable puede revisar lo que produjo el agente y aprobar su SHA despues.
Si no hay agentes independientes disponibles, usar revisores humanos o dejar
el estado NOT_READY; no representar autorrevision como contexto fresco.

# Registro JSON v1

Claves exactas: `schema_version` (entero 1), `base_commit`, `candidate_commit`,
`candidate_tree`, `author`, `risk`, `risk_rationale`, `risk_factors`, `reviews`
y `findings`. Sin claves duplicadas o desconocidas, NaN, infinitos o mas de
262144 bytes UTF-8. Los OID son canonicos completos y minusculos del formato
nativo; base y candidato deben ser commits y base ancestro estricto.
Se rechaza historia shallow. Las lecturas no aplican reemplazos Git.

Cada review contiene exactamente `id`, `reviewer`, `kind` (`human` o `agent`),
`fresh_context` (booleano), `status` (`completed` o `not_run`), `lenses` y
`read_set`. Cada lens contiene `name`, `assessment` (`pass` o `blocked`) y
`rationale` no vacio. Nombres de perspectiva y revisores sin duplicados.
Un agente sin contexto fresco cuenta solo en low. Un humano distinto del
autor es independiente; no se afirma que desconozca instrucciones del proyecto.

Cada fuente de read_set tiene `revision` (`base` o `candidate`) y `path`
relativa exacta. Debe existir como blob regular en ese commit. Se pueden
incluir fuentes de apoyo sin cambios; la union de lecturas debe cubrir cada
ruta cambiada en candidate, o en base si se borro. No se siguen enlaces o
submodulos. El resultado incluye modo, OID y SHA256 de los bytes originales
para que una persona compruebe el material. No basta con referenciar HEAD o
archivos locales que difieran del commit.

Cada finding contiene exactamente `id`, `severity` (`blocker`, `major`, `nit`),
`status` (`open`, `fixed`, `accepted`, `contested`), `scope`, `rationale`,
`decided_by` y `evidence`. Scope es una ruta del diff. Rationale no puede ser
vacio; evidence usa el mismo formato que read_set y debe ser no vacio para
un hallazgo cerrado. Decided_by es null para open y la identidad de un revisor
completado para los otros estados. Accepted requiere un revisor humano:
un agente o el autor no acepta el riesgo por su cuenta. Fixed y contested
exigen evidencia legible y decision de un revisor distinto del autor.

Todas las revisiones solicitadas deben haber terminado. Un fallo o not_run
no equivale a cero hallazgos. Las tres perspectivas deben estar cubiertas y
en pass. Un blocker o major abierto bloquea; un nit abierto no. No hay rondas
minimas, repeticion automatica ni aceptacion automatica por alcanzar un tope.
La decision de cierre debe constar explicitamente. Un informe incompleto
o inconcluso es NOT_READY, nunca PASS.

# Interfaces y evidencia

La [lectura y revision](contracts/baseline-risk-review.md) y la
[entrada previa al baseline](contracts/baseline-review-entrypoint.md) definen
sus interfaces, oraculos y limites. CLI: exit 0 para inspect o revision lista,
exit 1 para revision bien formada pero no lista, exit 2 para datos o Git
invalidos. Inspect siempre devuelve `review_ready: false` y no `approved_ref`.
Verify devuelve `review_ready`, `risk_floor`, `risk`, `required_reviewers`,
identidades exactas y hallazgos mecanicos. Ningun resultado concede aprobacion.

Las pruebas usan repositorios y procesos Git/Python reales, sin red o modelos.
Comprueban riesgos, borrados/renombres/modos, identidades, bloqueos, fuentes,
rechazo de datos ambiguos, lectura del commit pese a un checkout alterado,
ausencia de escrituras y el modo previo al baseline del comando existente.
Se conservan los 2138 IDs anteriores, Ubuntu/Windows y las dos suites.
No se afirma que un CI verde demuestre la calidad semantica del informe.

# Limites de confianza

El JSON registra lo declarado por el revisor: el programa puede comprobar
identidad del material y completitud, no que una persona lo haya entendido,
que un modelo haya leido cada byte ni que dos nombres sean dos personas.
No hay autenticacion criptografica de autor, revisor o contexto fresco. Las
trazas reales del entorno, cuando existan, se conservan como evidencia aparte.
La fuerza de los razonamientos y la independencia las verifica el responsable.
El bootstrap conserva este protocolo y herramientas, sin heredar aprobaciones.
Los perfiles historicos siguen funcionando sin presentarse como revisados.
