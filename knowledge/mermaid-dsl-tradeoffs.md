---
type: 'Concept'
title: 'Mermaid como DSL: por que NO sirve para automatizacion pero SI para KDD'
description: 'Analisis de las ventajas/desventajas de Mermaid como lenguaje generado por IA, y por que las mismas propiedades que lo descartan como UI de un motor de automatizacion son exactamente las que lo hacen encajar en KDD.'
tags: ['diagramas', 'mermaid', 'ccdd', 'okf', 'reference']
---

# Mermaid como DSL — por que no sirve para automatizacion pero si para KDD

Analisis de una pregunta concreta: ¿sirve Mermaid como DSL cuando quien lo genera es una IA?
La respuesta depende enteramente de para que se lo use. Complementa
[diagram-contract-spec](./diagram-contract-spec.md) (que documenta el CONTRATO de verificacion)
con el POR QUE de fondo: que hace a Mermaid util o inutil segun el contexto.

## Mermaid como UI interactiva de una plataforma de automatizacion (n8n, Zapier, Make): NO

Mermaid es una libreria de renderizado (texto -> SVG), no un canvas interactivo. No tiene nodos
arrastrables, paneles de configuracion por nodo, ni estado de ejecucion en vivo
(running/success/error). Por eso las plataformas de automatizacion reales usan librerias
dedicadas (React Flow, Rete.js, JointJS): necesitan esas affordances de edicion que Mermaid
nunca fue disenado para dar.

## Mermaid generado por IA como DSL de automatizacion: desventajas concretas

Encontradas de primera mano construyendo `mermaid-gate` (parser real, 20 tipos de diagrama) y
`scripts/validate_diagrams.py` (parsers propios en Python puro, 4 tipos) en este mismo repo:

1. **Sintaxis fragil sin loop de feedback**: los LLM generan Mermaid invalido con frecuencia
   (corchetes/parentesis sin cerrar, caracteres especiales sin escapar en labels, tipo de flecha
   equivocado). Sin un gate que valide y devuelva el error al modelo, buena parte de lo generado
   no parsea.
2. **Sin semantica nativa de automatizacion**: Mermaid no tiene concepto de "trigger", "params de
   una accion", "policy de retry", "referencia a credencial". Todo terminaria como texto libre
   dentro del label de un nodo (stringly-typed). La IA tendria que inventar una convencion (ej.
   JSON embebido en el label) que despues hay que re-parsear con tooling propio.
3. **Mezcla de versiones/dialectos**: la sintaxis de Mermaid cambio entre versiones mayores
   (classDiagram, gitGraph, etc.); un LLM entrenado con docs mezcladas de varias versiones genera
   con frecuencia una mezcla invalida para el renderer objetivo.
4. **IDs de nodo sin identidad estable**: son strings libres; si la IA regenera el diagrama, los
   ids pueden cambiar entre versiones y romper cualquier config externa que referencie un nodo por
   id — no hay diffing/versionado confiable a ese nivel.
5. **Es de una sola direccion**: Mermaid fue disenado para renderizar, no para round-trip. Si un
   humano edita visualmente en un canvas y hay que serializar de vuelta a Mermaid (y viceversa),
   no hay AST/schema formal que lo sostenga — hay que construirlo aparte (ver mas abajo, es
   exactamente lo que hizo este repo).

Conclusion para ese caso de uso: como DSL *generado por IA* para definir workflows reales, es un
mal fit. La falta de estructura tipada obliga a reinventar un schema por fuera de Mermaid — en
ese momento conviene generar directamente ese schema (JSON/YAML) y usar Mermaid solo para
*visualizar* el resultado, nunca como fuente de verdad.

## Mermaid dentro de KDD: SI, y no es por ser "un lindo diagrama"

Las mismas propiedades que lo descartan para automatizacion son, invertidas, exactamente las
tres que KDD exige a TODO artefacto (task contracts, rule contracts, specs) — y que un canvas
visual (Lucidchart, JointJS, React Flow) no puede dar:

1. **Diffable en git**: es texto plano. Un PR que cambia el diagrama muestra que nodo/edge se
   agrego o saco, igual que cualquier contrato de este repo. Un formato binario o JSON-con-
   coordenadas de un canvas no da eso de forma legible.
2. **Escribible por un agente sin GUI**: el caso de uso central de KDD es delegar a agentes
   efimeros headless. Un agente puede *emitir* texto Mermaid como parte de su entregable; no
   puede manejar un canvas interactivo. Es el unico formato de diagrama que un agente puede
   producir de forma realista en un pipeline sin humano.
3. **Verificable por maquina**: por tener gramatica real y parseable, se puede chequear contra un
   contrato de forma deterministica — literalmente lo que hacen `scripts/validate_diagrams.py`
   (este repo, Python puro, 4 tipos) y el proyecto hermano `mermaid-gate`
   (github.com/MauricioPerera/mermaid-gate, Node, parser real, 20 tipos). Un `.png` de un
   diagrama no se puede verificar; Mermaid si. Esto es la misma doctrina que el resto de KDD:
   si no lo puede verificar una maquina, no esta realmente especificado.

Bonus menor: renderiza nativo en GitHub/GitLab sin infraestructura extra — coherente con el
principio de [OKF-SPEC](./OKF-SPEC.md) de que si podes usar `cat`, lo podes leer.

## La distincion en una linea

Para automatizacion hace falta *editar* interactivamente (Mermaid no da eso). Para KDD hace
falta *versionar + verificar* texto (Mermaid da exactamente eso, igual que el resto del
sistema). No es la misma pregunta, y por eso la respuesta es distinta en cada caso.
