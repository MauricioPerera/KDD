# Contrato 34 - Cerrar las brechas de gobierno de KDD

Prerrequisitos: main 36b69a03101181160a3299549c2d173b657ade97; la
[auditoria y el objetivo](../knowledge/kdd-governance-closure.md) definen el
alcance y separan el control mecanico de la revision humana.

## KG-1 - Perimetro obligatorio de cierre e historial

FIX/OBJETIVO: una tarea solo puede quedar done cuando sus cambios y su
integracion respetan el contrato aprobado. La validacion historica debe
rechazar el mismo incumplimiento y no confiar en un recibo autoafirmado.
Contratos: [cierre](../knowledge/contracts/task-finish-perimeter.md) e
[historial](../knowledge/contracts/task-perimeter-history.md).

## KG-2 - Matriz de controles por operacion

FIX/OBJETIVO: ready, start, finish y aprobacion de producto tienen controles,
autoridad, evidencia y condiciones de aplicacion explicitas. Contratos y
oraculos propios se presentan a revision antes de implementar esta entrega.

## KG-3 - Fuerza de oraculos

FIX/OBJETIVO: exigir los controles estructurales aplicables y las contramuestras
revisadas del riesgo declarado, sin presentar etiquetas como prueba semantica.

## KG-4 - Restricciones y limites comprobables

FIX/OBJETIVO: los requisitos obligatorios sin mecanismo efectivo bloquean la
aprobacion; cada resultado declara el soporte y alcance realmente observados.

## KG-5 - Contexto y aprendizaje verificables

FIX/OBJETIVO: contexto y decisiones tienen identidades y relaciones auditables;
la coherencia del conocimiento y la pertinencia de reglas siguen en revision.

## Criterios de aceptación

- [x] [AC-1] `python -m unittest tests.test_task_finish_perimeter` exit 0; un cambio
  ajeno se rechaza antes del oraculo sin commit de cierre, con Git real.
- [x] [AC-2] `python -m unittest tests.test_task_perimeter_history` exit 0; se rechazan
  cierres ajenos aun con recibos omitidos o falsificados, y se preservan los validos.
- [x] [AC-3] `python scripts/validate_contracts.py knowledge/contracts` y
  `python scripts/validate_okf.py knowledge` exit 0, con nuevos sellos y enlaces.
- [x] [AC-4] Cada criterio KG-2 a KG-5 tiene contratos, oraculos aprobados y comando
  real exitoso antes de marcar esta casilla; definir el plan no satisface el criterio.
- [x] [AC-5] `python scripts/validate_budgets.py knowledge/contracts --contract task-git-complexity`
  exit 0; conservar oraculos anteriores, firmas, presupuestos y fronteras vigentes.
- [x] [CI-1] CI del candidato en Ubuntu/Windows con dos pasadas completas, controles
  existentes, evidencia por criterio y sin sustitucion de omisiones por PASS.

## Restricciones

- Tocar SOLO las rutas de los contratos aprobados de cada entrega. Las fuentes de
  esta primera entrega son scripts/task_git.py, scripts/task_evidence.py y
  scripts/validate_tasks.py. Contratos, oraculos y documentacion pertenecen al PM.
- No modificar pruebas anteriores, Task v1, helpers confiables, workflows ni
  protecciones sin presentar una nueva propuesta concreta a revision.
- ABORTAR SI falta la aprobacion del baseline; un caso exige ampliar permisos
  sin revision; la atribucion Git es ambigua; o cumplir un criterio exige
  debilitar otro. Conservar el estado y reportar la evidencia, sin forzar PASS.

## Checklist antes de delegar

- [x] RECON de los comandos y contratos relevantes ejecutado y conservado.
- [x] Oraculos nuevos sellados, fase roja y controles positivos conservados.
- [x] Baseline concreto revisado por una persona antes de implementar.
- [x] Perimetros y condiciones de aborto fijados por contrato.
- [x] Contexto y restricciones proporcionados con identidades auditables.
