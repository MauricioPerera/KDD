---
type: 'Concept'
title: 'Puente GAME Protocol: datos de juego bajo contratos KDD'
description: 'Receta canónica para integrar game-protocol (gameplay as data) en un proyecto KDD: vendorear el toolchain, perfil propio, y un task contract cuyo oráculo sellado corre lint/export/asserts del artefacto. Incluye las fricciones conocidas y sus mitigaciones.'
tags: ['game-protocol', 'ccdd', 'integracion', 'guide']
---

# Puente GAME Protocol — datos de juego bajo contratos KDD

[game-protocol](https://github.com/MauricioPerera/game-protocol) es el hermano de CCDD
para el dominio juego: documentos de dos capas (frontmatter YAML verificable + Markdown
juzgable), validación determinista sin LLM y artefacto compilado sin drift. Este nodo es
la receta **verificada en un proyecto real** (MiniTown) para usar ambos juntos: KDD
gobierna el *proceso* (contratos, oráculos sellados, perímetro); game-protocol gobierna
el *contenido* (qué es dato vs. lógica en un juego).

## La receta canónica

1. **Vendorear el toolchain** (no npm): copiar de game-protocol `tools/yaml-min.js`,
   `game-lint-core.js`, `game-lint.js`, `profile-helpers.js`, `game-build-core.js`,
   `game-export.js`, `rule-hints.js` y los `profiles/` que uses a un directorio del
   proyecto (p.ej. `game/tools/`, `game/profiles/`). Son Node puro sin dependencias;
   el CLI resuelve perfiles en `../profiles` relativo a `tools/`.
2. **Perfil propio si el género no existe**: un perfil es `{id, specVersion, sections,
   required, refs, rules, derive}` — el análogo de un [rule contract](./rule-contract-spec.md)
   para datos de juego. Puede componer un perfil existente (p.ej. reutilizar las
   colecciones voxel via require relativo) y sumar colecciones + reglas propias con
   prefijo de rule-id del proyecto.
3. **Un task contract KDD por la capa de datos**: target = el perfil; `touch_only` =
   `[GAME.md, profiles/<propio>.js, game-data.generated.js]`; y el **oráculo congelado**
   (sellado con `tests_sha256`, ver [validación](./validacion.md)) corre:
   - `lintGame(data, body, {profile})` del core vendoreado → 0 errores;
   - asserts de forma sobre `buildGame(data, profile)` (claves derivadas, rangos,
     invariantes del dominio);
   - **no-drift**: el `game-data.generated.js` commiteado debe ser deepEqual al
     recompilado — mismo patrón que el golden set sellado de los rule contracts.
4. **El motor consume, no redefine**: la lógica (sim, render, UI) va en contratos
   aparte cuyos fixtures NO leen el GAME.md real (fixtures sintéticos), de modo que la
   capa de datos evoluciona sin romper oráculos de lógica.

Con eso, la cadena de custodia de los datos queda completa: `touch_only` impide editar
el GAME.md fuera de contrato, `tests_sha256` congela al validador de los datos, y el
no-drift ata datos ↔ artefacto.

## Fricciones conocidas (y mitigación)

- **Doble toolchain**: los validadores KDD son Python, los del protocolo Node. En CI se
  corren ambos (el paso "Run project test suite" del workflow usa el runner del
  proyecto; los validadores Python del template quedan como están).
- **Gate CCDD Nivel 2 y targets JS**: `check_signature` del MCP es AST Python puro y no
  parsea JS; el `budget` sobre perfiles/motor JS no es exigible por el gate real. El
  veredicto práctico para lo JS es Nivel 1 + oráculos congelados (`node --test`).
- **Un GAME.md no es un nodo OKF**: usa el YAML subset de `yaml-min` y no lleva
  frontmatter OKF; vive fuera de `knowledge/` como artefacto hermano. Documentá su
  existencia con un nodo como este, no lo metas al índice OKF.
- **Sellado de los datos en sí**: el lint valida rangos/refs pero no impide ediciones
  válidas silenciosas. Si el proyecto necesita datos golden, game-protocol provee el
  sellado del documento (`dataSha256` en el frontmatter + `tools/game-seal.js` para
  calcularlo; la regla `data-seal` del lint verifica el sello) — el análogo directo de
  `tests_sha256`.

## Ejemplo real

MiniTown (city-sim cozy): perfil `minitown` que compone al perfil `voxel`, GAME.md con
arte voxel + balance de simulación/economía/clima como colecciones, cinco contratos KDD
con oráculos sellados sobre la capa de datos y la lógica, no-drift en el gate. Repo:
https://github.com/MauricioPerera/MiniTown
