---
type: 'Concept'
title: 'Estado verificable de KDD al 23 de octubre de 2026'
description: 'Corte de alcance implementado, flujo operativo, evidencia real y limites de la metodologia y sus herramientas.'
tags: ['kdd', 'reference', 'verification', 'tasks', 'bootstrap']
---

# Estado verificable de KDD

**KDD organiza el desarrollo mediante conocimiento enlazado, contratos y
oráculos aprobados, implementación delimitada y evidencia asociada a commits.**
Actualmente dispone de una plantilla inicializable, validadores, una CLI de
tareas y KDD-Board integrados con Git. El flujo se ha comprobado desde un
proyecto vacío hasta su calidad de producto en CI.

Este corte, fechado el **23 de octubre de 2026, America/Mexico_City**, describe
capacidades observadas. Las reglas normativas siguen en los nodos enlazados.
La revisión de código fuente examinada es
[`7886578b`](https://github.com/MauricioPerera/KDD/commit/7886578b8e4ce9f107851a4d7873ac9ab880dec8),
que incorpora el PR #120. Este documento es posterior a esa revisión.

## Componentes y responsabilidades

| Componente | Responsabilidad implementada | Referencia canónica |
| --- | --- | --- |
| Conocimiento OKF | Conservar contexto, decisiones y modelos en nodos Markdown enlazados. | [Especificación OKF](OKF-SPEC.md) |
| Task Contract y oráculo | Definir qué se implementa y cómo se comprueba; conservar la integridad de las pruebas mediante sello y referencia aprobada. | [Validación](validacion.md), [supervisión humana](supervision-humana.md) |
| Task y diario Git | Registrar el avance operativo en nodos de `main`, con una rama de implementación por tarea e historial de transiciones validable. | [Modelo Task](data_models/git-task.md), [tareas con Git](git-tasks.md) |
| CLI y KDD-Board | Operar el mismo coordinador; leer tareas confirmadas de `main` y devolver el commit real de cada cambio de estado. | [CLI](contracts/task-cli.md), [integración del tablero](board-git.md) |
| Bootstrap | Adaptar la plantilla a la identidad del proyecto, retirar ejemplos e historial operativo heredado y preparar el CI de producto. | [Inicializador](contracts/init-project.md), [arranque guiado](contracts/bootstrap-project.md) |
| Política de calidad | Delimitar archivos protegidos y cambios permitidos; ejecutar checks estructurales, funcionales, adversariales y de interfaz según el producto. | [Aprobación de calidad](quality-approval.md) |
| CI | Ejecutar validación y tablero en Ubuntu/Windows, conservar dos pasadas de la suite y exigir calidad de producto en proyectos inicializados. | [Calidad desde el arranque](bootstrap-product-quality-ci.md), [optimización de CI](contracts/ci-execution-deduplication.md) |

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
2. **Revisar las referencias.** La persona revisora aprueba commits completos.
   `KDD_APPROVED_BASELINE_REF` controla contratos/oráculos y
   `KDD_QUALITY_APPROVED_REF` controla la política y sus archivos protegidos.
   Pueden coincidir; el bootstrap no selecciona ni aprueba esas referencias.
3. **Registrar y ejecutar la tarea.** CLI o tablero recorren
   `backlog → ready → in_progress → done`; el bloqueo admite
   `in_progress → needs_human_input → ready`. Cada transición crea un commit.
   La implementación se realiza en `task/TASK-NNN`.
4. **Integrar y cerrar.** El coordinador o la persona responsable integra la
   rama preservando sus commits. `finish` prueba el `main` limpio con el
   oráculo aprobado y crea después el commit de cierre con evidencia durable.
   El tablero no realiza el merge ni el push.
5. **Publicar y verificar.** El flujo autorizado del repositorio publica el
   historial. El CI comprueba el checkout actual con un runner de calidad
   extraído del commit aprobado a un temporal externo; valida integridad y
   perímetro y ejecuta los checks dos veces.

El procedimiento y sus precondiciones completas viven en
[tareas con Git](git-tasks.md) y [calidad desde el arranque](bootstrap-product-quality-ci.md).
En el workflow generado, una política ausente o una referencia inválida produce
**FAIL**. El **PASS de calidad** requiere la ejecución satisfactoria del paso;
la ausencia de configuración no se acepta como SKIP satisfactorio.
El repositorio plantilla conserva su configuración opcional de ejemplos;
la obligatoriedad de `quality/product.json` corresponde a los proyectos inicializados.

## Evidencia de un proyecto nuevo

La demostración pública
[kdd-bootstrap-e2e-20261023](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023)
se creó exportando la revisión indicada de KDD, sin copiar su historial Git.
Se inicializó con identidad propia, se abrió KDD-Board vacío y se implementó
un normalizador de títulos con CLI. El stub fue rechazado antes de implementar.
Los siete cambios de estado se realizaron desde el tablero.

| Operación de TASK-001 | Commit original conservado |
| --- | --- |
| Crear: `backlog` | [`2157f49b`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/2157f49b0b0fb14609ddd8330ae3ea99e71273a9) |
| Aprobar: `ready` | [`4a62c465`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/4a62c465b6c605d810baf48ab3a1e7d4c4907793) |
| Iniciar: `in_progress` | [`800b8f03`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/800b8f036402413853e130174608bfc2c8235baa) |
| Bloquear: `needs_human_input` | [`cbd011e8`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/cbd011e83cda6b3448c230b9e663498a78cb259e) |
| Reanudar: `ready` | [`0e4198f8`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/0e4198f8ac00c446dc4b64795c1679b64f58771c) |
| Reiniciar: `in_progress` | [`dde4a4c4`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/dde4a4c41d664d74e6863335efe231c34b2bad18) |
| Implementar en la rama de tarea | [`c9a24bb2`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/c9a24bb2c25ea908665e0923804ea18bb36c8e1c) |
| Integrar conservando la implementación | [`ec672b8f`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/ec672b8f5793c854108b359fdc7330351532355f) |
| Cerrar: `done` | [`27f560ea`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/27f560ea18710c2b3017ccd8b743e328427328fd) |

El cierre conserva **21 pruebas** y la referencia histórica aprobada
`36efe59798f15579bca495da40f864302c890cb2`. Su
[evidencia versionada](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/blob/27f560ea18710c2b3017ccd8b743e328427328fd/docs/task-evidence/TASK-001-ec672b8f5793c854108b359fdc7330351532355f.json)
identifica el merge probado `ec672b8f`, el oráculo, el target y el resultado.
Un intento previo de cerrar sin implementación integrada fue rechazado sin
crear un commit de cierre.

El [primer CI](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/actions/runs/40056782873)
detectó un error real del oráculo en Windows: decodificaba salida UTF-8 con el
locale CP1252. Se añadió una regresión que fallaba antes del arreglo y se hizo
explícita la decodificación, conservando las aserciones anteriores. La persona
revisora aprobó después
[`4636c9e9`](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/commit/4636c9e9ff7ec62069760d5c9b2af7838de706ae)
para ambas variables de CI. Ese cambio pertenece a la demo; el bootstrap de
KDD mantiene la revisión fuente indicada al inicio.

| Verificación final de la demo | Resultado observado |
| --- | --- |
| CI de `4636c9e9` | [Run 40058077407](https://github.com/MauricioPerera/kdd-bootstrap-e2e-20261023/actions/runs/40058077407): cuatro jobs en `success`. |
| Calidad de producto por SO | `quality/product.json`: **PASS**, 9 pruebas funcionales + 8 adversariales + 5 de CLI, dos rondas, sin omisiones de producto. |
| Suite general por SO | 993 casos enumerados en cada una de dos pasadas; 47 omisiones en Ubuntu y 46 en Windows. |
| Política y workflow | 68 rutas protegidas existentes; workflow generado conservado sin edición manual. |
| Historial | Los nueve commits de la tarea permanecen como ancestros; la evidencia histórica de 21 pruebas sigue intacta. |

Las **22 pruebas actuales** corresponden al oráculo corregido del CI; el cierre
histórico mantiene sus **21 pruebas** originales. El PASS de producto no elimina
los SKIP de otras capas opcionales, como seguridad sin hallazgos aportados.
La revisión fuente de KDD también tiene
[CI satisfactorio](https://github.com/MauricioPerera/KDD/actions/runs/40052262735)
con los cuatro jobs Ubuntu/Windows y 66 contratos. El conjunto de Nivel 1
mantiene 19 gates; los controles del diario de tareas son adicionales. El
preflight local incluye un control de atestación más y muestra 20 comprobaciones.

## Optimización de CI comprobada

Se agrupan comandos de contratos exactamente iguales dentro de una invocación,
se evita el doble disparo por push de rama y PR y se cancelan ejecuciones
nativas superadas del mismo PR. Se conservan los cuatro jobs, Ubuntu/Windows
y las dos pasadas de la suite. La ejecución post-inicialización costosa ya
corría en su contrato y conserva esa ubicación.

La comparación alojada entre
[PR #118](https://github.com/MauricioPerera/KDD/actions/runs/39994660939) y
[PR #119](https://github.com/MauricioPerera/KDD/actions/runs/40008201182)
registró estos tiempos de job, excluyendo espera en cola:

| Job | Antes | Después |
| --- | ---: | ---: |
| validate Ubuntu | 130 s | 120 s |
| validate Windows | 1373 s | 1304 s |
| board Ubuntu | 17 s | 14 s |
| board Windows | 71 s | 109 s |

Son muestras de máquinas distintas. La variación de Board Windows ilustra por
qué estos tiempos no permiten atribuir un porcentaje global de ahorro a la
optimización. El [contrato de CI](contracts/ci-execution-deduplication.md)
delimita la agrupación y prohíbe reutilizar evidencia entre commits, SO o pasadas.

## Alcance de las garantías y trabajo pendiente

- **Integridad y adecuación.** El sello y la referencia detectan alteraciones;
  la fuerza del oráculo y la corrección de los requisitos requieren revisión.
  El cierre certifica el SHA probado con su oráculo, no revisiones futuras.
- **Confianza.** Git, el runner y las variables de aprobación necesitan control
  externo. Un SHA explícito no autentica por sí solo la decisión humana. Las
  protecciones de GitHub se configuran en cada repositorio nuevo.
- **Operación local.** Board usa localhost y token; el coordinador tiene lock
  local. La coordinación distribuida y el acceso multiusuario siguen pendientes.
- **Nivel 2 y dominios opcionales.** Los perfiles nativo/MCP y las capas de
  seguridad, privacidad, accesibilidad y otros dominios tienen mecanismos propios.
  Esta demo no constituye una validación integral de esas capacidades.
- **Arranque remoto.** Variables, protecciones y disponibilidad de Actions son
  configuración externa. La demo requirió habilitar Actions desde GitHub; el
  bootstrap no automatiza esa administración.
- **Próxima validación de uso.** El flujo demostrado cubre un producto CLI pequeño.
  Un piloto con varias tareas, dependencias, colaboradores y requisitos de interfaz
  permitiría medir esfuerzo, concurrencia y coste de revisión en un contexto mayor.

Los límites técnicos completos se mantienen en
[garantías verificables](verification-guarantees.md). Las mejoras pendientes
anteriores son una orientación de evolución; su implementación necesitará
contratos y evidencia propios.
