# Piloto de relevo de revisión en KDD-Board

El [PR #218](https://github.com/MauricioPerera/KDD/pull/218) incorporó una vista
de solo lectura para recuperar la revisión de un candidato desde el ID de su
tarea. Quedó integrado el 24 de noviembre de 2026 en
`7c8d3b9529e311657ba7bab00d85f7a99dc93f98`, con el baseline aprobado
`1edb5f7e936ccdf0b563056dbc0ef1f7a3874615` y la implementación
`449bdbc8ab15ae44d87d39aa24bea69b747b713e`.

## Qué tomamos de HumanLayer

- **La tarea sobrevive a la sesión.** HumanLayer permite varias sesiones por
  tarea. En KDD, un agente nuevo puede abrir el mismo `TASK-ID` y recuperar
  el candidato y su revisión desde el detalle de Board. [Tareas en HumanLayer](https://github.com/humanlayer/humanlayer/blob/fb899cd8cba767f0392708efc20d00938dec6a87/apps/docs/explanation/tasks.md#L46)
- **La revisión pertenece a una versión.** HumanLayer vincula comentarios a
  la versión del artefacto revisado y marca los anclajes que quedaron
  desactualizados. Board conserva el dictamen por SHA y muestra las versiones
  anteriores al seleccionar otro candidato. [Versionado](https://github.com/humanlayer/humanlayer/blob/fb899cd8cba767f0392708efc20d00938dec6a87/packages/db/src/tables/artifact-comments.ts#L85) · [Anclajes desactualizados](https://github.com/humanlayer/humanlayer/blob/fb899cd8cba767f0392708efc20d00938dec6a87/packages/ui/src/artifact-viewer-v2/anchor/resolve.ts#L76)
- **La decisión humana queda visible.** HumanLayer registra el estado y el
  responsable de cada permiso. Board muestra si la revisión puede pasar a
  decisión humana. `review_status` proviene del verificador v1 y
  `approved_ref` proviene del diario Git en `main`. [Registro de decisiones de HumanLayer](https://github.com/humanlayer/humanlayer/blob/fb899cd8cba767f0392708efc20d00938dec6a87/packages/db/src/tables/approvals.ts#L13) · [Aprobación del baseline en KDD](../../knowledge/quality-approval.md)

El operador prepara `selection.json` y el v1 original en
`.agents/logs/board-reviews/TASK-ID/` del proyecto. **Consultar revisión**
lee esos archivos bajo demanda y revalida el registro contra los objetos
Git locales. Cada entrada muestra el candidato, su árbol, la huella SHA-256
del v1 y el estado de revisión. La consulta autenticada sirve para el relevo
entre sesiones y el diario conserva la autoridad sobre la tarea.
[Guía de Board](../../knowledge/board-git.md#retomar-una-revision) ·
[Contrato del relevo](../../knowledge/contracts/board-review-handoff.md)

## Qué verificamos con TASK-990

Se creó `TASK-990` con el coordinador de tareas en un clon aislado y se usó el
v1 genuino del [piloto de Codex VPS](CODEX-VPS-BASELINE-PILOT.md#evidencia-de-a7e1c84).

| Dato | Valor |
| --- | --- |
| Base | `00e1af78c298e0d8f960040cdb7727c5c091640f` |
| Candidato revisado | `a7e1c849ea63631a3c9ec030d7ec122fd0472089` |
| Árbol | `34d947355e014e54f95318d132b1a6335889b38f` |
| SHA-256 de los bytes del v1 | `42121afad4b912d580661e6bf51939a5d5129bb4ffd6b8c5fc93e1385e84d8ca` |
| Candidato posterior con el mismo árbol | `337b98dfbc5e382bdc64a92022d33a4776614790` |

1. **Reinicio de Board.** Dos procesos distintos devolvieron la misma base,
   candidato, árbol y huella. El v1 quedó en `ready` y el diario devolvió
   `approved_ref: null`. La decisión humana seguía pendiente.
2. **Relevo con contexto fresco.** Un agente recibió el ID y las rutas de la
   aplicación y del clon. Recuperó el dictamen mediante el GET real, identificó
   la decisión pendiente y obtuvo HTTP 401 al omitir el token.
3. **Cambio del candidato.** Al seleccionar `337b98d`, Board devolvió
   `missing` para el nuevo SHA y conservó `a7e1c84` en el historial con su
   huella original. El índice, las referencias y el v1 conservaron sus bytes
   mientras se leía el estado. El operador restauró la selección inicial.
4. **Navegador y compatibilidad.** Chrome mostró la huella y el aviso de
   aprobación pendiente, y mantuvo ambos tras el refresco normal. El agente
   detectó un primer HTTP 409 con Python 3.14 en Windows. Después del ajuste
   que compara `ctime` dentro de cada fuente, Python 3.11 y 3.14 devolvieron
   el mismo resultado autenticado.

El ensayo reutilizó un v1 ya producido. Los IDs y la huella permiten cotejar
el expediente con el informe original. Los recibos del ensayo se conservan
en el registro local del piloto. Las [11 integraciones](../../tools/kdd-board/tests/review-handoff.test.ts)
cubren además la copia de un v1 bajo otro SHA, los objetos locales ausentes,
los enlaces y la autoridad del diario frente a un checkout divergente.

## Evidencia después de la fusión

El [CI de main](https://github.com/MauricioPerera/KDD/actions/runs/45494428538/attempts/1)
verificó las dos pasadas por sistema con el mismo inventario de 2.736 IDs y
cobertura en la primera. El post-init de Windows terminó en **341 s** de
ventana común. Board pasó **107/107** en ambos sistemas.

| Sistema | Pasadas | SKIP por pasada | Cobertura de líneas / ramas en la primera |
| --- | ---: | ---: | --- |
| Ubuntu | 2/2 | 10 | 75,12 % / 68,81 % |
| Windows | 2/2 | 11 | 77,22 % / 70,15 % |

El [despliegue de Pages](https://github.com/MauricioPerera/KDD/actions/runs/45500785947/attempts/1)
usó los inventarios de ese mismo CI. La [portada](https://mauricioperera.github.io/KDD/)
enlazó a esa ejecución y la [guía pública de Board](https://mauricioperera.github.io/KDD/knowledge/board-git.md)
coincidió byte por byte con la guía del merge. El preview local dejó 463 bytes
de margen en el índice de conocimiento. Este informe vive en `docs/reports/`
para que el relato del piloto se consulte por enlace.

## Qué sigue pendiente

1. **Repetir el relevo en una revisión nueva.** Verificar el flujo completo
   desde que el VPS produce otro v1 hasta que un agente distinto abre Board
   y el responsable toma la decisión sobre el SHA. En `TASK-990` se comprobó
   el relevo de la consulta con un v1 existente.
2. **Preparar la selección y el recibo desde el flujo de revisión.** La
   asociación entre la tarea, el candidato y el archivo v1 se prepara a mano.
   Queda por comprobar una entrega reproducible a Board desde el
   [flujo de Codex VPS](CODEX-VPS-BASELINE-AUTOMATION.md), con el mismo SHA y
   huella al repetir la preparación.
3. **Demostrar una reutilización explícita sobre otro candidato.** El caso de
   igual árbol probó que el dictamen anterior sigue visible y el SHA nuevo
   queda pendiente. Falta ensayar un v1 válido ligado al SHA nuevo, con la
   procedencia de la revisión reutilizada y la decisión humana trazable.
