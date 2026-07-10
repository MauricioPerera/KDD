---
type: 'Task Contract'
title: 'Checker de ciclos del grafo de un workflow'
description: 'Funcion pura que detecta ciclos en las connections de un workflow y los reporta en forma canonica: la propiedad global del grafo que el rule contract del dominio declaro code_only.'
tags: ['ccdd', 'workflow', 'grafo', 'ciclos', 'example']

task: check-graph
intent: "Detectar ciclos en el grafo de connections de un workflow y reportarlos en forma canonica."
target: src/check_workflow_graph.py
signature: "def find_graph_cycles(connections: dict) -> list:"
test_command: "python -m unittest tests/test_check_graph.py"
budget:
  max_cyclomatic_complexity: 10
  max_nesting_depth: 4
tests: "tests/test_check_graph.py"
tests_sha256: "c1740621cadbb77bba8919efe78e20d0f50368cbcafc9473ff42774d676858c4"
touch_only: ['src/check_workflow_graph.py']
deps_allowed: []
forbids: ['network', 'subprocess']
---

# Contract: check-graph

## Intent
Cerrar por codigo la frontera #1 del dominio
[workflow_policy](../data_models/workflow_policy.md): "ningun ciclo entre nodos" es una
propiedad GLOBAL del grafo, inexpresable por las familias declarativas (lo declaro
`code_only` el rule-set de C20). Con este contrato, el dominio workflows queda con la
dupla completa: datos para lo uniforme, codigo para lo global. Spec:
`specs/CONTRACT-22-graph-cycles.md`.

## Interface
```python
def find_graph_cycles(connections: dict) -> list:
    """Detecta ciclos en connections ({nodo: [destinos]}). Devuelve una lista de
    violaciones legibles (vacia = sin ciclos), cada una con prefijo 'connections:' y
    el camino del ciclo en forma canonica. Pura, determinista, nunca lanza."""
```

## Invariants
- Forma canonica: cada ciclo se reporta UNA vez, rotado para empezar en su nodo
  lexicograficamente menor, con el nodo inicial repetido al final
  ("connections: ciclo A -> B -> A"). Violaciones ordenadas.
- Convergencia NO es ciclo (el diamante A->B->D, A->C->D da cero violaciones).
- Destinos que no tienen entrada propia en el dict no generan ciclo ni error.
- Entradas malformadas (connections no-dict; destinos no-lista; nodos/destinos no-string)
  se SALTAN sin lanzar — la forma del workflow la valida el rule contract del dominio
  (C20); este checker solo decide ciclos. Lo malformado no oculta ciclos reales del resto.
- Determinista; stdlib puro; sin red; sin subprocess; mensajes ASCII.

## Examples
- `find_graph_cycles({"A": ["B"], "B": ["A"]})` -> 1 violacion con `A -> B -> A`
  (el caso FRONTERA del golden de C20, ahora visible por codigo).
- `find_graph_cycles({"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []})` -> `[]`.
- `find_graph_cycles({"A": ["A"]})` -> 1 violacion con `A -> A`.

## Do / Don't
- DO: DFS/coloreo iterativo o recursivo chico, dentro del budget.
- DO: forma canonica exacta del oraculo (rotacion al menor + ordenamiento).
- DON'T: red, IO, dependencias fuera de stdlib; validar la FORMA del workflow (eso es del
  rule contract); tocar tests/, knowledge/, examples/ ni el motor/gate.

## Tests
(Los tests estan en `tests/test_check_graph.py`, autorados por el orquestador y
congelados: aciclicos, diamante, self-loop, ciclo de 2 en ambas declaraciones, ciclo
largo, componente desconectado, multiples ciclos canonicos ordenados, malformados sin
lanzar y sin ocultar ciclos reales, determinismo.)

## Constraints
- PARAR y reportar si... el oraculo congelado fuera internamente contradictorio (p. ej.
  una forma canonica ambigua en algun caso) o exigiera algo imposible con stdlib puro.
