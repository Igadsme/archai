from __future__ import annotations

from pathlib import Path

from .model import GENERATABLE_OPS, ArchitectureGenerator


def architecture_tokens(architecture):
    return [GENERATABLE_OPS.index(node.op) for node in architecture.nodes if node.op in GENERATABLE_OPS]


def fit_generator(model: ArchitectureGenerator, architectures, *, conditions=None, epochs: int = 20,
                  lr: float = 1e-3, seed: int = 0):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    history = []
    for _ in range(epochs):
        losses = []
        for index, example in enumerate(architectures):
            if isinstance(example, tuple):
                architecture, condition_values = example
            else:
                architecture = example
                condition_values = conditions[index] if conditions is not None else (0.0,) * model.config.condition_dim
            tokens = architecture_tokens(architecture)
            if not tokens:
                continue
            target = torch.tensor(tokens, dtype=torch.long).unsqueeze(0)
            one_hot = F.one_hot(target, num_classes=len(GENERATABLE_OPS)).float()
            _, hidden = model.encoder(one_hot)
            latent = model.latent_projection(hidden[-1])
            if len(condition_values) != model.config.condition_dim:
                raise ValueError("every generator condition must match config.condition_dim")
            condition = torch.tensor([condition_values], dtype=torch.float32)
            sequence_logits = model.forward(latent, condition, teacher_tokens=target).transpose(1, 2)
            loss = F.cross_entropy(sequence_logits, target)
            losses.append(loss)
        if not losses:
            raise ValueError("at least one architecture with a generatable operation is required")
        loss = torch.stack(losses).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return history


def fit_sequences(model: ArchitectureGenerator, sequences, *, conditions=None, epochs: int = 20,
                  lr: float = 1e-3, seed: int = 0, optimizer=None, weights=None):
    """Teacher-forced maximum likelihood on token sequences with prior latents.

    Latents are drawn from N(0, I) at every step, matching `sample_tokens`, so the
    decoder learns p(tokens | condition) rather than an autoencoder whose sampling
    distribution would differ from training. Returns per-epoch losses.
    """
    import torch
    import torch.nn.functional as F
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if not sequences:
        raise ValueError("at least one sequence is required")
    vocabulary = model.config.vocabulary
    targets = torch.tensor([[vocabulary.index(token) for token in sequence] for sequence in sequences],
                           dtype=torch.long)
    condition_rows = conditions if conditions is not None else [(0.0,) * model.config.condition_dim] * len(sequences)
    if len(condition_rows) != len(sequences) or any(len(row) != model.config.condition_dim for row in condition_rows):
        raise ValueError("every condition must match config.condition_dim")
    condition_tensor = torch.tensor([list(row) for row in condition_rows], dtype=torch.float32)
    weight_tensor = (torch.tensor(weights, dtype=torch.float32) if weights is not None
                     else torch.ones(len(sequences)))
    generator = torch.Generator().manual_seed(seed)
    optimizer = optimizer or torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    history = []
    for _ in range(epochs):
        latent = torch.randn(len(sequences), model.config.latent_dim, generator=generator)
        logits = model.forward(latent, condition_tensor, teacher_tokens=targets)
        per_token = F.cross_entropy(logits.transpose(1, 2), targets, reduction="none").mean(dim=1)
        loss = (per_token * weight_tensor).sum() / weight_tensor.sum()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    return history


def generation_metrics(candidates):
    from archai_core.validation import validate_architecture
    valid = []
    for candidate in candidates:
        try:
            valid.append(validate_architecture(candidate))
        except Exception:
            continue
    hashes = {candidate.content_hash() for candidate in valid}
    op_signatures = {tuple(node.op for node in candidate.nodes) for candidate in valid}
    return {"validity": len(valid) / len(candidates) if candidates else 0.0,
            "uniqueness": len(hashes) / len(valid) if valid else 0.0,
            "diversity": len(op_signatures) / len(valid) if valid else 0.0}


def save_checkpoint(model, path: str | Path, metadata: dict):
    import torch
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "metadata": metadata}, path)


def load_checkpoint(model, path: str | Path):
    import torch
    payload = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(payload["state_dict"])
    return payload["metadata"]
