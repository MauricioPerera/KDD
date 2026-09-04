# KDD-Board — Definición del Proyecto

## Qué es
Una interfaz colaborativa de gestión de tareas y ejecución KDD (Knowledge-Driven Development) en tiempo real, diseñada para orquestar flujos de trabajo simbióticos entre desarrolladores humanos y agentes de IA autónomos a través del protocolo WebMCP (fastwebmcp), con protección estricta de credenciales mediante Blind Secrets Vault.

## Arquitectura
El sistema se compone de un backend modular en Node.js/TypeScript y un frontend reactivo sin dependencias pesadas:
- **Core State Engine (`TaskStore`)**: Máquina de estados determinista y persistente en JSON (`data/tasks.json`) que rige el ciclo de vida colaborativo (`backlog` -> `ready` -> `in_progress` -> `needs_human_input` -> `done`).
- **Blind Vault (`BlindVault`)**: Almacén seguro en `.env.local` que inyecta variables reales en el entorno del proceso para compilación/tests, mientras que enmascara criptográficamente todos los valores hacia los agentes de IA (`sk_***...***00`).
- **WebMCP Bridge (`fastwebmcp`)**: Servidor MCP integrado en el contexto web que expone 7 herramientas declarativas con esquemas Zod estrictos (`list_tasks`, `get_task`, `create_task`, `update_task_status`, `request_human_input`, `list_available_credentials`, `run_task_tests`).
- **KDD Test Runner (`TestRunner`)**: Ejecutor automatizado que corre comandos oráculo congelados (`node --test`), capturando salida, tiempos y métricas de conformidad KDD.
- **Frontend SPA Multi-Vista**:
  - `📋 Tablero`: Tablero Kanban interactivo con soporte de desbloqueo reactivo y píldoras de contratos en 1 clic.
  - `📊 Resumen KDD`: Dashboard de métricas, salud de pruebas y distribución de carga humano vs agente.
  - `📚 Documentación KDD`: Visor y validador de contratos OKF/CCDD y especificaciones normativas.
  - `🔍 Detalle de Tarea`: Espacio de trabajo dedicado full-screen.

## Capacidades objetivo
- Orquestación bidireccional de tareas con paso de posta automático entre humanos y agentes.
- Solicitud de requerimientos bloqueantes por parte del agente en forma de formulario seguro.
- Gestión CRUD de variables sensibles en el Blind Vault sin filtración de secretos al LLM.
- Ejecución y auditoría de suites de tests locales con terminal integrada y KPIs de salud.
- Navegación bidireccional en 1 clic entre tareas del backlog y contratos formales KDD.
- Validación determinista de contratos sin LLM mediante `scripts/validate_contracts.py`.
- Visualización e inspección de la Definición del Proyecto (`DEFINITION.md`) como anclaje metodológico previo al phaseado.

## Por qué es un caso válido / motivación real
Los agentes de IA actuales sufren de pérdida de contexto, riesgo de alucinación y peligro constante de exfiltración de credenciales cuando se les pide integrar servicios de terceros (APIs, bases de datos). KDD-Board resuelve este problema desacoplando la posesión del secreto (que reside únicamente en el entorno del sistema y en la mente del humano) de la invocación del código, todo gobernado por contratos verificables por máquina.

## Fuera de alcance
- Autenticación multi-usuario remota con OAuth/JWT (el sistema es una herramienta local de ingeniería y pair programming).
- Persistencia en base de datos distribuida (se prioriza formato plano auditable en Git `tasks.json` y `.env.local`).
- Ejecución de código en contenedores remotos o sandbox cloud (se ejecuta contra el runtime local del proyecto).
