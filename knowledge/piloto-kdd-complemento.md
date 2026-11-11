---
type: 'Concept'
title: 'Piloto de KDD como complemento para un repositorio existente'
description: 'Evidencia de paridad del validador fijado por Git en Codex, terminal y GitHub Actions.'
tags: ['kdd', 'adoption', 'plugin', 'validation', 'evidence']
---

# Piloto de KDD como complemento

El 10 de noviembre de 2026 se verificó que un repositorio Python existente puede adoptar un contrato KDD y validarlo con la misma revisión de KDD desde Codex, la terminal y GitHub Actions. El consumidor fue `MauricioPerera/delegate-codex-cli`, que ya tenía pruebas, historial y CI. El piloto quedó en la rama `codex/kdd-validator-pilot`, con un workflow adicional y la suite original intacta. [Base del consumidor](https://github.com/MauricioPerera/delegate-codex-cli/commit/ba90f5808639ebea5795139984b06d5aae38e99f) · [Árbol final del piloto](https://github.com/MauricioPerera/delegate-codex-cli/tree/b9518a9ddded49af4d0bbcf9142794c210555179)

## Diseño comprobado

- El repositorio consumidor guarda un único SHA completo de KDD en `.kdd/validator.lock`. Los tres entornos ejecutan `python .kdd/validate.py`. La skill de Codex indica ese comando y el workflow lo ejecuta en Ubuntu y Windows sobre el commit del evento. [Lanzador](https://github.com/MauricioPerera/delegate-codex-cli/blob/b9518a9ddded49af4d0bbcf9142794c210555179/.kdd/validate.py) · [Workflow](https://github.com/MauricioPerera/delegate-codex-cli/blob/b9518a9ddded49af4d0bbcf9142794c210555179/.github/workflows/kdd-pilot.yml)
- Cada ejecución requiere Git, Python 3.11 y acceso al repositorio de KDD. El lanzador obtiene el commit y comprueba el SHA y los blobs que materializa en un directorio temporal antes de ejecutar los validadores. El registro `KDD_PILOT` identifica el SHA solicitado y el verificado, el commit consumidor, el contrato, el sello y el resultado.
- El contrato se registró primero. Un adaptador sellado selecciona un caso `unittest` de la suite original que comprueba el orden del contexto y la posición de la meta. El sello corresponde al adaptador. El archivo original figura en el inventario del oráculo y se verificó que sus bytes permanecieron iguales en toda la prueba. [Commit del contrato y oráculo](https://github.com/MauricioPerera/delegate-codex-cli/commit/f6c2f77efb03e857ee31a8351d4bbbde07e04f9d)

## Evidencia

A corresponde a `e07e404b4a8576f26cf9b6d3628f7ce5cd8ccaa8` y B a `3cc5948dc0cf151519dbe8b595c30d7947159336`. Se compararon 25 registros, cinco escenarios en Codex para Windows, terminal en Ubuntu y Windows, y Actions en Ubuntu y Windows. Para cada escenario coincidieron el commit consumidor, el SHA efectivo de KDD y el sello. [Registros comparados](../docs/reports/KDD-PLUGIN-PILOT-EVIDENCE.json)

| Escenario | Commit consumidor | SHA de KDD | Resultado en los cinco entornos | GitHub Actions |
| --- | --- | --- | --- | --- |
| A inicial | `fd36da8` | A | Verde, un caso ejecutado | [42927995990](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42927995990) |
| Cambio a B | `340b6b3` | B | Verde, un caso ejecutado | [42928156535](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928156535) |
| Vuelta a A | `234112b` | A | Verde, un caso ejecutado | [42928172887](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928172887) |
| Inversión del orden | `fc1873d` | A | Rojo en la aserción de orden | [42928189260](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928189260) |
| Reversión | `b9518a9` | A | Verde, un caso ejecutado | [42928204122](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928204122) |

Los dos cambios de versión editaron únicamente el lock. La regresión cambió una línea de producción y falló en `test_kdd_prefix_is_deterministic_and_goal_is_last`. La reversión recuperó exactamente el árbol anterior a la regresión. Para repetir la prueba, hacer checkout de cada commit del consumidor y ejecutar el comando del piloto con Python 3.11. El workflow original pasó en el commit final. [CI original](https://github.com/MauricioPerera/delegate-codex-cli/actions/runs/42928204144)

En copias descartables se rechazaron un pin ausente o inválido, un commit remoto inexistente, un blob alterado, un contrato ausente y una política KDD sin referencia aprobada. Al invalidar el sello, la suite original siguió en verde y el lanzador rechazó el contrato antes de ejecutar el oráculo.

## Alcance del resultado

El piloto acredita la adopción de un contrato en un proyecto existente mediante una skill del propio repositorio y un lanzador común. La [plantilla](../README.md) sigue siendo el punto de partida documentado para proyectos nuevos. El [complemento público de Codex](../plugins/kdd-codex/README.md) ofrece su skill de flujo KDD. La instalación reutilizable del piloto y la distribución de esta integración como complemento quedan por validar.

La prueba de Codex se completó con el binario de la aplicación y el modo de permisos de la sesión. El intento con el aislamiento de escritura de Windows falló al iniciar el proceso de shell. El consumidor carecía de una política KDD activa. La prueba solo comprobó el rechazo al omitir su referencia, que pertenece al proyecto consumidor. El SHA del lock identifica los scripts de KDD. [Aprobación de calidad](quality-approval.md)
