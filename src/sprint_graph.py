"""Iterative graph operations for trusted, validated sprint snapshots."""
from collections import deque


def reverse_edges(graph):
    reverse = {key: [] for key in graph}
    for key, dependencies in graph.items():
        for dependency in dependencies:
            reverse[dependency].append(key)
    return {key: sorted(values) for key, values in reverse.items()}


def reachable(graph, start):
    """Reachable IDs, including start; handles cycles without recursion."""
    seen = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(graph[current])
    return seen


def cyclic_components(graph):
    """Kosaraju SCCs, iterative in both passes. Return only cyclic components."""
    seen, order = set(), []
    for start in sorted(graph):
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(graph[start]))]
        while stack:
            current, children = stack[-1]
            child = next(children, None)
            if child is None:
                order.append(current)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(graph[child])))
    reverse = reverse_edges(graph)
    assigned, cycles = set(), []
    for start in reversed(order):
        if start in assigned:
            continue
        component, pending = [], [start]
        assigned.add(start)
        while pending:
            current = pending.pop()
            component.append(current)
            for child in reverse[current]:
                if child not in assigned:
                    assigned.add(child)
                    pending.append(child)
        if len(component) > 1 or start in graph[start]:
            cycles.append(sorted(component))
    return sorted(cycles)


def satisfied_tasks(tasks, graph):
    """Only proven leaves and proven successors can enter the satisfied set."""
    reverse = reverse_edges(graph)
    remaining = {key: len(deps) for key, deps in graph.items()}
    pending = deque(key for key in graph if not remaining[key])
    satisfied = set()
    while pending:
        key = pending.popleft()
        task = tasks[key]
        proof = task.get('evidence')
        qualifies = (task['status'] == 'done' and proof is not None and proof['valid']
                     and not any(b['status'] == 'open' for b in task.get('blockers', [])))
        if not qualifies:
            continue
        satisfied.add(key)
        for child in reverse[key]:
            remaining[child] -= 1
            if remaining[child] == 0:
                pending.append(child)
    return satisfied


def inherited_priorities(tasks, pending_graph, selected, satisfied, ranks):
    """Track selected pending descendants for both ordering and explanation."""
    unlocks = {key: set() for key in tasks}
    for source in sorted(selected - satisfied):
        if tasks[source]['status'] == 'cancelled':
            continue
        for ancestor in reachable(pending_graph, source) - {source}:
            unlocks[ancestor].add(source)
    priorities = {}
    for key, targets in unlocks.items():
        own = ranks[tasks[key]['priority']]
        rank = max([own] + [ranks[tasks[t]['priority']] for t in targets])
        sources = sorted(t for t in targets if ranks[tasks[t]['priority']] == rank) if rank > own else []
        priorities[key] = (rank, sources, sorted(targets))
    return priorities
