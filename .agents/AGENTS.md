# Reglas para Agentes de IA

Si eres un agente de IA interactuando con este repositorio, debes acatar las siguientes reglas:

1. **Metodología KDD Obligatoria**: Este repositorio utiliza Knowledge-Driven Development. Antes de escribir código, debes leer los contratos en `knowledge/contracts/` y la spec normativa de los nodos OKF en `knowledge/OKF-SPEC.md`.
2. **Carga la Skill Local**: Tienes disponible la skill `kdd-okf-ccdd-hybrid` en el directorio `.agents/skills/`. Debes adoptarla en tu contexto para entender cómo generar y validar los contratos híbridos OKF-CCDD.
3. **No dupliques contexto**: Utiliza enlaces de markdown relativos a `knowledge/` cuando necesites explicar el porqué de una implementación.
4. **Validación Determinista (dos niveles)**:
   - **Nivel 1 (incluido, obligatorio):** `python scripts/validate_contracts.py knowledge/contracts` + el `test_command` del contrato. Ambos corren local y en CI (`.github/workflows/validate.yml`).
   - **Nivel 2 (opcional, si lo tienes):** el gate CCDD real vía servidor MCP `ccdd-complexity` con las tools `lint_task_contract` y `run_integration_gate`.
   Ningún contrato se considera terminado hasta que pase el nivel 1.
5. **Precedencia del Budget**: si hay gate CCDD disponible, la config firmada del gate manda — el `budget` del frontmatter solo puede ser <= a los topes firmados y ante conflicto gana la config firmada. Sin gate, el `budget` es declarativo/informativo y el validador incluido solo verifica su presencia.
6. **Ciclo de Vida del Contrato**: `draft` -> `validated` (validador/lint en verde) -> `implemented` (`test_command` en verde) -> `verified` (salida REAL de los comandos pegada en `.agents/logs/<task>-REPORT.md`; ese directorio está gitignorado a propósito).