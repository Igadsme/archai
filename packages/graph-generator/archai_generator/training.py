from __future__ import annotations

from pathlib import Path

from .model import GENERATABLE_OPS, ArchitectureGenerator


def architecture_tokens(architecture):
    return [GENERATABLE_OPS.index(node.op) for node in architecture.nodes if node.op in GENERATABLE_OPS]


def fit_generator(model: ArchitectureGenerator, architectures, *, epochs: int = 20, lr: float = 1e-3, seed: int = 0):
    import torch
    import torch.nn.functional as F
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    history = []
    for _ in range(epochs):
        losses = []
        for architecture in architectures:
            tokens = architecture_tokens(architecture)
            if not tokens:
                continue
            target = torch.tensor(tokens, dtype=torch.long).unsqueeze(0)
            one_hot = F.one_hot(target, num_classes=len(GENERATABLE_OPS)).float()
            _, hidden = model.encoder(one_hot)
            latent = hidden[-1]
            condition = torch.zeros(1, model.config.condition_dim)
            logits = model.decoder(model.context(torch.cat([latent[:, :model.config.latent_dim], condition], dim=-1)).unsqueeze(1))
            sequence_logits = logits.expand(1, target.shape[1], -1).transpose(1, 2)
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
