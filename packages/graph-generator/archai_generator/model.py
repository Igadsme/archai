from __future__ import annotations

from dataclasses import dataclass

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture

GENERATABLE_OPS = ("conv3x3", "conv1x1", "avg_pool3x3", "skip")


@dataclass(frozen=True)
class GeneratorConfig:
    latent_dim: int = 32
    hidden_dim: int = 64
    max_nodes: int = 8
    condition_dim: int = 8


class ArchitectureGenerator:
    """Research model skeleton with an explicit trainable autoregressive interface.

    Training data and checkpoint paths are intentionally supplied by the caller;
    the class never invents a checkpoint or claims that it has been trained.
    """
    def __init__(self, config: GeneratorConfig = GeneratorConfig()):
        try:
            import torch
            from torch import nn
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install the 'ml' extra to use the generator") from exc
        self.config = config
        self.encoder = nn.GRU(input_size=len(GENERATABLE_OPS), hidden_size=config.hidden_dim, batch_first=True)
        self.context = nn.Linear(config.latent_dim + config.condition_dim, config.hidden_dim)
        self.decoder = nn.Linear(config.hidden_dim, len(GENERATABLE_OPS))

    def parameters(self):
        return list(self.encoder.parameters()) + list(self.context.parameters()) + list(self.decoder.parameters())

    def state_dict(self):
        return {"encoder": self.encoder.state_dict(), "context": self.context.state_dict(),
                "decoder": self.decoder.state_dict(), "config": self.config.__dict__}

    def load_state_dict(self, state):
        self.encoder.load_state_dict(state["encoder"])
        self.context.load_state_dict(state["context"])
        self.decoder.load_state_dict(state["decoder"])

    def forward(self, latent, condition, steps: int | None = None):
        import torch
        steps = steps or self.config.max_nodes
        context = torch.tanh(self.context(torch.cat([latent, condition], dim=-1))).unsqueeze(1)
        sequence = context.expand(-1, steps, -1)
        return self.decoder(sequence)

    def sample(self, *, seed: int = 0, condition: tuple[float, ...] = (0.0,) * 8,
               input_spec: TensorSpec | None = None, output_classes: int = 10) -> list[Architecture]:
        import torch
        generator = torch.Generator().manual_seed(seed)
        spec = input_spec or TensorSpec(channels=3, height=32, width=32)
        latent = torch.randn(1, self.config.latent_dim, generator=generator)
        task = torch.tensor([condition], dtype=torch.float32)
        logits = self.forward(latent, task).squeeze(0)
        results = []
        for offset in range(self.config.max_nodes):
            op = GENERATABLE_OPS[int(torch.argmax(logits[offset]).item())]
            nodes = [Node(id="input", op="input", channels=spec.channels)]
            edges = []
            previous = "input"
            for index in range(offset + 1):
                node_id = f"node_{index}"
                nodes.append(Node(id=node_id, op=op, channels=spec.channels))
                edges.append(Edge(source=previous, target=node_id))
                previous = node_id
            nodes.append(Node(id="output", op="output", channels=spec.channels))
            edges.append(Edge(source=previous, target="output"))
            results.append(validate_architecture(Architecture(nodes=nodes, edges=edges,
                input_spec=spec, output_classes=output_classes, generator_version="archai-generator")))
        return results
