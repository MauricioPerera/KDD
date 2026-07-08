"""Detector de ciclos en grafo de connections de un workflow.

Implementacion del contrato check-graph (C22): detecta ciclos,
los reporta en forma canonica, sin lanzar ante entrada malformada.
"""


def find_graph_cycles(connections: dict) -> list:
    """Detecta ciclos en connections ({nodo: [destinos]}).

    Devuelve lista de violaciones legibles (vacia = sin ciclos).
    Cada violacion: prefijo 'connections:' + camino en forma canonica.
    Forma canonica: rotado al nodo lexicograficamente menor, nodo inicial
    repetido al final. Violaciones ordenadas. Pura, determinista, nunca lanza.
    """

    # Validar que connections sea dict
    if not isinstance(connections, dict):
        return []

    # Mapeo: nodo -> [destinos]. Validar cada entrada.
    graph = {}
    for node, dests in connections.items():
        # Validar: nodo debe ser string
        if not isinstance(node, str):
            continue
        # Validar: destinos debe ser lista
        if not isinstance(dests, list):
            continue
        # Validar: todos los destinos deben ser strings
        valid_dests = [d for d in dests if isinstance(d, str)]
        if len(valid_dests) != len(dests):
            # Hay destinos no-string; saltar esta entrada pero continuar
            continue
        graph[node] = valid_dests

    # DFS con 3 colores: 0=WHITE (no visitado), 1=GRAY (en pila), 2=BLACK (done)
    color = {node: 0 for node in graph}
    parent = {}  # parent[node] = nodo previo en el DFS
    cycles_canonical = set()  # Set de ciclos en forma canonica (deduplicar)

    def dfs(node, stack_path):
        """DFS recursivo. stack_path = lista de nodos desde raiz a node."""
        color[node] = 1  # GRAY

        for dest in graph[node]:
            if dest not in graph:
                # Destino no tiene entrada en graph; ignorar (no es ciclo)
                continue

            if color[dest] == 0:
                # WHITE: recursiva
                dfs(dest, stack_path + [dest])
            elif color[dest] == 1:
                # GRAY: back edge = ciclo encontrado
                # Ciclo: desde dest (primera ocurrencia en pila) hasta node
                dest_idx = stack_path.index(dest)
                cycle_part = stack_path[dest_idx:]  # Nodos del ciclo sin repetir inicial
                # Rotar a forma canonica: empezar en nodo lex menor
                min_node = min(cycle_part)
                min_idx = cycle_part.index(min_node)
                rotated = cycle_part[min_idx:] + cycle_part[:min_idx]
                canonical = rotated + [rotated[0]]  # Repetir el primer nodo al final
                # Convertir a string y agregar a set (deduplicar)
                cycle_str = " -> ".join(canonical)
                cycles_canonical.add(cycle_str)

        color[node] = 2  # BLACK

    # Iterar cada nodo no visitado como raiz
    for start_node in graph:
        if color[start_node] == 0:
            dfs(start_node, [start_node])

    # Convertir a lista de violaciones, ordenadas
    violations = [f"connections: ciclo {cycle}" for cycle in sorted(cycles_canonical)]
    return violations
