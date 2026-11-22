---
type: 'Concept'
title: 'Delegación efímera con Goldfish'
description: 'Preparar, revisar y verificar encargos que un agente nuevo puede resolver con contratos y pruebas vigentes.'
tags: ['metodologia', 'delegacion', 'contexto', 'review']
---

# Delegación efímera con Goldfish

El orquestador conserva el estado de la tarea. Un agente nuevo recibe un
encargo que puede entender y verificar con los artefactos del proyecto. Goldfish
es el revisor de solo lectura que examina el encargo con contexto fresco. Este
flujo concreta SPEC, DELEGAR y VERIFICAR en la [metodología de ejecución](metodologia-ejecucion.md).

## 1. Preparar el contexto mínimo

El orquestador prepara una copia de trabajo identificada por su SHA base y
entrega un encargo breve con estos insumos:

- **Objetivo y garantías.** Estado final observable, criterios de aceptación y
  enlace al contrato de la tarea. Incluir las decisiones vigentes y los contratos
  antecedentes que determinan el resultado, con ruta y SHA o huella comprobable.
- **Perímetro.** Rutas de lectura necesarias, punto de entrada, rutas editables
  según `touch_only` y decisiones internas delegadas. Identificar las pruebas
  congeladas y sus auxiliares aprobados. El implementador puede consultar una
  dependencia directa adicional en su copia y debe dejar constancia de ella.
- **Verificación.** Comando exacto, directorio de ejecución, runtime,
  dependencias y resultado esperado. Si la tarea corrige un defecto, adjuntar
  el fallo de partida que reproduce ese defecto. Incluir los comandos vecinos
  ya identificados y quién los ejecuta.
- **Entrega y escalamiento.** Lugar donde guardar el diff o commit, evidencia
  y dudas. Identificar el SHA del contrato y oráculo aprobado cuando aplique.
  El Goldfish que revisa antes de la aprobación recibe el SHA candidato y su
  base.

Comprobar que cada insumo esencial esté accesible, completo y corresponda a la
versión indicada. Si se ensambla el contexto, comprobar esa lista contra el
manifiesto de [contexto entregado](context-learning-provenance.md). Usar fuentes
requeridas y fijar la huella de los archivos estáticos cuando el perfil lo
permita. Si el ensamblador omite o trunca un insumo esencial, completar el
encargo con enlaces comprobados y verificar de nuevo la entrega. Un aborto de
guardrail se resuelve antes de delegar.

Entregar al revisor y al implementador las decisiones vigentes de su revisión.
El Goldfish empieza por el encargo y después lee los insumos pertinentes.
Cada agente empieza con una sesión fresca y recibe los artefactos del encargo
sin el historial del orquestador. Para cambios en paralelo, usar copias con
escritura independiente y respetar las dependencias entre tareas. Los permisos
efectivos del entorno determinan el aislamiento de archivos y credenciales.

## 2. Revisar según el riesgo

Aplicar los pisos, perspectivas y número de revisores de la
[revisión proporcional](baseline-risk-review.md#riesgo-y-esfuerzo). El tamaño
del diff orienta el tiempo de lectura. El riesgo lo determinan las garantías
que pueden fallar y quién depende de ellas.

La [tabla de encargos por riesgo](../docs/reports/DELEGACION-EFIMERA-GOLDFISH.md#encargos-por-nivel-de-riesgo)
recoge ejemplos de aplicación de ese protocolo.

El informe emite dos juicios. El primero comprueba si un agente puede proceder
sin inventar una decisión. El segundo comprueba si las pruebas distinguen una
implementación válida de una incorrecta. Para cada hallazgo, citar la fuente,
dar el contraejemplo y proponer la comprobación más pequeña que lo discrimine.
Revisar también la causa y la alternativa más simple, según las perspectivas
del protocolo. KDD permite que el agente elija una descomposición interna
cuando la interfaz, el comportamiento y el perímetro ya están fijados.

El orquestador conserva el resultado y resuelve los hallazgos antes de entregar
el encargo aplicable. Para cambios de garantías se aplica la
[aprobación humana del baseline](quality-approval.md). Si cambia el SHA,
comprobar el alcance del [registro de revisión](baseline-risk-review.md#registro-json-v1)
y volver a revisar las garantías que el diff pueda afectar.

## 3. Implementar y escalar

El implementador trabaja dentro del perímetro, ejecuta las pruebas acordadas
y devuelve la entrega con los archivos tocados, decisiones internas, lecturas
adicionales y resultados. Escala al orquestador antes de la acción afectada
si ocurre alguno de estos casos:

- Falta una decisión vigente, las fuentes se contradicen o una instrucción
  requiere una ruta fuera de `touch_only`.
- El comando falla por entorno o da verde sin comprobar la garantía. Registrar
  comando, directorio, error o contraejemplo y el insumo necesario para repetir.
- La solución exige cambiar una garantía, un oráculo congelado, un runtime
  aprobado o una protección. Identificar qué cambio exige revisión y usar el
  proceso de aprobación aplicable.

En el escalamiento incluir la ruta o referencia, el resultado observado, la
decisión exacta que falta y qué parte del trabajo sigue siendo verificable.
El orquestador corrige el entorno o el encargo y registra la resolución. Si se
delega de nuevo, entregar el paquete corregido y la evidencia del estado actual.

## 4. Verificar las pruebas vecinas

Elegir una prueba por consumidor o variante relevante y registrar qué
protege. Las pruebas vecinas complementan la [validación habitual](validacion.md).
La [matriz de pruebas vecinas](../docs/reports/DELEGACION-EFIMERA-GOLDFISH.md#matriz-de-pruebas-vecinas)
reúne los controles y sus requisitos de evidencia.

El [piloto con tres tareas reales](../docs/reports/DELEGACION-EFIMERA-GOLDFISH.md)
documenta por qué estos controles se aplican al encargo, al oráculo y a los
consumidores vecinos.

El [piloto con MCP Events](../docs/reports/KDD-MCP-EVENTS-IMPACTO.md) mide
la coordinación entre máquinas con el mismo cambio y encargo de revisión.
En el mismo piloto se verificó [reanudar el hilo y reconocer una reentrega](../docs/reports/KDD-MCP-EVENTS-IMPACTO.md#recuperación-del-orquestador-tras-un-reinicio)
tras reiniciar el proceso que conserva el estado.
