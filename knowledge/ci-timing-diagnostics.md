---
type: 'Concept'
title: 'Diagnostico de tiempos antes de repartir las suites de CI'
description: 'Publicar una proyeccion de duraciones existentes sin alterar pruebas ni atribuirle aceptacion.'
tags: ['ci', 'performance', 'diagnostics']
---

# Primera entrega

Cinco CI del 16 de noviembre dieron medianas de 14:38 en Ubuntu y 41:24 en
Windows, con uno a tres segundos de cola. En el [main medido](https://github.com/MauricioPerera/KDD/actions/runs/43913368575),
contratos y suites consumieron 694 de 755 s en Ubuntu y 1.742 de 1.834 s en
Windows. El [post-init](postinit-windows-runtime.md) terminó antes.

# Forma y limites del diagnostico

El [contrato](contracts/ci-timing-diagnostics.md) define formato, evidencia
incompleta y límites de publicación. El JSON proyecta métricas de los
recibos del [runtime fijado](contracts/ci-trusted-execution.md). Conserva
los hashes y estados de cada fuente. Las pasadas se identifican por hash
sin inferir su orden. La cobertura sigue en la primera.

Los tiempos de procesos concurrentes y del controlador pueden solaparse.
La proyección complementa los [inventarios](pages-ci-inventory.md) y la
[aprobación de calidad](quality-approval.md).

# Secuencia posterior

1. Aplicar la [revisión del baseline](baseline-risk-review.md) y reunir tres
   CI completos del mismo SHA, con runtime, inventario e intentos fallidos.
2. Comparar costos por módulo, fase y runner antes de ajustar el paralelismo.
3. Definir contratos separados para repartir suites o comandos. Conservar
   Ubuntu, Windows, dos pasadas y la conciliación de IDs y cobertura.
