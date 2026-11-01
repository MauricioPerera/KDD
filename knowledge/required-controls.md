---
type: 'Concept'
title: 'Requisitos mecanicos con mecanismo y cobertura explicitos'
description: 'Aplicar budgets soportados y bloquear restricciones requeridas sin mecanismo efectivo, conservando limites honestos del legado.'
tags: ['governance', 'restrictions', 'budget', 'quality']
---

# KG-4: candidato verificado en CI

Desarrolla el [objetivo de gobierno](kdd-governance-closure.md), despues de la
[garantia de oraculos](oracle-assurance.md). La implementacion candidata conserva
el baseline humano 17800863ecca2b41c168076dd7c4a73da00a8460 y sus oraculos.
La condicion previa se cumplio con el CI de KG-3 antes de implementar. El candidato
e202760c01b7d5d1978f1419859f2919f586a838 del [PR 152](https://github.com/MauricioPerera/KDD/pull/152)
completo el [CI 41256786660](https://github.com/MauricioPerera/KDD/actions/runs/41256786660):
143 contratos y dos suites de 1796 casos en cada sistema, con inventario identico,
cero fallos, errores u omisiones de fixture. Conserva los SKIP normales (10 en
Ubuntu, 9 en Windows por pasada); el board pasa en ambos sistemas. No esta fusionado a main.
Contratos: [cobertura de budgets](contracts/required-budget-coverage.md) y
[controles de producto](contracts/quality-required-controls.md).

Un requisito declarado obligatorio debe tener un mecanismo efectivo en su
alcance o bloquear. Un campo presente, un scan sin hallazgos o un exit cero
sin mediciones no bastan. La persona revisora decide que requisitos son
obligatorios antes de implementar y comprueba la cobertura de esa seleccion.
El codigo informa exactamente lo solicitado y observado, sin ampliar el claim.

## Politica aprobada

Agregar `required_controls` a la politica de [calidad](quality-approval.md).
Puede coexistir con `oracle_reviews` y `generated_task_evidence`.
Lista declarada vacia, IDs duplicados, claves desconocidas o rutas ambiguas
son CONTROL_POLICY. Cada entrada requerida toma el contrato y sus limites
desde el SHA aprobado; no permite sustituirlos por valores del candidato.

```json
{
  "id": "app-budget",
  "contract": "knowledge/contracts/app.md",
  "kind": "budget",
  "mechanism": "python-ast"
}
```

Para una prohibicion de runtime:

```json
{
  "id": "deny-network",
  "contract": "knowledge/contracts/app.md",
  "kind": "forbid",
  "capability": "network",
  "mechanism": "runtime"
}
```

Este segundo requisito **no tiene enforcement en este perfil**: debe bloquear
con CONTROL_UNSUPPORTED. No se sustituye por un scan textual ni por el campo
forbids. Un timeout, herramienta ausente o error de medicion tambien bloquean.
No se instala un motor automaticamente ni se degrada un Nivel 2 requerido.

La politica protege contrato y scripts/validate_budgets.py y
scripts/validate_contracts.py. El verificador comprueba el contrato completo
y extrae esos modulos desde blobs Git regulares aprobados, fuera del checkout.
No importa un medidor alterado del candidato. Helpers ejecutables adicionales
de otros checks conservan el inventario protegido definido por su revisor.

Los controles se ejecutan dos veces, antes de oracle_reviews y checks ordinarios
de cada pasada. Integridad y perimetro se recomprueban tras cada control incluso
si falla. No se puede desactivar un control declarado para obtener aprobacion. Los targets
medidos conservan la misma version a traves de controles, checks y ambas pasadas.
Un cambio observado despues de medir bloquea con CONTROL_CHANGED; no se emite
una aprobacion sobre una version final distinta de la medida. No se promete
rollback ni observar cambios hostiles transitorios entre comprobaciones.

## Medicion requerida de budgets

La API anterior validate_directory y su CLI conservan las omisiones historicas.
El nuevo modo `--required --json` y measure_required declaran cobertura real:

| Situacion | Resultado requerido |
| --- | --- |
| Selector sin contrato, o cero funciones | BUDGET_COVERAGE |
| Target ausente o no regular | BUDGET_TARGET |
| Lenguaje o metrica sin soporte | BUDGET_UNSUPPORTED |
| Fuente Python no parseable | BUDGET_PARSE |
| Exceso medido | Regla BUDGET_* correspondiente y valor observado |
| Fuente soportada dentro de todos los limites | PASS con mediciones, nunca cero cobertura |

Soporte inicial: funciones Python del modulo, incluidas las que seleccionan
los algoritmos AST existentes. Scope explicito: module-functions; no se afirma
el alcance de otro motor, lenguaje o definicion de complejidad. Las metricas
son cyclomatic_max, nesting_max, lines_max y params_max. Se observan nodos
FunctionDef y AsyncFunctionDef, incluidos metodos y funciones anidadas; no se
miden lambdas ni el coste de llamadas externas. Se conservan los algoritmos
AST previos, incluida su forma de contar ramas y anidamiento. Una key adicional
requerida, como memory_max, no se ignora. No se sube un limite para medir verde.

El reporte incluye schema_version, status, contracts_checked,
functions_measured y measurements con metodo, lenguaje, alcance, target,
hash, limites y funciones con sus metricas. target_sha256 identifica el texto
normalizado a LF, como las tareas; declarar hash_method=sha256-lf. Un resultado
fallido conserva las medidas que causaron el rechazo. Metricas estaticas no
miden memoria, latencia, aislamiento ni correccion semantica del producto.

## Evidencia de producto y compatibilidad

Cada linea REQUIRED_CONTROL contiene JSON con id, iteracion, aprobacion,
identidades de entradas, status, mecanismo, alcance, cobertura y resultados.
runner_sha256 identifica los bytes Git aprobados de cada modulo; los hashes
de target declaran LF normalizado y conservan tambien target_raw_sha256. Cada
proceso de medicion tiene un timeout fijo de 120 segundos; timeout/error bloquea.
AST y Git no aislan procesos: runtime_isolation=false. El auditor
audit_forbids conserva su API advisory y FORBID_UNVERIFIED informativo;
no se promueve a gate ni se modifica GATE_SPECS o el bundle historico de tareas.

La politica antigua que no declara required_controls conserva sus checks e
informa que no solicito esta garantia. No se deduce que sus campos budget,
deps_allowed o forbids estan efectivamente impuestos. Un perfil Nivel 2 puede
proporcionar garantias distintas solo mediante su ejecucion y evidencia reales.
La [integracion nativa](native-level2.md) conserva su fallo explicito ante
ausencia o capacidad no soportada, sin afirmar sandbox o firma de un humano.

La persona revisora decide limites, alcance, restricciones obligatorias y
riesgo aceptable. El codigo exige esa politica y registra el soporte observado;
un hash correcto o una metrica dentro de limites no deciden esas cuestiones.

Produccion autorizada: scripts/validate_budgets.py y scripts/verify_quality.py.
PARAR y presentar otra propuesta si hace falta otra fuente, oraculo anterior,
dependencia, elevar budgets o modificar workflows/protecciones. El baseline humano
y el CI dual-OS 2x de KG-3 se comprobaron antes de implementar. La verificacion
final de KG-4 completo su CI dual-OS 2x; las restricciones conservan el alcance y
las limitaciones descritas, sin afirmar aislamiento de runtime.
