# SPRINT-00 — Ensayar decisiones antes del piloto

Protocolo: [sprints](../../knowledge/sprints.md). Ensayo documental local autorizado
por el usuario con "Probemos". No es una de las tres entregas del piloto comparativo.

## Identidad y resultado

- Estado: closed
- Frente: metodologia KDD, una tarea activa y un coordinador.
- Coordinador y revisor tecnico: asistente de esta conversacion (sin revision independiente).
- Responsable de producto: usuario; la aceptacion humana del resultado no se presume.
- Inicio: 2026-09-08 15:34:39 UTC. Revision final: 15:49:39 UTC.
- Resultado: poder decidir admision, pausa y cierre con la plantilla y registrar ocho
  escenarios concretos, corrigiendo hasta tres ambiguedades documentales encontradas.
- Por que ahora: comprobar el protocolo antes de construir automatizacion.
- Exclusiones: tablero, codigo ejecutable, gate nuevo, despliegue, GitHub y medicion de ahorro.
- Aceptacion: ocho escenarios con datos, decision y fundamento; limites pendientes
  explicitos; validadores OKF y specs en verde tras las correcciones.

## Seleccion ordenada

| Orden | Trabajo | Contribucion | Dependencia | Responsable |
|---|---|---|---|---|
| 1 | D1: recorrer los ocho casos de PILOT.md y examinar bordes | Encontrar ambiguedades | Protocolo y plantilla existentes | Asistente |
| 2 | D2: corregir hasta tres ambiguedades documentales | Hacer decisiones aplicables | D1 y perimetro documental | Asistente |
| 3 | D3: repetir casos, validar y entregar evidencia | Resultado revisable | D2 | Asistente |

Son tareas documentales con alcance y aceptacion en este documento, no contratos
CCDD de implementacion de codigo. Fuente de los escenarios: [PILOT](PILOT.md).

## Capacidad y consumption_budget

- Tokens y coste: unknown; sin telemetria acumulada atribuible a este ensayo.
- Limite alternativo: 15 minutos de reloj desde inicio; incluye preparacion, ejecucion,
  verificacion y cierre. Reserva: 3 minutos de verificacion y 1 minuto de cierre.
- WIP: 1; no se delegan agentes.
- Contexto: tres documentos de sprints y reglas KDD ya leidas; sin limite tecnico de
  tokens instrumentado. Ampliar lecturas solo para resolver un hallazgo concreto.
- Intentos sin evidencia nueva: maximo 2 por caso. Limite de D2: tres ambiguedades.
- Parada: al minuto 11 no iniciar mas correcciones; consumir la reserva para verificar
  y cerrar. Si falla la verificacion sin tiempo, reportar partial con evidencia.
- Revision anticipada: tras D1; hallazgos fuera del perimetro vuelven al backlog.

## Admision

Base: commit 1ddc216b1e07de6eb705f1ab70fdc76b21e0e30c con propuesta documental local
del turno anterior. Validaciones previas: OKF 76, specs 33, contratos 38 sin errores.

| Trabajo | Admision | Evidencia y limite |
|---|---|---|
| D1 | Admitido al inicio | Archivos leidos; sin dependencias externas; WIP 0; presupuesto de 15 minutos |
| D2 | Condicional a D1 | Maximo tres ambiguedades; solo knowledge/sprints.md, plantilla y documento del ensayo |
| D3 | Admitido al finalizar D2 | Validacion documental; reserva incluida; entrega en outputs/ |

## Decisiones, consumo y cierre

D1: ocho escenarios recorridos manualmente. Se encontraron tres ambiguedades:
admision sin pertenencia explicita, alcance de pausa y reserva contada dos veces.
D2 admitido: los tres hallazgos caben en el perimetro documental previsto; se corrigen
protocolo y plantilla. No se agrega trabajo al tablero ni codigo ejecutable.

| Caso | Datos sinteticos y accion intentada | Primera lectura | Decision tras D2 |
|---|---|---|---|
| 1 | Seleccion A; B es urgente y contribuye al mismo objetivo, pero no fue seleccionada | Ambiguo: admision comprobaba contribucion, no pertenencia | No admitir B hasta cambio de seleccion registrado |
| 2 | A pierde dependencia; C ya admitida no depende de A y tiene presupuesto | Ambiguo: el texto decia pausar sin precisar alcance | Bloquear A, permitir C si mantiene admision; no pausar todo el sprint |
| 3 | Limite 100, consumido 80, reserva 20; intentar implementacion 1 o verificacion final 20 | Implementacion rechazada; verificacion ambigua por doble reserva | Rechazar implementacion (101); admitir verificacion (100) si completa controles |
| 4 | Proveedor no devuelve tokens; limite alternativo 15 minutos y reloj disponible | Resuelto | Tokens unknown, controlar reloj; nunca registrar cero |
| 5 | Pruebas de tareas pasan pero el recorrido de aceptacion integrado falla | Resuelto | No aprobar; cerrar partial/not_achieved si llega la revision final |
| 6 | Aparece mejora de avatar durante recuperacion de acceso | Resuelto | Backlog; ninguna implementacion automatica |
| 7 | Contrato de recuperacion abarca emision y consumo; solo emision cabe este sprint | Resuelto | Referenciar entrega parcial y evidencia; no duplicar contrato ni marcarlo totalmente cumplido |
| 8 | Llega revision final, resultado parcial y dos tareas pendientes | Resuelto | Cerrar partial, repriorizar pendientes sin arrastre automatico |

Metodo: lectura manual de reglas contra cada escenario por el mismo asistente que
redacto el protocolo. No se ejecutaron intentos HTTP/MCP ni existe un gate de admision.
Los numeros del caso 3 son sinteticos y no representan consumo de esta conversacion.

Comprobacion adicional del objetivo: caso 7 solo es aceptable si el objetivo del sprint
era la entrega parcial declarada; si prometia recuperacion completa, no esta logrado.

## Evidencia D3 y cierre

D3 admitido y ejecutado tras D2. A las 15:36:31 UTC habian transcurrido 112 segundos
desde el inicio; quedaban 788 segundos del limite total para documentar y entregar.
La verificacion ya estaba completada; su reserva fue consumida por esa fase, no
sumada otra vez. Ningun bloqueo requirio ampliar el alcance o iniciar codigo.

Salida real de validacion local (exit 0 en los tres comandos):

```text
python scripts/validate_okf.py knowledge
OK: todos los nodos OKF son conformes
Resumen: 0 error(es), 0 warning(s) en 76 archivo(s)

python scripts/validate_specs.py specs
OK: todos los contratos de specs son validos
Resumen: 0 error(es) en 33 archivo(s)

python scripts/validate_contracts.py knowledge/contracts
OK: todos los contratos son validos
Resumen: 0 error(es), 0 warning(s) en 38 archivo(s)
```

`git diff --check`: exit 0 para archivos rastreados. Los nuevos documentos de sprint
no son contratos reconocidos por los validadores; los ocho casos se revisaron manualmente.

Identidad de los documentos verificados (SHA256 de bytes locales):
- `knowledge/sprints.md`: `1EBB3D1C39B17EAEA1131624A60C92A8F487B5828A86474E5E702BD6694C15EA`
- `specs/sprints/TEMPLATE-SPRINT.md`: `F2A7B96E664181215078B6CB190C07A4753254F53E4BC5EF7AE25A9D76491388`

Resultado tecnico: achieved para el ensayo documental; ocho decisiones explicitas
tras corregir tres ambiguedades y validaciones estructurales en verde. Revisor: mismo
asistente, sin independencia ni aceptacion humana atribuida. No se aprueba un producto
ni se declara logrado el piloto de ahorro.

Consumo: un turno de asistente; proveedor OpenAI, identificador exacto de modelo no
medido; tokens/coste/reparto por fase unknown. Reloj observado hasta verificacion:
112 segundos. No convertir ese tiempo ni las cifras sinteticas en tokens ahorrados.
El cierre y empaquetado posterior pertenecen al mismo turno; el tiempo anterior no
se presenta como duracion total de la conversacion. El arranque del reloj no incluye
los turnos anteriores que elaboraron la propuesta.

Backlog repriorizado, sin ejecucion en este ensayo:
1. Elegir una entrega real de producto y su criterio integrado para iniciar PILOT-1.
2. Obtener consumo atribuible al sprint o declarar limite alternativo medible.
3. Evaluar automatizacion solo despues de revisar las entregas del piloto.

Ventana de regresiones: solo esta revision documental; seguimiento posterior no medido.
No hay linea base comparable ni porcentaje de ahorro demostrable.
