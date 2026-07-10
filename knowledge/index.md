# Knowledge Bundle (OKF)

Bienvenido a la base de conocimiento del proyecto. El formato de los nodos está especificado en [OKF-SPEC](./OKF-SPEC.md).

## Referencia
- [Especificación OKF](./OKF-SPEC.md) — spec normativa de nodos OKF.
- [Metodología de ejecución por contratos](./metodologia-ejecucion.md) — proceso operativo de nivel proyecto (specs/, docs/reports/, delegación y verificación).
- [Validación de contratos](./validacion.md) — nodo canónico: niveles 1 y 2, gate multi-lenguaje, export, precedencia del budget y ciclo de vida.
- [Casos reales de la metodología](./casos-reales.md) — incidentes verificados que motivaron las reglas; evidencia separada del proceso normativo.
- [Upgrade de la plantilla](./plantilla-upgrade.md) — qué es infraestructura sobreescribible desde upstream vs. propiedad del proyecto; procedimiento manual de upgrade.
- [Rule contract](./rule-contract-spec.md) — vertiente que valida reglas de negocio como datos declarativos (no solo código); familias, golden set y frontera dato/lógica.

## Estructura
- [Contratos de Desarrollo](./contracts/)
  - [Ejemplo de Tarea (Hello World)](./contracts/sample_task.md)
  - [Validación de registro de usuario](./contracts/validate-user-record.md)
  - [Validación de límite de pago por país](./contracts/validate-payment-limit.md)
  - [Router de mensajes por emisor](./contracts/route-message.md)
  - [Checker de ciclos del grafo de un workflow](./contracts/check-graph.md)
  - [Validador editorial de artículos](./contracts/validate-article.md)
  - [Checker de cableado de agentes](./contracts/check-agent-wiring.md)
  - [Motor de reglas declarativo (rule contract)](./contracts/validate-rules.md)
  - [Gate determinista de rule contracts](./contracts/rules-gate.md)
  - [Gate de skills de agente](./contracts/skills-gate.md)
  - [Gate de coherencia CHANGELOG↔reportes](./contracts/changelog-gate.md)
  - [Gate de perímetro (touch_only como dato)](./contracts/perimeter-gate.md)
  - [Herramienta de benchmark de gates y suite](./contracts/benchmark-gates.md)
  - [Gate de UX/accesibilidad de páginas HTML](./contracts/ux-page-gate.md)
  - [Gate de formato de mensaje de commit](./contracts/commit-message-gate.md)
  - [Validador OKF de la base de conocimiento](./contracts/validate-okf.md)
  - [Validador de contratos de ejecución (specs)](./contracts/validate-specs.md)
  - [Lint ASCII de literales en scripts](./contracts/lint-ascii.md)
  - [Inicializador de proyecto desde la plantilla](./contracts/init-project.md)
  - [Versionado de la plantilla (coherencia CHANGELOG/README/upgrade)](./contracts/versioning-plantilla.md)
  - [Ensamblador de contexto CCDD Nivel 2](./contracts/assemble-context.md)
  - [Exportador de contratos para el gate CCDD Nivel 2](./contracts/export-gate-contract.md)
  - [Regla de contexto presupuestado en las reglas de agentes](./contracts/agents-context-rule.md)
- [Modelos de Datos](./data_models/)
  - [Tabla users](./data_models/users_table.md)
  - [Limites de pago por pais](./data_models/payment_limits.md)
  - [Reglas de control de fronteras](./data_models/border_rules.md)
  - [Politica de workflows](./data_models/workflow_policy.md)
  - [Politica de ruteo de mensajes](./data_models/message_routing.md)
  - [Estilo editorial de articulos](./data_models/editorial_style.md)
  - [Registro de servidores MCP](./data_models/mcp_registry.md)
  - [Cableado de agentes](./data_models/agent_wiring.md)
  - [Convención UX/accesibilidad](./data_models/ux_page_contract.md)
  - [Convención de mensaje de commit](./data_models/commit_message_contract.md)
- [Arquitectura](./architecture/)
  - [Arquitectura general](./architecture/overview.md)