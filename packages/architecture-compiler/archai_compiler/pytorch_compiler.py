from __future__ import annotations

from collections import defaultdict, deque

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture


def compile_architecture(architecture: Architecture, *, input_channels: int | None = None,
                         fan_in_reduction: str | None = None):
    """Compile only the allow-listed graph into a torch.nn.Module.

    PyTorch is imported lazily so schema/benchmark tooling remains usable in a
    lightweight environment. The compiler deliberately rejects unsupported
    tensor fan-in instead of executing dynamic user code.
    """
    validate_architecture(architecture)
    reduction = fan_in_reduction or architecture.metadata.get("fan_in_reduction", "mean")
    if reduction not in {"mean", "sum"}:
        raise ValueError("fan_in_reduction must be 'mean' or 'sum'")
    try:
        import torch
        from torch import nn
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("install the 'ml' extra to compile PyTorch models") from exc
    by_id = {node.id: node for node in architecture.nodes}
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in architecture.edges:
        incoming[edge.target].append(edge.source)
    # Do not trust serialized node order. Compilation order is a topological
    # property, not an incidental JSON ordering.
    indegree = {node.id: len(incoming[node.id]) for node in architecture.nodes}
    children = defaultdict(list)
    for edge in architecture.edges:
        children[edge.source].append(edge.target)
    queue = deque([node.id for node in architecture.nodes if indegree[node.id] == 0])
    order = []
    while queue:
        current = queue.popleft()
        order.append(by_id[current])
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    modules = nn.ModuleDict()
    channels = {node.id: (input_channels or architecture.input_spec.channels)
                for node in architecture.nodes if node.op == "input"}
    for node in order:
        if node.op == "input":
            continue
        parents = incoming[node.id]
        in_ch = channels[parents[0]]
        if node.op == "avg_pool3x3":
            modules[node.id] = nn.AvgPool2d(3, stride=1, padding=1)
            channels[node.id] = in_ch
            continue
        if node.op in {"output", "skip", "none"}:
            channels[node.id] = in_ch
            continue
        kernel = node.kernel_size if node.op == "conv3x3" else 1
        layers: list[nn.Module] = [nn.Conv2d(in_ch, node.channels, kernel,
                                             padding=kernel // 2, bias=True)]
        if node.normalization == "batch":
            layers.append(nn.BatchNorm2d(node.channels))
        elif node.normalization == "layer":
            layers.append(nn.GroupNorm(1, node.channels))
        if node.activation == "relu":
            layers.append(nn.ReLU())
        elif node.activation == "gelu":
            layers.append(nn.GELU())
        modules[node.id] = nn.Sequential(*layers)
        channels[node.id] = node.channels

    class CompiledArchitecture(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = modules
            self.head = nn.LazyLinear(architecture.output_classes)

        def forward(self, x):
            values = {next(n.id for n in architecture.nodes if n.op == "input"): x}
            for node in order:
                if node.op == "input":
                    continue
                sources = incoming[node.id]
                if not sources:
                    raise RuntimeError(f"node {node.id} has no input")
                value = values[sources[0]]
                if len(sources) > 1:
                    value = sum(values[s] for s in sources)
                    if reduction == "mean":
                        value = value / len(sources)
                if node.op == "none":
                    value = torch.zeros_like(value)
                elif node.op not in {"output", "skip"}:
                    value = self.layers[node.id](value)
                values[node.id] = value
            out = values[next(n.id for n in architecture.nodes if n.op == "output")]
            return self.head(out.flatten(1))

    return CompiledArchitecture()
