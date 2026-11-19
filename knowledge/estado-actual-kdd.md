---
type: 'Concept'
title: 'Estado verificable de KDD y evidencia historica'
description: 'Estado verificado de main, historial de pruebas y limites de KDD.'
tags: ['kdd', 'reference', 'verification', 'tasks', 'bootstrap', 'ci', 'pages']
---

# Estado verificable de KDD

**KDD organiza el desarrollo mediante conocimiento enlazado, contratos y
oráculos aprobados, implementación delimitada y evidencia asociada a commits.**
Actualmente dispone de una plantilla inicializable, validadores, una CLI de
tareas y KDD-Board integrados con Git. El flujo se ha comprobado desde un
proyecto vacío hasta su calidad de producto en CI.

## Corte verificado del 11 de noviembre de 2026

El CI de main en `144168d` verificó 2.287 casos por pasada y el piloto de actualización del complemento quedó comprobado.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-verificado-del-11-de-noviembre-de-2026)

## Corte histórico del 8 de noviembre de 2026 en e9689aa

El PR #171 verificó 2.187 IDs en dos pasadas por sistema y documentó las garantías y límites de ese corte.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-histórico-del-8-de-noviembre-de-2026-en-e9689aa)

### Qué acredita cada resultado

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#qué-acredita-cada-resultado)

### Garantías integradas en los últimos dos PR

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#garantías-integradas-en-los-últimos-dos-pr)

### Evidencia del commit integrado

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#evidencia-del-commit-integrado)

### Hallazgos de la auditoría posterior

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#hallazgos-de-la-auditoría-posterior)

### Límites medidos

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#límites-medidos)

## Flujo ligero ODD integrado

El PR #172 verificó el flujo editorial ligero en ambos sistemas. [Protocolo vigente](odd-lightweight.md).

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#flujo-ligero-odd-integrado)

## Corrección de la referencia de aceptación

El PR #173 unificó la referencia de aceptación y la del baseline. [Contrato](contracts/acceptance-baseline-routing.md).

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corrección-de-la-referencia-de-aceptación)

## Corte histórico del 8 de noviembre de 2026 en 71630f0

El PR #170 incorporó la revisión proporcional del baseline. El CI verificó 2.168 IDs en dos pasadas por sistema.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-histórico-del-8-de-noviembre-de-2026-en-71630f0)

## Corte histórico del 6 de noviembre de 2026, 23:38 UTC

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-histórico-del-6-de-noviembre-de-2026-2338-utc)

### Capacidades integradas

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#capacidades-integradas)

### Pendientes registrados en este corte

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#pendientes-registrados-en-este-corte)

## Corte historico del 6 de noviembre de 2026, anterior a la publicacion de temporales

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-historico-del-6-de-noviembre-de-2026-anterior-a-la-publicacion-de-temporales)

### Lo aprendido del CI

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#lo-aprendido-del-ci)

### Pendientes para cerrar el objetivo

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#pendientes-para-cerrar-el-objetivo)

## Actualizacion posterior del 1 de noviembre de 2026

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#actualizacion-posterior-del-1-de-noviembre-de-2026)

## Corte verificado del 1 de noviembre de 2026

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-verificado-del-1-de-noviembre-de-2026)

## Corte verificado del 31 de octubre de 2026

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-verificado-del-31-de-octubre-de-2026)

## Corte historico del 29 de octubre de 2026

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-historico-del-29-de-octubre-de-2026)

## Corte historico del 28 de octubre de 2026

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-historico-del-28-de-octubre-de-2026)

## Corte historico del 24 de octubre

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#corte-historico-del-24-de-octubre)

## Componentes y responsabilidades

| Componente | Responsabilidad implementada | Referencia canónica |
| --- | --- | --- |
| Conocimiento OKF | Conservar contexto, decisiones y modelos en nodos Markdown enlazados. | [Especificación OKF](OKF-SPEC.md) |
| Task Contract y oráculo | Definir qué se implementa y cómo se comprueba; conservar la integridad de las pruebas mediante sello y referencia aprobada. | [Validación](validacion.md), [supervisión humana](supervision-humana.md) |
| Contratos de grupo | Componer y ejecutar contratos atomicos e integraciones bajo una referencia explicita; disponible en el main del corte actual. | [Grupos](group-contracts.md) |
| Contexto CCDD v0.3 | Validar, ensamblar y comparar contextos como perfil opt-in, integrado en main. No ejecuta proveedores dinamicos ni acredita firmas de quorum. | [Compatibilidad de contexto](context-v03-compat.md) |
| Task y diario Git | Registrar el avance operativo en nodos de `main`, con una rama de implementación por tarea e historial de transiciones validable. | [Modelo Task](data_models/git-task.md), [tareas con Git](git-tasks.md) |
| CLI y KDD-Board | Operar el mismo coordinador; leer tareas confirmadas de `main` y devolver el commit real de cada cambio de estado. | [CLI](contracts/task-cli.md), [integración del tablero](board-git.md) |
| Bootstrap | Adaptar la plantilla a la identidad del proyecto, retirar ejemplos e historial operativo heredado y preparar el CI de producto. | [Inicializador](contracts/init-project.md), [arranque guiado](contracts/bootstrap-project.md) |
| Política de calidad | Delimitar archivos protegidos y cambios permitidos; ejecutar checks estructurales, funcionales, adversariales y de interfaz según el producto. | [Aprobación de calidad](quality-approval.md) |
| Trazabilidad de requisitos | Consultar requisito, contrato, prueba, commit y evidencia, con verificaciones desde el historial Git. | [Trazabilidad](requirements-traceability.md) |
| Aceptacion y controles declarados | Comprobar obligaciones, oraculos, controles requeridos y procedencia segun la politica del producto. Su disponibilidad no acredita automaticamente una entrega. | [Aceptacion](acceptance.md), [controles requeridos](required-controls.md), [oraculos revisados](oracle-assurance.md) |
| CI | Ejecutar validación y tablero en Ubuntu/Windows, con runtime revisado fuera del checkout, dos pasadas completas y reportes por ID; exigir calidad de producto en proyectos inicializados. | [Calidad desde el arranque](bootstrap-product-quality-ci.md), [tiempo del CI](ci-runtime.md), [frontera de confianza](ci-audit-remediation.md) |
| Pages | Compilar el sitio real en PR de ambas plataformas y reconstruir al desplegar el SHA de main cuyo CI paso, con cotejo de inventarios de las cuatro pasadas y discovery estricto. | [Build en PR](pages-pr-validation.md), [inventario](pages-ci-inventory.md), [operacion](../site/README.md) |

El **ciclo del contrato** (`draft → validated → implemented → verified`) y el
**estado de la tarea** son dimensiones distintas. Una tarea lista para comenzar
necesita una referencia explícita del contrato aprobado; el cierre necesita
evidencia de ejecución sobre la implementación integrada. Las responsabilidades
de definición, ejecución y revisión se desarrollan en la
[metodología de ejecución](metodologia-ejecucion.md).

## Flujo operativo consolidado

1. **Preparar el proyecto.** Inicializar con su `OWNER/REPO`, definir conocimiento,
   contratos, oráculos y `quality/product.json` propios. El proyecto comienza
   sin las tareas de ejemplo TASK-001/TASK-002 ni sus evidencias heredadas.
2. **Revisar las referencias.** La persona revisora aprueba commits completos
   para los contratos y oráculos, y para la política de calidad del producto.
   El CI nativo selecciona `baseline_ref` y `quality_ref` del registro externo
   por árbol Git. Ambas referencias pueden apuntar al mismo commit revisado.
   [Registro de aprobaciones](approval-registry.md)
3. **Registrar y ejecutar la tarea.** CLI o tablero recorren
   `backlog → ready → in_progress → done`; el bloqueo admite
   `in_progress → needs_human_input → ready`. Cada transición crea un commit.
   La implementación se realiza en `task/TASK-NNN`.
4. **Integrar y cerrar.** El coordinador o la persona responsable integra la
   rama preservando sus commits. `finish` prueba el `main` limpio con el
   oráculo aprobado y crea después el commit de cierre con evidencia durable.
   El tablero no realiza el merge ni el push.
5. **Publicar y verificar.** El CI de la plantilla usa el runtime revisado
   para comprobar contratos y ejecutar dos pasadas del inventario. En un
   proyecto inicializado, el paso de calidad extrae su verificador de la
   referencia aprobada, comprueba integridad y perímetro, y ejecuta dos rondas
   de checks del producto. [Calidad desde el arranque](bootstrap-product-quality-ci.md)

El procedimiento y sus precondiciones completas viven en
[tareas con Git](git-tasks.md) y [calidad desde el arranque](bootstrap-product-quality-ci.md).
En el workflow generado, una política ausente o una referencia inválida produce
**FAIL**. El **PASS de calidad** requiere la ejecución satisfactoria del paso;
la ausencia de configuración no se acepta como SKIP satisfactorio.
El repositorio plantilla conserva su configuración opcional de ejemplos;
la obligatoriedad de `quality/product.json` corresponde a los proyectos inicializados.

## Evidencia historica de un proyecto nuevo

El piloto recorrió una tarea desde KDD-Board y verificó los nueve commits de la tarea y la calidad del producto.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#evidencia-historica-de-un-proyecto-nuevo)

## Varias tareas y dependencias comprobadas

El piloto recorrió cuatro tareas dependientes desde KDD-Board y comprobó sus 28 commits originales y el CI de producto.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#varias-tareas-y-dependencias-comprobadas)

## Mejoras integradas y rendimiento medido

El archivo conserva la comparación del PR #123 y el historial de cambios del CI entre los PR #122 y #127.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#mejoras-integradas-y-rendimiento-medido)

## Correccion del contador de Pages en el corte historico

La evidencia histórica registra la adopción del inventario real del CI y su comprobación en Pages.

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#correccion-del-contador-de-pages-en-el-corte-historico)

## Alcance de las garantías y trabajo pendiente

Las capacidades y sus límites se detallan en [garantías verificables](verification-guarantees.md).

[Evidencia de este corte](../docs/reports/ARCHIVO-ESTADO-KDD.md#alcance-de-las-garantías-y-trabajo-pendiente)
