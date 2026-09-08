# SPRINT-02 — Ordenar trabajo ejecutable y explicar impedimentos

Estado: closed. Frente: planificacion KDD. Autorizacion: "implementemoslo".
Coordinador e implementador: asistente; revision propia, sin subagentes.
Resultado: CLI que recibe backlog relacionado, ordena alternativas ejecutables y
explica bloqueos transitivos, ciclos y prioridad heredada usando admision existente.

## Seleccion y presupuesto

Una tarea de implementacion: sprint-planner. Previamente: modelo y oraculo independiente
del codigo; despues: pruebas focales, regresion y validadores. WIP 1.
Tokens y coste unknown. Limite operativo: dos correcciones sin evidencia nueva;
investigacion solo para fallos concretos. Reserva de verificacion: suite y CLI real.
No tablero, persistencia, eventos externos ni publicacion remota en este sprint.

## Criterios de aceptación

- [x] `python -m unittest tests.test_sprint_planner` pasa, con negativos y cambios de estado.
- [x] `python -m src.sprint_planner examples/sprints/backlog.json` propone el prerrequisito
  de una entrega critica y explica la causa original de la entrega bloqueada.
- [x] `python scripts/preflight.py` sin fallos; skips opcionales identificados.
- [x] `python -m unittest discover -s tests` sin regresiones.

## Restricciones

- Tocar SOLO nuevos src/sprint_planner.py, src/sprint_graph.py, su oraculo y modelo,
  contrato, ejemplo, guia y referencias del indice/protocolo. Admision existente intacta.
- ABORTAR SI requiere alterar tests congelados existentes, ejecutar agentes o cambiar
  estado del tablero. Hallazgos fuera del objetivo vuelven al backlog.

## Cierre

Resultado tecnico: achieved. 24 tests nuevos pasan; 35 junto al validador anterior.
Suite completa: 806 tests en 88.183 segundos, OK. Preflight exit 0, 18/19; seguridad
SKIP por evidencia opcional ausente. CLI propone schema antes que docs y explica
credentials como origen del bloqueo manual; reporta cycle-a/cycle-b por separado.
Comparacion adicional del algoritmo de ciclos contra cierre transitivo: 530 grafos OK.
Cadena de 1100 tareas cubierta por el oraculo. Paquete extraido: 35 tests OK.

Oraculo congelado SHA256 normalizado:
06cb37922e387ac0a91036cdc80725e864f8b3c751920837e781112383ff8038.
Sin cambios al oraculo ni al validador anterior. Una implementacion, sin correcciones
de codigo por fallos. Aclaracion documental en revision: recheck_on cubre elegibilidad;
los cambios de prioridad de descendientes tambien requieren recalcular el plan.
Evidencia local: .agents/logs/sprint-planner-REPORT.md. Revision propia, sin independencia.
No se ejecuto CI remoto ni Nivel 2, ni se publico este sprint. Tokens/coste unknown.
Pruebas de bloqueo son sobre snapshots confiados; no acreditan ahorro.

Backlog posterior: conectar a cambios de estado reales y admision atomica en el
despachador; integrar relaciones al tablero; medir resultados de entregas comparables.
Ninguna de esas tareas se inicio como ampliacion silenciosa de este sprint.
