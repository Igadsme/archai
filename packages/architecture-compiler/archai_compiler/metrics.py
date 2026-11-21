from __future__ import annotations

from dataclasses import dataclass

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture


@dataclass(frozen=True)
class AnalyticalMetrics:
    parameters: int
    flops: int
    activation_memory_bytes: int


def analytical_metrics(architecture: Architecture) -> AnalyticalMetrics:
    validate_architecture(architecture)
    h, w = architecture.input_spec.height, architecture.input_spec.width
    params = 0
    flops = 0
    by_id = {node.id: node for node in architecture.nodes}
    incoming = {node.id: [] for node in architecture.nodes}
    for edge in architecture.edges:
        incoming[edge.target].append(edge.source)
    channels = {node.id: architecture.input_spec.channels for node in architecture.nodes if node.op == "input"}
    # validation ensures acyclicity; process in a stable topological order.
    pending = [node.id for node in architecture.nodes if not incoming[node.id]]
    order = []
    while pending:
        current = pending.pop(0)
        order.append(current)
        for child in (edge.target for edge in architecture.edges if edge.source == current):
            if child not in order and all(parent in order for parent in incoming[child]):
                pending.append(child)
    for node_id in order:
        node = by_id[node_id]
        if node.op == "input":
            continue
        in_channels = channels[incoming[node_id][0]]
        if node.op in {"conv3x3", "conv1x1"}:
            kernel = node.kernel_size if node.op == "conv3x3" else 1
            params += in_channels * node.channels * kernel * kernel + node.channels
            flops += 2 * h * w * in_channels * node.channels * kernel * kernel
            channels[node_id] = node.channels
        elif node.op == "avg_pool3x3":
            flops += h * w * in_channels * 9
            channels[node_id] = in_channels
        else:
            channels[node_id] = in_channels
    max_channels = max(channels.values())
    return AnalyticalMetrics(params, flops, h * w * max_channels * 4)
