---
type: 'Architecture'
title: 'Trazabilidad de requisitos con evidencia Git'
description: 'Relacionar requisitos, contratos, oraculos, tareas y evidencia sin inventar cobertura ni actualizar estados.'
tags: ['requirements', 'traceability', 'git', 'quality']
---

# Resultado y alcance

La [especificacion breve](traceability-product-spec.md) define esta entrega.
El [modelo](data_models/requirement-trace.md) describe los artefactos de entrada
y el reporte. Se reutilizan las [tareas Git](git-tasks.md) y su evidencia;
no se crea un segundo diario ni se modifica el formato Task v1.

Los contratos son [modelo](contracts/traceability-model.md),
[proyeccion Git](contracts/traceability-git.md) y
[CLI e integracion de calidad](contracts/traceability-cli.md).

## Unidad de trazabilidad

Una especificacion de producto breve contiene IDs REQ-NNN estables y texto
observable. Un manifiesto optativo vincula cada ID con contratos y tareas.
El enlace requisito/contrato es una decision humana explicita; el verificador
deriva oraculo, target, aprobacion, commit probado y evidencia desde Git.
No deduce relaciones semanticas por nombres, embeddings o salida de un LLM.

Un requisito puede necesitar varios contratos y tareas. Todos sus enlaces
deben estar verificados para considerarlo completo. Un mismo contrato puede
servir a varios requisitos. Una tarea solo puede tener su contrato canonico.
Las tareas futuras pueden declararse antes de crearlas; se muestran pendientes.
No basta con encontrar el nombre de un test o con declarar un estado a mano.

## Referencias y aprobacion

Se resuelve --ref una sola vez a un commit; el default es main. Es una revision
observada, no una aprobacion implicita de HEAD. Se leen blobs regulares de ese
commit, incluso desde otra rama o con cambios locales. No se ejecutan pruebas
ni codigo del producto, no se escribe un reporte al disco automaticamente y
no hay checkout, commit, fetch, push o cambios de estado.

Para cada tarea aprobada se compara la huella del requisito con la de su
approved_ref: ruta del spec, ID, texto y conjunto completo de enlaces propios.
El orden del JSON no cambia la huella. Agregar un requisito ajeno no invalida
los anteriores; cambiar texto o enlaces del mismo requisito requiere nueva
aprobacion y evidencia mediante una tarea nueva. Task v1 no se reabre ni se
reescribe retroactivamente para acomodar requisitos nuevos.

El contrato y el oraculo conservan sus comprobaciones canonicas de aprobacion.
Una evidencia done conserva su significado historico. Solo se muestra vigente
para el alcance observado si contrato, target y oraculo actuales siguen siendo
iguales a sus blobs probados, normalizando LF como el coordinador existente.

## Diario y evidencia

Se reutilizan validate_snapshot y validate_range, sin volver a implementar las
reglas de transicion o aceptar un JSON de evidencia desconectado de la tarea.
La base de auditoria se deriva de los branch_base de las tareas enlazadas: el
snapshot de cada inicio debe mostrar esa tarea ready, sin branch_base fijado,
con el mismo contrato y approved_ref. Se audita desde la base mas antigua que
cubre esos inicios en la primera linea de padres de la revision observada.
Si un inicio llego por un merge de diario, se incluye ese merge y se deja al
validador canonico auditar su origen. Una base fuera de primera linea no se
acepta como atajo para saltar transiciones. Sin inicios se valida el snapshot.

Esto permite historiales de proyecto ya existentes sin reinterpretar todas sus
migraciones previas. El reporte identifica audit_base y observed_commit; no
afirma haber auditado un tramo anterior. Historia insuficiente, evidencia
alterada, un salto intermedio o un import que reescribe el diario hacen fallar
la comprobacion. No se sustituye una comprobacion fallida por un simple hash.

## Estados y salida

El reporte JSON v1 separa ok (validacion solicitada) de complete
(todos los requisitos vigentes y verificados). Distingue pending, verified y
stale. Un proyecto pendiente puede tener ok=true y complete=false. Un enlace
invalido o desfasado tiene ok=false y nunca pasa como cobertura vigente.
--require-verified exige tambien complete=true para habilitar el cierre.
En ese modo un pendiente produce ok=false y TRACE_PENDING. Un error de entrada
produce un reporte con TRACE_INPUT, TRACE_SCHEMA, TRACE_SPEC o TRACE_GIT;
la API no requiere interpretar excepciones para decidir el resultado.

La matriz Markdown deriva del mismo reporte. Contiene ID, contrato, oraculo,
tarea, commit probado, evidencia y estado; no crea una segunda fuente de verdad.
Las rutas/identidades se validan antes de imprimirlas y los campos se escapan.
Un manifiesto ausente o vacio es un error explicito al invocar la herramienta,
no un SKIP ni una aprobacion. La herramienta no se activa globalmente por glob.

## Integracion y compatibilidad

Un proyecto opta por un manifiesto, normalmente quality/traceability.json, y un
check obligatorio dentro de [quality/product.json](quality-approval.md).
La receta exacta esta en examples/traceability/README.md. Se protegen el spec,
manifiesto, los tres modulos nuevos y los cinco validadores canonicos de tareas;
se conservan los checks funcionales/adversariales propios del producto.
El verificador de calidad existente ejecuta ese comando dos veces con el resto.

No se agrega un gate global ni se cambia workflow, runtime revisado, autoridad
del tablero o proteccion remota. Siguen siendo 19 gates, Ubuntu/Windows y dos
pasadas. No se inventa una migracion de todos los contratos historicos de KDD
ni se atribuye cobertura a ejemplos sin tareas propias verificadas.

## Limites de confianza

La huella preserva la identidad declarada; no prueba que una asercion compruebe
la intencion del requisito. La evidencia cubre contrato/target/oraculo y el
requisito enlazado, no todas las dependencias transitivas o servicios externos.
No se afirma que se hayan vuelto a ejecutar pruebas en observed_commit.
No se autentica al humano ni al productor de la evidencia. Se hereda la base
de confianza del coordinador, los validadores y la politica protegida.
No se consulta GitHub ni se inventa un estado de CI a partir de una URL.

Contratos y oraculos se revisan primero segun [quality-approval](quality-approval.md).
PARAR y reportar si se necesita cambiar un oraculo anterior, el diario canonico,
el runtime, los workflows o las protecciones para completar esta entrega.
