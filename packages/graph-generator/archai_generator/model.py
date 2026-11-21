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
        self.latent_projection = nn.Linear(config.hidden_dim, config.latent_dim)
        self.context = nn.Linear(config.latent_dim + config.condition_dim, config.hidden_dim)
        self.decoder_rnn = nn.GRU(input_size=len(GENERATABLE_OPS), hidden_size=config.hidden_dim, batch_first=True)
        self.decoder = nn.Linear(config.hidden_dim, len(GENERATABLE_OPS))

    def parameters(self):
        return (list(self.encoder.parameters()) + list(self.latent_projection.parameters()) +
                list(self.context.parameters()) + list(self.decoder_rnn.parameters()) + list(self.decoder.parameters()))

    def state_dict(self):
        return {"encoder": self.encoder.state_dict(), "latent_projection": self.latent_projection.state_dict(),
                "context": self.context.state_dict(), "decoder_rnn": self.decoder_rnn.state_dict(),
                "decoder": self.decoder.state_dict(), "config": self.config.__dict__}

    def load_state_dict(self, state):
        self.encoder.load_state_dict(state["encoder"])
        self.latent_projection.load_state_dict(state["latent_projection"])
        self.context.load_state_dict(state["context"])
        self.decoder_rnn.load_state_dict(state["decoder_rnn"])
        self.decoder.load_state_dict(state["decoder"])

    def forward(self, latent, condition, steps: int | None = None, teacher_tokens=None):
        import torch
        import torch.nn.functional as F
        steps = steps or self.config.max_nodes
        context = torch.tanh(self.context(torch.cat([latent, condition], dim=-1))).unsqueeze(0)
        if teacher_tokens is None:
            sequence = torch.zeros(latent.shape[0], steps, len(GENERATABLE_OPS), device=latent.device)
        else:
            start = torch.zeros(teacher_tokens.shape[0], 1, dtype=torch.long, device=teacher_tokens.device)
            shifted = torch.cat([start, teacher_tokens[:, :-1]], dim=1)
            sequence = F.one_hot(shifted, num_classes=len(GENERATABLE_OPS)).float()
        decoded, _ = self.decoder_rnn(sequence, context)
        return self.decoder(decoded)

    def sample(self, *, seed: int = 0, condition: tuple[float, ...] = (0.0,) * 8,
               input_spec: TensorSpec | None = None, output_classes: int = 10) -> list[Architecture]:
        import torch
        generator = torch.Generator().manual_seed(seed)
        spec = input_spec or TensorSpec(channels=3, height=32, width=32)
        latent = torch.randn(1, self.config.latent_dim, generator=generator)
        task = torch.tensor([condition], dtype=torch.float32)
        context = torch.tanh(self.context(torch.cat([latent, task], dim=-1))).unsqueeze(0)
        previous = torch.zeros(1, 1, len(GENERATABLE_OPS))
        generated_ops = []
        for _ in range(self.config.max_nodes):
            decoded, context = self.decoder_rnn(previous, context)
            logits = self.decoder(decoded[:, -1])
            probabilities = torch.softmax(logits, dim=-1)
            operation_index = int(torch.multinomial(probabilities, 1, generator=generator).item())
            generated_ops.append(GENERATABLE_OPS[operation_index])
            previous = torch.nn.functional.one_hot(torch.tensor([[operation_index]]), num_classes=len(GENERATABLE_OPS)).float()
        results = []
        for offset in range(self.config.max_nodes):
            nodes = [Node(id="input", op="input", channels=spec.channels)]
            edges = []
            previous = "input"
            for index in range(offset + 1):
                node_id = f"node_{index}"
                nodes.append(Node(id=node_id, op=generated_ops[index], channels=spec.channels))
                edges.append(Edge(source=previous, target=node_id))
                previous = node_id
            nodes.append(Node(id="output", op="output", channels=spec.channels))
            edges.append(Edge(source=previous, target="output"))
            results.append(validate_architecture(Architecture(nodes=nodes, edges=edges,
                input_spec=spec, output_classes=output_classes, generator_version="archai-generator")))
        return results
