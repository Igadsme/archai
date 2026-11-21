from __future__ import annotations

import re

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture

_EDGE = re.compile(r"(?:(?<=\|)|^)([^~|]+)~(\d+)\|")
_OPS = {"nor_conv_1x1": "conv1x1", "nor_conv_3x3": "conv3x3", "avg_pool_3x3": "avg_pool3x3",
        "skip_connect": "skip", "none": "none"}


def architecture_from_string(architecture_string: str, *, input_spec: TensorSpec,
                             output_classes: int = 10) -> Architecture:
    """Convert the NAS-Bench-201 cell string into a valid, canonical DAG.

    Each benchmark edge becomes an explicitly represented operation node and
    each intermediate destination gets a typed merge node. This preserves the
    edge/operator encoding used for lookup while making tensor fan-in explicit.
    """
    groups = [group for group in architecture_string.split("+") if group]
    matches = [match for group in groups for match in _EDGE.findall(group)]
    if not matches or not groups:
        raise ValueError("invalid NAS-Bench-201 architecture string")
    nodes = [Node(id="input", op="input", channels=input_spec.channels)]
    edges: list[Edge] = []
    by_target: dict[int, list[str]] = {}
    index = 0
    for target, group in enumerate(groups, start=1):
        group_matches = _EDGE.findall(group)
        if not group_matches:
            raise ValueError(f"missing NAS-Bench-201 edges for destination {target}")
        for operation, source_text in group_matches:
            if operation not in _OPS:
                raise ValueError(f"unsupported NAS-Bench-201 operation: {operation}")
            source = int(source_text)
            if source < 0 or source > 3:
                raise ValueError(f"invalid NAS-Bench-201 source node: {source}")
            source_id = "input" if source == 0 else f"merge_{source}"
            operation_id = f"edge_{index}"
            nodes.append(Node(id=operation_id, op=_OPS[operation], channels=input_spec.channels))
            edges.append(Edge(source=source_id, target=operation_id))
            by_target.setdefault(target, []).append(operation_id)
            index += 1
    for target in sorted(by_target):
        merge_id = f"merge_{target}"
        nodes.append(Node(id=merge_id, op="skip", channels=input_spec.channels))
        edges.extend(Edge(source=op_id, target=merge_id) for op_id in by_target[target])
    nodes.append(Node(id="output", op="output", channels=input_spec.channels))
    last = f"merge_{max(by_target)}"
    edges.append(Edge(source=last, target="output"))
    return validate_architecture(Architecture(nodes=nodes, edges=edges, input_spec=input_spec,
        output_classes=output_classes, search_space="nasbench201", metadata={"encoding": architecture_string}))
