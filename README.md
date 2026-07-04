# KDD Template (Knowledge-Driven Development)

Este es un repositorio plantilla para proyectos que implementan la metodología **Knowledge-Driven Development (KDD)**, la cual unifica:
- **OKF (Open Knowledge Format):** Un formato minimalista para estructurar el conocimiento, diseño y arquitectura como archivos markdown con frontmatter YAML. La spec normativa de los nodos OKF está en [`knowledge/OKF-SPEC.md`](knowledge/OKF-SPEC.md).
- **CCDD (Contract-Driven Development):** Una metodología para gobernar el desarrollo con agentes de IA efímeros mediante contratos estrictos y umbrales deterministas (complejidad, tests congelados).

## Estructura del Repositorio

- `knowledge/`: Aquí vive tu base de conocimiento OKF. Todo archivo aquí es un nodo indexable.
- `knowledge/contracts/`: Donde se definen las tareas para los desarrolladores (humanos o IA) usando el formato híbrido OKF+CCDD.
- `src/` y `tests/`: Código de implementación y pruebas automatizadas.
- `scripts/validate_contracts.py`: Validador determinista de contratos (stdlib, sin LLM, sin red).
- `.agents/`: Reglas locales para agentes de IA que clonen este repositorio.

## Cómo usar esta plantilla

1. Usa este repositorio como "Template" en GitHub o clónalo localmente.
2. Explora `knowledge/index.md` para ver cómo se estructuran los conceptos.
3. Al delegar trabajo a un agente (ej. Claude, Antigravity, etc.), el agente leerá `.agents/AGENTS.md` y entenderá inmediatamente que debe respetar los contratos CCDD de este repositorio.

## Validación de Contratos

La validación tiene **dos niveles**. Solo el nivel 1 es obligatorio y viene incluido en la plantilla.

### Nivel 1 — Incluido y obligatorio (local + CI)
- `python scripts/validate_contracts.py knowledge/contracts` — valida frontmatter, secciones obligatorias y examples de cada contrato.
- El `test_command` declarado en el frontmatter del contrato — debe terminar en verde.

Ambos corren localmente y en CI (`.github/workflows/validate.yml` ejecuta el validador y `python -m unittest discover -s tests -p "test_*.py"`).

### Nivel 2 — Opcional (si el entorno del agente lo tiene)
Si el agente dispone del servidor MCP `ccdd-complexity`, el gate CCDD real se invoca con sus tools `lint_task_contract` (lint del contrato) y `run_integration_gate` (gate de complejidad/integración). Si no está disponible, el nivel 1 es suficiente para considerar un contrato válido.

## Precedencia del Budget

- **Con gate CCDD disponible (nivel 2):** la config firmada por el gate manda. El `budget` del frontmatter solo puede ser **<=** los topes firmados; ante cualquier conflicto gana la config firmada del gate.
- **Sin gate (solo nivel 1):** el `budget` del contrato es declarativo/informativo. El validador incluido solo verifica su **presencia** en el frontmatter; no aplica (enforce) los topes.

## Ciclo de Vida del Contrato

1. **draft** — contrato redactado en `knowledge/contracts/<task>.md`.
2. **validated** — `python scripts/validate_contracts.py knowledge/contracts` (y `lint_task_contract` si hay gate) en verde.
3. **implemented** — `test_command` del contrato en verde.
4. **verified** — la salida **REAL** de los comandos (validador + `test_command`, y gate si corre) se pega en `.agents/logs/<task>-REPORT.md`. Ese directorio está gitignorado a propósito: es evidencia local, no parte del repo.