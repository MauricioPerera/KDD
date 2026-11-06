---
type: 'Concept'
title: 'Remediacion de perimetro, controles y CI'
description: 'Contratos y criterios para integrar gobierno, mejorar perfiles y revisar cambios confiables.'
tags: ['audit', 'ci', 'security', 'quality']
---

# Alcance

El punto de partida es main `f1faf516b0622bd5d91ffb7321580127530aa948`.
La rama parte del candidato independiente `0d6b66d099e63349ac3920863c73952a646fb9cf`
que integra main y KG-1 a KG-5; esa integracion no implica que el PR 158 se
haya fusionado o que su CI mas reciente haya pasado. Los contratos y oraculos
KG se conservan. El baseline original de complejidad OKF `369712a` ya habia
sido aprobado; su cherry-pick conserva sus archivos, reindexados sobre esta base.

- KG-1 exige perimetro en cierre e historial. KG-2 a KG-5 hacen visibles y
  verifican controles requeridos cuando estan soportados; no son un sandbox.
- [Perfil post-apply](contracts/init-post-apply-profile.md): comparar perfiles
  con el mismo arbol, inventario y entorno en Windows/Ubuntu, conservar todos
  los intentos y confirmar CI real; no elevar 600 s ni omitir pruebas.
- [Revision exacta](contracts/trusted-ci-change-review.md): la primera
  instalacion no puede autoautorizarse mediante el guard antiguo. Cualquier
  excepcion o cambio de protecciones requiere aprobacion puntual posterior.
- [Complejidad OKF](contracts/validate-okf-complexity.md): conservar tipos de
  grupo y comparar presupuesto y comportamiento con el main vigente.

# Integracion posterior de main

El PR 158 se integro despues mediante `292f0e53aa50c7836300fafb389baa45dc176f08`.
La rama conserva esa ascendencia y los cuatro artefactos de cierre incorporados.
Las pruebas y el CI del head combinado deben validarse por separado; las
pasadas anteriores no acreditan el nuevo arbol.

# Criterios

Conservar Ubuntu/Windows, Board, coverage de IDs, dos pasadas completas y
controles anteriores. Verificar pruebas nuevas, gates estructurales, ambos
sistemas y limites. Un timeout o fallo remoto se registra, no se convierte en
exito. Baseline humano de nuevos contratos y cambios de oraculo antes de
implementar el perfil y el guard; runtime confiable y protecciones externos
siguen sujetos a revision independiente.
