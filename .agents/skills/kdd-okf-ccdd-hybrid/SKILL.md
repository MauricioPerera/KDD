---
name: kdd-okf-ccdd-hybrid
description: Define el estándar Knowledge-Driven Development (KDD) que unifica el modelado de contexto de Open Knowledge Format (OKF) con el rigor de Contract-Driven Development (CCDD). Úsala al redactar o validar un task contract híbrido OKF+CCDD, al crear nodos en knowledge/, al instanciar la plantilla KDD en un proyecto, o cuando se mencione "contrato híbrido", "task contract", "nodo OKF", "KDD" o el ciclo draft→validated→implemented→verified.
---

# Knowledge-Driven Development (KDD): OKF + CCDD

Esta skill establece las reglas obligatorias al definir tareas de desarrollo utilizando la metodología híbrida. 
El objetivo es que los contratos no sean documentos aislados, sino nodos vivos de la base de conocimiento OKF que controlan determinísticamente a los agentes efímeros.

## 1. El Contrato es un Nodo OKF
Todo Task Contract CCDD que se escriba (p.ej. `implementar_login.md`) debe comenzar estrictamente con un Frontmatter YAML válido.

## 2. Fusión de Metadatos (Frontmatter)
El Frontmatter debe unificar los campos requeridos por ambas metodologías:
- **OKF Fields:** `type` (debe ser `'Task Contract'`), `title`, `description`, `tags`.
- **CCDD Fields:** `task`, `intent`, `target`, `signature`, `test_command`, `budget`, `tests`, `tests_sha256`, `deps_allowed`.

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
tests_sha256: "a1b2c3d4e5f6..."
---
```

## 3. Contexto Interconectado (Enlaces OKF)
Para proveer el contexto del negocio y diseño a los agentes efímeros sin abrumarlos, **está prohibido duplicar reglas de negocio de manera verbosa en el contrato**.
En lugar de eso, en secciones como `## Intent`, `## Interface`, o `## Constraints`, se DEBE usar un enlace de Markdown relativo hacia los nodos de OKF relevantes (arquitectura, modelos de datos).
- **DO:** "Validar formato contra `knowledge/data_models/users_table.md`"
- **DON'T:** "La tabla de usuarios tiene un uuid, un email, un password, y una fecha de creación, y su ID es un string de 36 caracteres..."

## 4. Validación Continua Obligatoria (dos niveles)
Antes de dar un contrato por terminado o pasárselo a un agente efímero, debes validarlo. La referencia canónica completa (niveles 1 y 2, gate multi-lenguaje, export para el gate) está en [knowledge/validacion.md](../../../knowledge/validacion.md) — esta skill no la duplica. Resumen: nivel 1 (obligatorio) = `python scripts/validate_contracts.py knowledge/contracts` (incluye el sello `tests_sha256`; sellar con `--hash`) + `python scripts/validate_specs.py specs` + `python scripts/validate_okf.py knowledge` (estructura/frontmatter de nodos OKF) + `python scripts/lint_ascii.py scripts` + `python scripts/validate_rules.py <dir>` (rule contracts, capa opcional) + `python scripts/validate_skills.py skills .agents/skills` (skills de agente, capa opcional) + `python scripts/validate_changelog.py` (coherencia CHANGELOG↔reportes, capa opcional) + `python scripts/validate_ux_page.py examples/ux-page` (UX/accesibilidad mecanica sobre paginas HTML autocontenidas, capa opcional) + `test_command` en verde, local y en CI (matriz dual-OS, suite 2x); nivel 2 (opcional) = gate CCDD vía MCP `ccdd-complexity` (`lint_task_contract`, `run_integration_gate`). Sin gate disponible, el nivel 1 basta para considerar el contrato válido.

## 5. Precedencia del Budget
Ver [knowledge/validacion.md](../../../knowledge/validacion.md): con gate manda su config firmada (el `budget` del frontmatter solo puede ser <=); sin gate, el `budget` es declarativo y el validador solo verifica su presencia.

## 6. Ciclo de Vida del Contrato
`draft` → `validated` → `implemented` → `verified`; el detalle de cada estado y la evidencia requerida están en [knowledge/validacion.md](../../../knowledge/validacion.md). La evidencia va en `.agents/logs/<task>-REPORT.md` (gitignorado a propósito: local, no parte del repo).

## 7. Contexto presupuestado (CCDD Nivel 2)
Antes de delegar la implementación a un agente efímero, ensambla el contexto de la tarea con
`python scripts/assemble_context.py ccdd/context.json "<tarea>"` (usa `-v` si necesitas el
contexto completo). El momento es entre **validated** e **implemented**: el contrato ya está
en verde y vas a pasárselo a un dev, así que primero le preparas su presupuesto de slots.

El reporte de slots/guardrails que devuelve el ensamblador se pega en
`.agents/logs/<task>-REPORT.md` junto con la evidencia del ciclo de vida (sección 6): forma
parte de lo que hace que una tarea quede **verified**. Si un guardrail sale con
`on_fail: abort` (exit 2), la delegación se bloquea — resuélvelo antes de continuar. No
duplices aquí la doc del ensamblador: la referencia por ruta basta (regla 7 de
`.agents/AGENTS.md`).
