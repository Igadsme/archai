from __future__ import annotations

from dataclasses import dataclass

from .schema import Architecture


@dataclass(frozen=True)
class ValidationError(ValueError):
    errors: tuple[str, ...]

    def __str__(self) -> str:
        return "; ".join(self.errors)


def validate_architecture(architecture: Architecture) -> Architecture:
    errors: list[str] = []
    ids = [node.id for node in architecture.nodes]
    if len(ids) != len(set(ids)):
        errors.append("node ids must be unique")
    by_id = {node.id: node for node in architecture.nodes}
    for edge in architecture.edges:
        if edge.source not in by_id or edge.target not in by_id:
            errors.append(f"edge references unknown node: {edge.source}->{edge.target}")
        if edge.source == edge.target:
            errors.append(f"self-cycle at {edge.source}")
    edge_pairs = [(edge.source, edge.target) for edge in architecture.edges]
    if len(edge_pairs) != len(set(edge_pairs)):
        errors.append("duplicate edges are not allowed")
    incoming = {node_id: 0 for node_id in by_id}
    outgoing = {node_id: 0 for node_id in by_id}
    adjacency = {node_id: [] for node_id in by_id}
    for edge in architecture.edges:
        if edge.source in by_id and edge.target in by_id:
            incoming[edge.target] += 1
            outgoing[edge.source] += 1
            adjacency[edge.source].append(edge.target)
    roots = [node.id for node in architecture.nodes if node.op == "input"]
    sinks = [node.id for node in architecture.nodes if node.op == "output"]
    if len(roots) != 1 or len(sinks) != 1:
        errors.append("architecture must contain exactly one input and one output")
    if roots and incoming[roots[0]]:
        errors.append("input node cannot have incoming edges")
    if sinks and outgoing[sinks[0]]:
        errors.append("output node cannot have outgoing edges")
    if any(node.op not in {"input", "output"} and incoming[node.id] == 0 for node in architecture.nodes):
        errors.append("non-input nodes must have an incoming path")
    if any(node.op not in {"input", "output"} and outgoing[node.id] == 0 for node in architecture.nodes):
        errors.append("non-output nodes must have an outgoing path")
    state = {node_id: 0 for node_id in by_id}
    def visit(node_id: str) -> None:
        if state[node_id] == 1:
            errors.append("graph contains a cycle")
            return
        if state[node_id] == 2:
            return
        state[node_id] = 1
        for child in adjacency[node_id]:
            visit(child)
        state[node_id] = 2
    for node_id in by_id:
        visit(node_id)
    if roots and not errors:
        # A graph is compiled as a typed tensor graph. Every merge must combine
        # equal channel counts; implicit projection layers would change the
        # architecture being evaluated and are therefore forbidden here.
        for node_id, parents in ((node_id, [edge.source for edge in architecture.edges if edge.target == node_id]) for node_id in by_id):
            if len(parents) > 1 and len({by_id[parent].channels for parent in parents}) > 1:
                errors.append(f"fanin channel mismatch at {node_id}")
    if roots and sinks and not errors:
        seen = set()
        stack = [roots[0]]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(adjacency[current])
        if sinks[0] not in seen:
            errors.append("output is not reachable from input")
    if errors:
        raise ValidationError(tuple(dict.fromkeys(errors)))
    return architecture.with_id()
