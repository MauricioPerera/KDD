---
name: kdd-okf-ccdd-hybrid
description: Define el estándar Knowledge-Driven Development (KDD) que unifica el modelado de contexto de Open Knowledge Format (OKF) con el rigor de Contract-Driven Development (CCDD).
---

# Knowledge-Driven Development (KDD): OKF + CCDD

Esta skill establece las reglas obligatorias al definir tareas de desarrollo utilizando la metodología híbrida. 
El objetivo es que los contratos no sean documentos aislados, sino nodos vivos de la base de conocimiento OKF que controlan determinísticamente a los agentes efímeros.

## 1. El Contrato es un Nodo OKF
Todo Task Contract CCDD que se escriba (p.ej. `implementar_login.md`) debe comenzar estrictamente con un Frontmatter YAML válido.

## 2. Fusión de Metadatos (Frontmatter)
El Frontmatter debe unificar los campos requeridos por ambas metodologías:
- **OKF Fields:** `type` (debe ser `'Task Contract'`), `title`, `description`, `tags`.
- **CCDD Fields:** `task`, `intent`, `target`, `signature`, `test_command`, `budget`, `tests`, `deps_allowed`.

Ejemplo:
```yaml
---
type: 'Task Contract'
title: 'Implementar verify_user'
description: 'Función pura para validación de ID.'
tags: ['ccdd', 'auth']

task: verify_user
intent: "Implementar la validación..."
target: verify_user.py
signature: "def verify_user(id: str) -> bool:"
test_command: "python -m unittest verify_test.py"
budget:
  max_cyclomatic_complexity: 4
tests: "verify_test.py"
---
```

## 3. Contexto Interconectado (Enlaces OKF)
Para proveer el contexto del negocio y diseño a los agentes efímeros sin abrumarlos, **está prohibido duplicar reglas de negocio de manera verbosa en el contrato**.
En lugar de eso, en secciones como `## Intent`, `## Interface`, o `## Constraints`, se DEBE usar un enlace de Markdown relativo hacia los nodos de OKF relevantes (arquitectura, modelos de datos).
- **DO:** "Validar formato contra [users_table.md](../data_models/users_table.md)"
- **DON'T:** "La tabla de usuarios tiene un uuid, un email, un password, y una fecha de creación, y su ID es un string de 36 caracteres..."

## 4. Validación Continua Obligatoria (dos niveles)
Antes de dar un contrato por terminado o pasárselo a un agente efímero, debes validarlo. Hay dos niveles:

- **Nivel 1 (incluido en la plantilla, obligatorio):** `python scripts/validate_contracts.py knowledge/contracts` valida frontmatter, secciones obligatorias y examples; y el `test_command` del contrato debe terminar en verde. Ambos corren local y en CI (`.github/workflows/validate.yml`).
- **Nivel 2 (opcional, si el entorno lo tiene):** el gate CCDD real vía servidor MCP `ccdd-complexity`, con las tools `lint_task_contract` (lint del contrato) y `run_integration_gate` (gate de complejidad/integración).

Si no hay gate disponible, el nivel 1 es suficiente para considerar el contrato válido.

## 5. Precedencia del Budget
- **Con gate CCDD disponible (nivel 2):** la config firmada por el gate manda. El `budget` del frontmatter solo puede ser **<=** los topes firmados; ante cualquier conflicto gana la config firmada del gate.
- **Sin gate (solo nivel 1):** el `budget` del contrato es declarativo/informativo. El validador incluido solo verifica su **presencia** en el frontmatter; no enforced los topes.

## 6. Ciclo de Vida del Contrato
1. **draft** — contrato redactado en `knowledge/contracts/<task>.md`.
2. **validated** — `python scripts/validate_contracts.py knowledge/contracts` (y `lint_task_contract` si hay gate) en verde.
3. **implemented** — `test_command` del contrato en verde.
4. **verified** — la salida **REAL** de los comandos se pega en `.agents/logs/<task>-REPORT.md`. Ese directorio está gitignorado a propósito: es evidencia local, no parte del repo.
