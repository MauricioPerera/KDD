# <Nombre del proyecto> — Definición

<!--
COMO USAR ESTA PLANTILLA (borrar este bloque en tu copia):

1. Copiala a la raiz de tu proyecto: cp TEMPLATE-DEFINITION.md DEFINITION.md
2. Completala EN CONVERSACION con un humano, no de una sentada vos solo --
   ver la skill .agents/skills/kdd-definir/SKILL.md (reglas + proceso).
3. Cuando cierre, seguis a PLAN (knowledge/metodologia-ejecucion.md): recien
   ahi se fasean las capacidades objetivo en tareas atomicas y arranca el
   primer task contract (knowledge/contracts/TEMPLATE-task-contract.md).
4. DEFINITION.md no es un nodo OKF ni lo valida ningun gate -- es
   documentacion previa a que exista el primer contrato. Podes borrarlo o
   archivarlo despues sin que nada se rompa.
-->

## Qué es

<Una frase. Qué hace el proyecto, para quién.>

## Arquitectura

<Solo si aplica. Componentes y como se comunican entre si. Si hay un core
reusable + interfaces/pieles (ej. una libreria + CLI + UI que la
consumen), decilo asi de explicito -- esa forma condiciona como se van a
dividir despues las tareas atomicas.>

## Capacidades objetivo

<Lista de capacidades, SIN fasear salvo que ya sepas el orden real de
implementacion (fasear de mas, temprano, suele ser una decision inventada
sin evidencia).>

- <capacidad 1>
- <capacidad 2>

## Por qué es un caso válido / motivación real

<Que problema resuelve y para quien. Si es un caso de estudio de la
metodologia, la motivacion real tiene que ser ademas de eso -- dogfooding
vacio (un proyecto que solo existe para "probar el metodo") es mas debil
que uno con valor externo genuino.>

## Fuera de alcance

<Explicito, en negativo. Decisiones que NO se toman aca porque son de
implementacion (nombres de comandos, stack exacto de una pieza menor,
layout de UI) -- esas se definen en el contrato de la tarea que las
necesite, no aca.>

- <fuera de alcance 1>
- <fuera de alcance 2>
