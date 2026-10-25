---
type: 'Concept'
title: 'Especificacion breve del producto de trazabilidad'
description: 'Resultado observable del MVP que une requisitos, contratos, pruebas, commits y evidencia.'
tags: ['requirements', 'traceability', 'product']
---

# Producto: trazabilidad verificable en KDD

Un responsable debe poder conocer que implementacion y evidencia respaldan
cada requisito y detectar cuando esa relacion dejo de estar vigente. La
operacion consulta Git sin modificar el proyecto ni ejecutar su producto.

## Requisitos

- [REQ-001] Definir requisitos con IDs unicos y enlaces explicitos, completos y validables hacia contratos y tareas.
- [REQ-002] Derivar el oraculo, target, aprobacion, commit probado y artefacto desde las fuentes canonicas en Git.
- [REQ-003] Rechazar evidencia alterada o transiciones invalidas, conservando los commits originales del diario importado.
- [REQ-004] Detectar cambios del requisito, sus enlaces o los archivos probados y mostrar evidencia desfasada sin borrar su valor historico.
- [REQ-005] Consultar una revision fija, por defecto main, sin ejecutar pruebas ni cambiar archivos, ramas, indice o estados.
- [REQ-006] Emitir JSON y matriz Markdown coherentes, distinguiendo pendiente, verificado y desfasado; exigir completitud al cerrar.
- [REQ-007] Integrar la comprobacion en la calidad del producto conservando sus otras pruebas, Ubuntu/Windows y las dos pasadas.

## Criterio de entrega

Los [contratos](requirements-traceability.md) verifican un proyecto Git nuevo
con una tarea completada mediante el coordinador real, y mutaciones adversariales
de cada enlace. La huella acredita integridad de relaciones declaradas; su
significado de producto sigue sujeto a revision humana. Este spec describe
el MVP nuevo y no declara verificados los requisitos historicos de KDD.
