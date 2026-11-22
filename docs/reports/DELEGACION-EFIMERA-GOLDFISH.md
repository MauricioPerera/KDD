# Piloto de delegación efímera con Goldfish

El 13 de noviembre de 2026 se repitió la batería de delegación con tres tareas
históricas de KDD. Cada copia Git tenía un índice y almacén propios, sin remoto
y con una revisión de profundidad. Los agentes recibieron los contratos y
oráculos previos a la implementación. Cada revisor e implementador inició con
contexto fresco. Las instrucciones acotaron las lecturas. El sistema de archivos
del host seguía accesible.

La guía de [delegación efímera](../../knowledge/delegacion-efimera-goldfish.md)
usa los resultados de este piloto.

## Tiempos y verificación

| Tarea y baseline del piloto | Tamaño del cambio histórico | Revisión | Implementación inicial | Casos por pasada final |
| --- | --- | ---: | ---: | ---: |
| Pages · [`b39bec5`](https://github.com/MauricioPerera/KDD/commit/b39bec5ca00a8a5555b0c4f4f67dfefc8d2a5258) | 1 archivo, 4 líneas | 251,89 s | 109,71 s | 4 |
| Validador OKF · [`369712a`](https://github.com/MauricioPerera/KDD/commit/369712a82b0ff17292b456cd77a20de56e790aa2) | 1 archivo, 98 líneas | 283,06 s | 262,81 s | 30 |
| Oráculos multiarchivo · [`22a5b93`](https://github.com/MauricioPerera/KDD/commit/22a5b9342608c01e2ec6c3800b9984059d395aa6) | 8 archivos, 359 líneas | 385,58 s | 1.105,61 s | 36 |

El tamaño suma líneas añadidas y retiradas en la implementación histórica.
La medición de revisión va del despacho a la escritura del informe. La de
implementación incluye las pruebas del agente. Algunas sesiones se solaparon.
Las tres entregas finales pasaron dos ejecuciones dirigidas en Windows nativo
y Ubuntu sobre WSL con Python 3.11.15. Se comprobó que cada pasada conservaba
los mismos IDs para su encargo.

## Controles reproducidos

| Encargo | Falso verde | Comprobación que lo distingue |
| --- | --- | --- |
| Pages | El workflow contenía el comando de instalación como comentario y ejecutaba `true`. Pasaban las cuatro pruebas. | Parsear el YAML y comprobar qué ejecuta el paso. El discovery con el entorno de despliegue comprueba el efecto. |
| OKF | Una caché por ruta devolvía datos anteriores dentro del mismo proceso. Pasaban las 30 pruebas. | Cambiar el índice entre dos llamadas de la API. El resultado debe incluir el nuevo `ORPHAN`. |
| Multiarchivo | Un auditor modificado aceptaba una fila con cero casos si otra compensaba el total. Pasaban las 14 integraciones del oráculo. | Con Git real, falsificar el recibo y recalcular su sello. El auditor de referencia y la entrega experimental lo rechazaron. |

Un cuarto Goldfish detectó tres problemas en paquetes derivados en 305,14 s.
Una instrucción pedía editar una ruta fuera del perímetro, otro paquete omitía
el contrato que seleccionaba el medidor y un tercero contenía el paso ficticio
de Pages. Un implementador nuevo escaló la contradicción de alcance, pidió
una decisión concreta y dejó intacto su paquete. Al retirar el contrato previo
de OKF en una copia completa, el medidor devolvió éxito con el filtro del
contrato ausente. Con el contrato presente, reportó cuatro excesos.

## Hallazgos del traspaso y del cierre

- **Contexto incompleto.** El ensamblador de la tarea grande agotó los 13.000
  tokens disponibles, omitió los dos contratos de la tarea y truncó la entrada
  del usuario. El comando devolvió éxito. La lista explícita de lecturas
  entregó los contratos a los agentes. Un perfil experimental con fuentes
  requeridas entregó las cuatro fuentes completas y abortó con código 2
  ante una huella errónea, en ambos sistemas.
- **Prueba vecina.** Las 35 pruebas iniciales de multiarchivo pasaron, pero
  `test_acceptance_rejects_binary_newline_mutation` falló en ambos sistemas.
  La entrega había omitido la lista de rutas que el llamador exige comparar
  byte a byte. Una mutación CRLF a LF en un proyecto sin diario daba
  `acceptance_approved`.
  El implementador corrigió esa ruta compartida y verificó el caso en unos
  71 s de retrabajo. Las dos pasadas finales incluyeron la prueba, con 36 casos
  por sistema y pasada. También pasaron 24 casos de los módulos de aceptación,
  calidad e inventario binario en cada sistema.

La muestra cubre una tarea por tamaño y un revisor por encargo principal.
Los tiempos son observaciones locales. El piloto no midió CI completo ni
comparó el desempeño con sesiones que heredaran la conversación. El informe
de ejecución, los diffs y los logs se conservaron en el directorio local de
evidencia del piloto. Los SHA de la tabla identifican los insumos históricos.

## Encargos por nivel de riesgo

| Riesgo | Encargo de revisión |
| --- | --- |
| Bajo | Una lectura breve del encargo, el perímetro y la evidencia. Si hay una garantía que verificar, buscar el contraejemplo más plausible. Para una edición elegible, aplicar el [flujo ligero](../../knowledge/odd-lightweight.md). |
| Medio | Al menos un revisor independiente comprueba el encargo contra el código real y busca falsos verdes en las garantías afectadas. Pide una prueba vecina si detecta un consumidor compartido. |
| Alto | Dos revisores independientes cubren las perspectivas del protocolo. Dar un encargo explícito sobre las fronteras de confianza, compatibilidad y efectos de fallo. En tareas de varias etapas, fijar qué evidencia permite pasar de una a otra. |

## Matriz de pruebas vecinas

Al preparar la spec y al leer el diff, el orquestador recorre las llamadas,
los artefactos y las configuraciones que usan la garantía afectada. Elige un
caso dirigido por consumidor o variante
relevante y registra qué protege. Si un mismo caso cubre varios consumidores,
anotar la cobertura. Ante un nuevo hallazgo, conservar el fallo y repetir el
caso en la entrega corregida junto con el conjunto dirigido original.

| Si el cambio toca | Ejecutar también |
| --- | --- |
| Helper compartido, API, formato o recibo | Una integración por ruta pública afectada. Probar productor y consumidor juntos, variantes histórica y actual y rechazo de un artefacto inválido. |
| Aprobación, inventario, sellos o comparación de bytes | Los flujos que pasan identidad o integridad por el mismo punto, incluidos los perfiles sin la función nueva. Probar un caso válido y una alteración rechazada. |
| Discovery, dependencias o configuración de ejecución | El consumidor real en su entorno de ejecución. Cuando la garantía sea detectar una dependencia ausente, comprobar el fallo sin ella y el inventario esperado con el lock. |
| Refactor de un validador | La suite anterior de la API y la CLI, el presupuesto aplicable y al menos un comportamiento sensible al cambio. Si se promete releer archivos, modificar la entrada entre dos llamadas en el mismo proceso. |

Registrar la base, el candidato o la huella del diff, los insumos entregados,
quién revisó y las salidas reales de las pruebas del candidato. Enlazar los
hallazgos, su resolución y cualquier comprobación pendiente. Las pruebas vecinas
complementan la [validación habitual](../../knowledge/validacion.md), incluidas las dos pasadas
en Ubuntu y Windows del CI aplicable. Guardar la evidencia antes de cerrar
la sesión o retirar la copia. Para medir el coste de revisión, anotar inicio y
entrega del informe, y medir aparte la implementación y el retrabajo.
