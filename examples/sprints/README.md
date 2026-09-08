# Probar admision y planificacion

Desde la raiz de KDD, Python 3.11+ y biblioteca estandar:

```sh
python -m src.sprint_planner examples/sprints/backlog.json
python -m unittest tests.test_sprint_planner tests.test_sprint_admission
```

El ejemplo devuelve `executable: ["schema", "docs"]` y `next_task: "schema"`:
schema hereda prioridad urgent de integration. La tarea docs tiene prioridad high,
pero su relacion related_to con integration no la bloquea ni le transfiere prioridad.
integration sigue pendiente de credentials y schema; el reporte identifica el bloqueo
access, su responsable project-owner y su condicion de salida. cycle-a y cycle-b
forman un ciclo sin detener el trabajo independiente.

Para probar la reactivacion en una copia del JSON: resolver el bloqueo de credentials
(`status: "resolved"` dentro de blockers), marcar credentials y schema `done`, asignar
a cada una `evidence: {"valid": true, "reference": "report@revision"}` y actualizar
el consumo real. Volver a ejecutar: integration pasa a ser candidata si cabe en el
presupuesto. Invalidar despues evidencia de schema vuelve a impedir integration.
Los valores del ejemplo son sinteticos; no contienen credenciales ni consumo real.

## Contrato de la salida

- `executable`: alternativas ordenadas frente al mismo saldo. No lanzarlas en lote.
- `next_task`: primera alternativa; actualizar snapshot tras cada ejecucion.
- `tasks`: razon de elegibilidad o rechazo, causas originales, prioridad y dependencias
  a observar en recheck_on, incluidas las completadas cuya evidencia puede invalidarse.
- `cycles`: componentes ciclicos con IDs ordenados, no caminos inventados.
- `errors`: problemas de formato o referencias inexistentes; ninguna tarea se admite
  si el snapshot es invalido.

Exit 0: hay candidata; exit 1: snapshot valido sin candidata; exit 2: entrada invalida.
Recalcular ante cualquier cambio del backlog, seleccion, estado de sprint o presupuesto.
recheck_on explica dependencias de elegibilidad; un cambio en la prioridad de un
descendiente tambien puede afectar el orden y exige recalcular aunque no figure ahi.
No hay sondeo, servicio de eventos, reserva atomica, verificacion de evidencia en disco
ni integracion al tablero. El coordinador proporciona un snapshot confiable.
Formato completo: `knowledge/data_models/sprint-backlog.md`.

La admision individual anterior sigue disponible:

```sh
python -m src.sprint_admission examples/sprints/admit.json
python -m src.sprint_admission examples/sprints/reject-selection.json
python -m src.sprint_admission examples/sprints/reject-dependency.json
python -m src.sprint_admission examples/sprints/reject-budget.json
```

Esperado: exit 0 para admit; exit 1 para los tres rechazos con su codigo especifico.
