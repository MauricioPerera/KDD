---
type: 'Concept'
title: 'Perfiles de adopción KDD'
description: 'Define niveles progresivos para adoptar la validación KDD sin asumir toda la infraestructura desde el primer día.'
tags: ['kdd', 'adopcion', 'validacion']
---

# Perfiles de adopción KDD

KDD ofrece tres perfiles explícitos. El perfil elegido cambia la profundidad de
la verificación, no el formato de los contratos ni la trazabilidad de los tests.

## Minimal

Para un proyecto nuevo: valida contratos y ejecuta la suite del proyecto una sola vez.

```text
python scripts/run_profile.py --profile minimal
```

## Standard

Es el perfil recomendado: exige una referencia de contrato/oráculo aprobada,
ejecuta todos los `test_command` y añade specs, OKF, reglas, skills,
changelog y secretos. El SHA lo proporciona quien aprueba el oráculo; no se
deduce de `HEAD`.

```text
python scripts/run_profile.py --profile standard --approved-ref <SHA_APROBADO>
```

## Strict

Para CI o una revisión de entrega: añade budgets, auditoría de seals, auditoría
de `forbids` y preflight. El modo global de budgets es diagnóstico mientras se
migran los contratos históricos; una tarea nueva puede limitarlo con
`validate_budgets.py --contract <task>`.

```text
python scripts/run_profile.py --profile strict --approved-ref <SHA_APROBADO>
```

Para incorporar mutación a una revisión concreta:

```text
python scripts/run_profile.py --profile strict --approved-ref <SHA_APROBADO> --mutation-contract knowledge/contracts/<task>.md
```

Para hacer cumplir el budget de una tarea sin bloquearse por la deuda histórica:

```text
python scripts/run_profile.py --profile strict --approved-ref <SHA_APROBADO> --budget-contract knowledge/contracts/<task>.md
```

Todos los perfiles se detienen en el primer fallo, muestran el paso responsable
y usan comandos explícitos sin shell. Así la adopción puede crecer por etapas sin
convertir un proyecto pequeño en una instalación de infraestructura completa.
El reporte separa `PASS`, `FAIL` y `SKIP`; los comandos de contratos se agrupan
por producto e infraestructura. `minimal` conserva su uso sin referencia
aprobada y no ofrece la misma garantía.
