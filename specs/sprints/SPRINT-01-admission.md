# SPRINT-01 — Admitir o rechazar una tarea con evidencia ejecutable

Estado: closed. Responsable/coordinador/revisor tecnico: asistente de esta conversacion;
sin revision independiente. Usuario autoriza implementacion con "adelante".
Resultado: funcion y CLI que admiten un caso valido y rechazan sprint inactivo,
tarea ajena, dependencias pendientes y presupuesto insuficiente.

## Seleccion y admision

Una sola tarea activa: [sprint-admission](../../knowledge/contracts/sprint-admission.md).
Dependencias: Python disponible y tests escritos antes del codigo. Oraculo:
tests/test_sprint_admission.py, SHA256 normalizado registrado en el contrato.
Primera corrida sin implementacion: error ModuleNotFoundError, esperado.
Perimetro implementador: src/sprint_admission.py. Coordinador prepara contrato,
oraculo, ejemplo y evidencia. No subagentes; no tablero ni ejecucion de tareas.

## consumption_budget

Tokens/coste unknown: sin telemetria atribuible. Limite operativo alternativo:
una implementacion, maximo dos ciclos de correccion sin nueva evidencia, una tarea
activa. Reserva de verificacion: suite focal, validadores y suite de regresion.
No afirmar ahorro a partir de cifras sinteticas del ejemplo. Contexto: contrato,
protocolo y reglas KDD; no exploracion adicional de backlog.

## Aceptacion y parada

- CLI devuelve JSON y exit 0 para examples/sprints/admit.json.
- Oraculo verifica rechazos, presupuesto exacto, reserva parcial, tipos invalidos y CLI.
- Validaciones estructurales y regresion no introducen fallos.
- Parar si requiere persistencia, tablero, telemetria externa o reservar presupuesto concurrente.

## Cierre

Resultado: achieved para la prueba tecnica local. Once tests nuevos pasan, incluyendo
CLI real; suite completa: 782 tests, 89.535 segundos, exit 0. Preflight: exit 0,
18/19 checks; seguridad SKIP por ausencia de evidencia opcional, no verificada.
Los cuatro ejemplos se ejecutaron: admitida exit 0; seleccion, dependencia y
presupuesto rechazados exit 1 con sus codigos esperados.

Una implementacion; ningun ciclo de correccion de codigo. Oraculo sin modificaciones
desde el sello. Paquete autonomo tambien probado: 11 tests, exit 0.
Evidencia local: `.agents/logs/sprint-admission-REPORT.md`.
No se ejecuto CI remoto ni gate de complejidad Nivel 2; no hay revision independiente.
No se modifico el tablero ni se publico en GitHub. Tokens/coste y ahorro: unknown.
Pendientes a priorizar: fuente de estado confiable, reserva atomica y conexion al
despachador; requieren nuevos contratos y no se iniciaron en este sprint.

Datos y estimaciones pertenecen a un snapshot confiado:
esta prueba no impide a otro proceso iniciar trabajo ni gastar presupuesto.
