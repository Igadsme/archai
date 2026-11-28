"""CPU-feasible training data for the API generator: chain graphs labelled with analytical FLOPs.

The corpus is random GENERATABLE_OPS chains (the vocabulary `ArchitectureGenerator.sample()` builds), each
labelled with its exact analytical FLOP count. The generator learns p(ops | FLOP budget); it learns nothing
about accuracy. FLOPs are expressed as a fraction of an all-conv3x3 chain at the same input spec, so the
condition means the same thing for any input size.
"""
from __future__ import annotations

import random

from archai_core.schema import Architecture, Edge, Node, TensorSpec

from .model import GENERATABLE_OPS

ENCODING_NAME = "analytical_flops_budget_v1"
N_BINS = 6
CONDITION_DIM = 2 + N_BINS  # conditioned flag, FLOPs fraction, one-hot bin


def chain(ops, spec: TensorSpec, output_classes: int) -> Architecture:
    nodes = [Node(id="input", op="input", channels=spec.channels)]
    edges = []
    previous = "input"
    for index, op in enumerate(ops):
        node_id = f"node_{index}"
        nodes.append(Node(id=node_id, op=op, channels=spec.channels))
        edges.append(Edge(source=previous, target=node_id))
        previous = node_id
    nodes.append(Node(id="output", op="output", channels=spec.channels))
    edges.append(Edge(source=previous, target="output"))
    return Architecture(nodes=nodes, edges=edges, input_spec=spec, output_classes=output_classes,
                        generator_version="archai-generator")


def flops_of(ops, spec: TensorSpec, output_classes: int) -> int:
    from archai_compiler.metrics import analytical_metrics
    return analytical_metrics(chain(ops, spec, output_classes)).flops


def reference_flops(length: int, spec: TensorSpec, output_classes: int) -> int:
    """FLOPs of the most expensive chain in the space (every op conv3x3)."""
    return flops_of(["conv3x3"] * length, spec, output_classes)


def bin_of(fraction: float, n_bins: int = N_BINS) -> int:
    return min(n_bins - 1, max(0, int(min(1.0, max(0.0, fraction)) * n_bins)))


def bin_ceiling(index: int, n_bins: int = N_BINS) -> float:
    return (index + 1) / n_bins


def encode_bin(index: int | None, n_bins: int = N_BINS) -> tuple[float, ...]:
    """Condition for "FLOPs fraction within bin `index`"; `None` is the unconditioned (all-zero) code."""
    if index is None:
        return (0.0,) * CONDITION_DIM
    one_hot = [0.0] * n_bins
    one_hot[index] = 1.0
    return (1.0, bin_ceiling(index, n_bins), *one_hot)


def bin_for_budget(fraction: float, n_bins: int = N_BINS) -> int:
    """Largest bin whose ceiling fits under the budget (bin 0 when even that is above it)."""
    return max(0, min(n_bins - 1, int(min(1.0, max(0.0, fraction)) * n_bins + 1e-9) - 1))


def encode_budget(fraction: float | None) -> tuple[float, ...]:
    """Condition for a FLOPs budget (fraction of the reference); `None` means unconditioned."""
    return encode_bin(None if fraction is None else bin_for_budget(fraction))


def build_corpus(size: int, *, length: int = 8, seed: int = 0, spec: TensorSpec | None = None,
                 output_classes: int = 10) -> list[dict]:
    """Random chains with a per-sample op mixture, so cheap and expensive chains are both well covered."""
    rng = random.Random(seed)
    spec = spec or TensorSpec(channels=3, height=32, width=32)
    reference = reference_flops(length, spec, output_classes)
    corpus = []
    for _ in range(size):
        weights = [rng.gammavariate(0.7, 1.0) for _ in GENERATABLE_OPS]
        ops = rng.choices(GENERATABLE_OPS, weights=weights, k=length)
        flops = flops_of(ops, spec, output_classes)
        corpus.append({"ops": ops, "flops": flops, "flops_fraction": flops / reference,
                       "bin": bin_of(flops / reference)})
    return corpus


def budget_adherence(model, *, budgets, samples: int, length: int, spec: TensorSpec, output_classes: int,
                     seed: int = 0) -> list[dict]:
    """For each budget fraction: share of sampled chains within budget, conditioned vs. unconditioned."""
    reference = reference_flops(length, spec, output_classes)
    rows = []
    for index, budget in enumerate(budgets):
        outcome = {}
        for label, condition in (("conditioned", encode_budget(budget)), ("unconditioned", encode_budget(None))):
            sequences = model.sample_tokens(samples, steps=length, seed=seed + index, condition=condition)
            within = sum(flops_of(ops, spec, output_classes) / reference <= budget for ops in sequences)
            outcome[label] = within / samples
        rows.append({"budget_fraction": budget, "within_budget_conditioned": outcome["conditioned"],
                     "within_budget_unconditioned": outcome["unconditioned"]})
    return rows
