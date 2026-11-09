---
type: 'Concept'
title: 'Flujo ligero para cambios pequenos'
description: 'Reducir los artefactos de trabajo editorial acotado conservando la aprobacion de las garantias.'
tags: ['methodology', 'odd', 'git', 'review']
---

# Flujo ligero para cambios pequenos

Este perfil adapta el criterio de recuperacion de
[Organic Driven Development](https://github.com/Gentleman-Programming/gentle-ai/blob/main/docs/usage.md#organic-driven-development-odd).
El pedido, el diff y la evidencia breve del commit o PR deben bastar para que
otra persona pueda retomar el trabajo. La exploracion precede a esa decision.

## Entrada y cierre

1. Confirmar que el pedido autoriza el cambio. Leer los archivos afectados,
   sus referencias y la politica aplicable. Usar la via ligera si la
   intencion es editorial, el alcance cabe en un commit y otra persona puede
   retomarlo con el pedido y el diff. En esta primera version son elegibles
   ediciones de archivos existentes en `README.md`,
   `docs/KDD-PARA-PERSONAS.md` y `docs/guides/**/*.md`.
2. Comprobar el diff y los enlaces o ejemplos afectados. Resumir la
   intencion y los controles ejecutados en el commit o PR. El flujo no exige
   una spec, nodo de tarea, rama por tarea ni informe adicional. Aplicar las
   reglas de rama y aprobacion del proyecto.
3. Comprobar el candidato local con los SHA completos de la base de trabajo
   y del candidato. La base representa el punto anterior a todo el cambio.

   ```text
   python scripts/baseline_review.py --small-change --base-ref BASE --candidate-ref CANDIDATO --editorial-only
   ```

   `--editorial-only` declara que la persona a cargo leyo el diff completo,
   confirmo que el cambio es recuperable y comprobo que conserva las
   garantias y respeta las politicas vigentes, incluso si protegen una guia.
   El resultado `lightweight` registra elegibilidad, sin conferir aprobacion.
   Git identifica archivos y modos. El juicio editorial y las restricciones
   de producto requieren leer el contenido y su politica.
4. Volver al [flujo de ejecucion](metodologia-ejecucion.md) si el resultado
   indica `standard`, cambia el alcance o aparece incertidumbre. Si cambian
   requisitos, criterios de aceptacion, contratos, oraculos, politicas o
   garantias, definir el nuevo contrato y su prueba antes de implementar y
   aplicar la [revision del baseline](baseline-risk-review.md) y su
   [aprobacion humana](quality-approval.md). Un cambio de codigo que cumple
   un baseline vigente sigue el proceso aplicable a ese baseline.

Corregir una errata en una guia puede ser ligero. Rebajar un compromiso
publicado en la misma guia requiere revision aunque solo cambie una palabra.
Las dos pasadas de la suite en Ubuntu y Windows se aplican por el CI
habitual. El [contrato](contracts/odd-lightweight.md) define la comprobacion
de Git, sus salidas y sus limites.
