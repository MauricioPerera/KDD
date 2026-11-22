# Impacto de MCP Events en KDD

**Resultado del piloto, 22 de noviembre de 2026.** MCP Events automatiza el
traspaso entre el orquestador y agentes en máquinas distintas. El beneficio
comprobado es poder avanzar al recibir el evento de respuesta y reconstruir
cada traspaso por sus identificadores. El costo observado fue **4,91 s más
de coordinación externa en promedio** en una tarea con artefacto fijo. KDD
conserva la responsabilidad de comprobar la entrega con el contrato y el
oráculo. [Piloto](../../examples/mcp-events-kdd/README.md) ·
[Evidencia estructurada](mcp-events-kdd-2026-11-22/evidencia.json)

## Impacto en el flujo de trabajo

| Etapa | Responsabilidad de KDD | Aporte observado de MCP Events |
| --- | --- | --- |
| Preparar | El orquestador fija el SHA, ensambla el contexto y verifica el contrato, el perímetro y el oráculo sellado. | El encargo viaja al ejecutor con identidad de tarea e hilo. |
| Implementar | El ejecutor efímero devuelve una propuesta. El orquestador controla qué se aplica en la copia de trabajo. | `task.received` despierta al ejecutor del VPS. `task.replied` permite leer su respuesta una vez. |
| Revisar | Goldfish evalúa un encargo de solo lectura con contexto fresco. El orquestador conserva el dictamen y comprueba los contraejemplos. | Otro encargo despierta al revisor local en el mismo hilo, con sus propios IDs de tarea y de evento. |
| Verificar y promover | KDD ejecuta el oráculo, comprueba las huellas y el perímetro y registra las salidas. El protocolo de baseline exige una revisión proporcional al riesgo y aprobación humana del SHA exacto. | Los recibos del receptor y los IDs permiten rastrear la entrega y el avance. |

El receptor valida la firma y la suscripción antes de anunciar el evento. El
orquestador observa ese registro por SSH y comprueba el par, el hilo y la tarea
antes de recuperar el resultado. La firma respalda la procedencia del aviso.
El sello, el diff y las salidas de prueba respaldan el resultado técnico.
`verified` es el cierre de este piloto. La revisión `review_ready` y la
aprobación se rigen por el flujo de baseline de KDD.
[Delegación efímera](../../knowledge/delegacion-efimera-goldfish.md) ·
[Revisión del baseline](../../knowledge/baseline-risk-review.md) ·
[Aprobación de calidad](../../knowledge/quality-approval.md)

## Evidencia y costo

Se repitió `commit-message-length-config` desde
`eae041fe86582fbf323c1f9dd14420318b55d29a` con el diff del candidato
`9a522357e6414100d6ddc5954b734d4a826281c3`. El ejecutor `gpt-5.6-sol` en
el VPS recibió la propuesta exacta que debía reproducir. Goldfish usó
`qwen3.8-9b-distill` en la misma instancia de LM Studio. El verificador
comprobó la igualdad del diff, el blob Git, el prompt y el cuerpo HTTP
completo de las cuatro inferencias. La segunda pareja invirtió el orden.
[Contrato de la tarea](../../knowledge/contracts/commit-message-length-config.md) ·
[Entradas y salidas de la comparación](mcp-events-kdd-2026-11-22/evidencia.json)

| Orden | Flujo | Total | Llamada a Qwen | Codex activo | Coordinación externa | KDD local |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Directo | 79,19 s | 64,30 s | 3,76 s | 1,55 s | 9,59 s |
| 2 | MCP Events | 42,66 s | 15,21 s | 12,46 s | 7,27 s | 7,72 s |
| 3 | MCP Events | 34,93 s | 15,51 s | 10,71 s | 5,87 s | 2,83 s |
| 4 | Directo | 23,28 s | 14,92 s | 3,66 s | 1,78 s | 2,92 s |

- **Coordinación.** El promedio directo fue 1,66 s y el de MCP Events, 6,57 s.
  En Goldfish, el tramo fuera de LM Studio pasó de 0,02 s a 2,97 s. La
  coordinación externa suma el arranque del stream y el tiempo de transporte y
  espera fuera de los intervalos activos.
- **Modelos y tiempo total.** La métrica de Qwen cubre del POST a la respuesta
  completa de LM Studio. La de Codex mide la ejecución activa en el VPS,
  incluidas sus herramientas. Qwen devolvió 206 tokens en cada corrida. La
  primera llamada tardó 64,30 s y las otras tres, entre 14,92 s y 15,51 s.
  Una sola tarea con dos corridas por ruta da evidencia del costo observado
  de coordinación. Estimar el efecto general sobre el tiempo total o el
  costo de CI requiere otra muestra.
- **Intervención y calidad.** Cada corrida tuvo un arranque y cero
  intervenciones posteriores gracias al arnés compartido. Las cuatro
  reprodujeron el fallo de la base y pasaron dos veces 32 pruebas. Cada
  corrida con eventos registró cuatro callbacks firmados y dos lecturas
  disparadas por callback. El costo de preparar los worktrees y los
  servicios quedó fuera del cronómetro.

En la comparación anterior al diff fijo, Goldfish objetó un guard correcto
porque trató `type(True) == int` como verdadero. Se conservó el dictamen y
se comprobó con Python que el candidato rechazaba `True` y admitía `0`.
Este caso muestra por qué el orquestador debe poder contrastar un hallazgo del
modelo con una prueba dirigida antes de resolverlo.
[Comprobación independiente registrada](mcp-events-kdd-2026-11-22/evidencia.json)

## Criterio de adopción propuesto

El flujo directo tiene menos componentes para encargos que se pueden
despachar y esperar desde un solo entorno. MCP Events encaja como opción
cuando KDD debe coordinar ejecutores o revisores en entornos distintos y el
valor de despertar agentes y rastrear entregas compensa el costo operativo
del receptor, las suscripciones y el acceso al registro.

Para evaluar una adopción más amplia, llevar estos controles al siguiente piloto.

1. **Conservar identidad y evidencia.** Vincular la base, el candidato o su
   diff, el contrato, el oráculo y las salidas de verificación con el revisor
   y los IDs del encargo. Aplicar las perspectivas y el número de revisores
   que correspondan al riesgo.
2. **Probar recuperación en KDD.** Interrumpir el orquestador entre guardar
   el resultado y avanzar a la siguiente etapa. Reentregar el mismo evento
   y comprobar que se retome el encargo con la evidencia original y una sola
   transición. El piloto actual sigue el journal en una sesión y guarda
   evidencia parcial si esa sesión se interrumpe.
3. **Medir en tareas distintas.** Repetir con cambios de tamaños y riesgos
   diferentes. Registrar preparación de servicios, coordinación, ejecución
   de agentes y verificaciones de KDD como intervalos distintos. Comparar
   también fallos de entrega y retrabajo con el flujo directo.

La evidencia versionada conserva huellas de las capturas originales, además
de los tiempos y los IDs usados para comprobar el piloto. Los registros
íntegros y el verificador de la medición quedaron en el directorio local de
evidencia. [Extracto verificable](mcp-events-kdd-2026-11-22/evidencia.json)
