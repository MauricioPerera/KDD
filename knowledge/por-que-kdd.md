---
type: 'Concept'
title: 'Por que KDD (vs. Spec Kit, BMAD, o solo un AGENTS.md)'
description: 'Posicionamiento honesto: que hace distinto a KDD frente a las alternativas mas conocidas para desarrollar con agentes de IA, y en que casos NO conviene usarlo.'
tags: ['ccdd', 'okf', 'posicionamiento', 'reference']
---

# Por que KDD

Pregunta directa que este repo nunca respondia en un solo lugar: si ya existe
`AGENTS.md`, GitHub `spec-kit` o `BMAD-METHOD`, ¿para que otro metodo mas?
Esto no es marketing — es una comparacion honesta, con los tradeoffs reales
de elegir KDD, escrita para que quien evalua adoptarlo decida con evidencia,
no con promesas.

## La diferencia de fondo: quien verifica, y con que

Las tres alternativas mas conocidas resuelven un problema similar
(coordinar agentes de IA sobre una base de codigo) con una estrategia de
verificacion distinta:

- **`AGENTS.md`** (convencion, no herramienta): un archivo markdown con
  instrucciones de build/test/estilo que un agente lee al arrancar. Cero
  mecanismo propio de verificacion — el agente hace lo que el archivo
  dice, y confiar en que lo hizo bien depende de tests que YA existian en
  el proyecto (si los hay) o de que un humano revise el diff.
- **GitHub `spec-kit`**: flujo de comandos (`/specify`, `/plan`, `/tasks`)
  que gira una idea en lenguaje natural hacia una especificacion y un plan
  de implementacion estructurados, antes de escribir codigo. Fuerte en
  definir intent con precision; la verificacion de que el codigo generado
  cumple ese intent sigue siendo, en su mayoria, revision humana o del
  propio agente — no hay un gate mecanico e independiente que corra
  aparte del agente que escribio el codigo.
- **`BMAD-METHOD`**: orquesta personas/roles (analista, PM, arquitecto,
  dev, QA) como agentes separados con memoria de proyecto compartida.
  Fuerte en dividir el trabajo por rol y mantener contexto entre fases;
  la garantia de correctitud depende de que el rol "QA" (otro agente LLM)
  juzgue bien el trabajo del rol "dev" — sigue siendo juicio de un modelo,
  no un chequeo determinista.

**KDD apuesta a un punto distinto: que el agente que implementa NUNCA sea
el mismo que define "esto esta bien".** Concretamente:

1. **Oraculo congelado por hash, no por confianza.** El test que decide si
   una tarea paso se escribe ANTES de delegar la implementacion, y su
   hash SHA256 queda sellado en el contrato (`tests_sha256`). Si el
   implementador reescribe el test para que pase, el hash no coincide y
   el gate lo detecta — sin que un LLM tenga que "notar" el intento. Ver
   [validacion.md](./validacion.md), campo `tests_sha256`.
2. **Perimetro como dato verificable, no como instruccion de prompt.**
   `touch_only` en el frontmatter declara que archivos puede tocar la
   tarea; `scripts/validate_perimeter.py` compara contra el diff real
   (`git diff --name-only`) y rompe con `OUT_OF_PERIMETER` si el
   implementador se salio del alcance — otra vez, mecanico, no un "por
   favor no toques otros archivos" que el agente puede ignorar.
3. **El gate que cierra el circulo: correr el test_command de verdad.**
   Hasta la incorporacion de
   [`test-command-gate`](./contracts/test-command-gate.md), un contrato
   podia declarar `test_command` y nunca correrlo en CI — la promesa
   quedaba escrita pero no verificada. Ahora `Nivel 1` ejecuta cada
   `test_command` y falla si algun exit code no es 0: el hueco entre "el
   contrato dice que hay tests" y "los tests realmente pasan" queda
   cerrado por un gate, no por confianza.
4. **Cero LLM en el camino obligatorio.** Los 10 gates de Nivel 1 son
   Python puro, sin red ni subprocess salvo la unica excepcion documentada
   (el gate de arriba, cuyo intent ES correr un comando). Nada del
   veredicto "paso"/"no paso" depende de que un modelo interprete bien un
   prompt de evaluacion — evita la clase de fragilidad de "el juez LLM lo
   dejo pasar esta vez".

## Lo que KDD NO tiene (todavia) y las alternativas si

Ser honesto incluye decir donde KDD esta atras:

- **Sin flujo de refinamiento de intent tan pulido como `spec-kit`.**
  `spec-kit` invierte mucho en la fase de ir de idea difusa a spec
  precisa via conversacion guiada; KDD asume que quien escribe el
  contrato ya sabe bastante bien que quiere (el trabajo de afinar el
  intent pasa ANTES, no esta instrumentado dentro de la herramienta).
- **Sin orquestacion de roles como `BMAD-METHOD`.** KDD tiene un solo rol
  explicito con nombre (PM que delega a devs efimeros); no modela
  analista/arquitecto/QA como agentes separados con su propia memoria de
  proyecto — quien quiera esa division de trabajo la arma por fuera.
- **Mas pesado que `AGENTS.md`.** Escribir un contrato completo (intent,
  firma, invariantes, ejemplos, oraculo congelado, sellado por hash) es
  mas trabajo previo que soltar un agente con un `AGENTS.md` de 20 lineas
  y confiar en que ya sabe que hacer. Para un cambio trivial de una
  linea, ese overhead no se justifica — KDD rinde en tareas donde
  "que el agente se salga del alcance sin que nadie lo note" es un riesgo
  real (proyectos grandes, equipos, agentes con permisos amplios).

## Cuando conviene KDD y cuando no

- **Conviene** cuando el costo de una tarea "aparentemente verde" pero mal
  hecha es alto (produccion, equipos, dinero real de por medio) y hay
  tiempo de escribir el contrato antes de delegar.
- **No conviene** para prototipado rapido de una sola persona donde la
  friccion de escribir contrato+oraculo antes de cada cambio supera el
  riesgo de que el agente se equivoque — ahi `AGENTS.md` solo, o
  `spec-kit` para ordenar el intent, alcanzan.

## Ver tambien

- [validacion.md](./validacion.md) — referencia normativa completa de los
  gates y el ciclo de vida de un contrato.
- [quickstart.md](./quickstart.md) — como se ve esto en la practica, paso
  a paso.
- [metodologia-ejecucion.md](./metodologia-ejecucion.md) — como el PM
  delega a agentes efimeros y verifica el resultado.
