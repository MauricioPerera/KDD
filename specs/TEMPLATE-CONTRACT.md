# Contrato NN — <título corto del objetivo>

Prerrequisitos: <contratos previos completados / estado del repo>. <1-3 líneas de contexto:
qué problema cierra este contrato y por qué ahora.>

> Capa: este es un **contrato de ejecución** (nivel proyecto). Las tareas que impliquen código
> delegado a un agente efímero llevan además su **task contract** CCDD en
> `knowledge/contracts/<task>.md` (validado por `scripts/validate_contracts.py`).

## <ID-TAREA-1> (T1) — <título>

<Qué está mal hoy o qué falta, con ruta:línea si aplica.>

FIX/OBJETIVO: <estado final deseado, no pasos. Invariantes que NO pueden cambiar.>

## <ID-TAREA-2> (T2) — <título>

<...>

## Criterios de aceptación

- [ ] Por tarea: `python scripts/validate_contracts.py knowledge/contracts` exit 0 y
  `python -m unittest discover -s tests -p "test_*.py"` verde (UNA corrida).
- [ ] <criterio observable por máquina 1 — comando + resultado esperado>
- [ ] <criterio observable por máquina 2>
- [ ] Final: suite completa 2× verde (dos corridas idénticas ≈ sin flaky); CI verde.

## Restricciones

- Tocar SOLO: <lista explícita de archivos/dirs por tarea — conjuntos DISJUNTOS si hay
  devs concurrentes>.
- Sin dependencias nuevas (stdlib salvo aprobación explícita); sin red ni subprocess en
  scripts deterministas.
- Respetar OKF: todo nodo nuevo en `knowledge/` con frontmatter válido y enlazado desde
  `knowledge/index.md`; los task contracts pasan el validador.
- NO commitear (el PM commitea por tarea verificada). Si algo no se puede sin romper otro
  criterio, PARAR y reportar.
- ABORTAR SI: <condiciones concretas, p.ej. un criterio resulta inalcanzable por una razón
  legítima; falta una dependencia que no se puede instalar; el fix exige tocar archivos
  fuera del perímetro> → PARAR, documentar el porqué con evidencia en el reporte y marcar
  BLOQUEADO. No improvisar ni forzar: si el objetivo era demostrar X y el análisis muestra
  que X es falso o equivalente, documentarlo con la evidencia ES el entregable válido.

## Checklist antes de delegar

> Forma operativa de las reglas RECON / red-team / perímetro / aborto de
> [knowledge/metodologia-ejecucion.md](../knowledge/metodologia-ejecucion.md).
> Ante divergencia, manda la metodología y este checklist se re-alinea.

- [ ] RECON corrido: toda suposición del contrato verificada con un check real (comando de
  suite real del CI, workflows completos — incluidos los condicionales por diff —, deps).
- [ ] Todo criterio de aceptación tiene comando + resultado esperado (por máquina, nunca
  "por lectura").
- [ ] Red-team hecho: ningún camino cumple los comandos sin cumplir la intención (¿evasión
  del budget? ¿test que pasa en vacío? ¿oráculo que se puede reescribir?) y ningún check
  contradice otra orden del propio contrato (eso fuerza un judgment call al agente).
- [ ] Perímetro de archivos declarado por tarea, disjunto entre tareas concurrentes.
- [ ] Condiciones de aborto explícitas (ABORTAR SI rellenado, no genérico).
