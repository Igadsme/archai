from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 1
    learning_rate: float = 1e-3
    weight_decay: float = 0.0
    gradient_accumulation_steps: int = 1
    early_stopping_patience: int = 0
    mixed_precision: bool = False
    seed: int = 0
    device: str = "cpu"


@dataclass(frozen=True)
class TrainingResult:
    status: str
    best_validation_loss: float
    epochs_completed: int
    wall_clock_seconds: float
    history: tuple[dict[str, float], ...]
    checkpoint_path: str | None = None


def _seed_everything(seed: int) -> None:
    import torch
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _batch_loss(model, batch, criterion, device):
    inputs, targets = batch
    return criterion(model(inputs.to(device)), targets.to(device))


def train_model(model, train_loader, validation_loader, config: TrainingConfig,
                *, checkpoint_path: str | Path | None = None, resume_path: str | Path | None = None,
                criterion=None, on_epoch_end: Callable[[dict[str, float]], None] | None = None) -> TrainingResult:
    """Train a classifier with reproducible seeds, accumulation, AMP, and recovery.

    Load/save payloads contain only a state dict and JSON-safe metadata. The
    engine never deserializes arbitrary model objects. `on_epoch_end` receives
    each epoch's history row after its checkpoint is written; an exception it
    raises stops training (used for cooperative job cancellation).
    """
    import torch
    from torch import nn

    if config.epochs <= 0 or config.gradient_accumulation_steps <= 0:
        raise ValueError("epochs and accumulation steps must be positive")
    _seed_everything(config.seed)
    device = torch.device(config.device)
    model.to(device)
    criterion = criterion or nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    start_epoch, best_loss, stale, history = 0, float("inf"), 0, []
    if resume_path:
        payload = torch.load(resume_path, map_location=device, weights_only=True)
        model.load_state_dict(payload["model_state"])
        optimizer.load_state_dict(payload["optimizer_state"])
        start_epoch = int(payload["epoch"]) + 1
        best_loss = float(payload["best_validation_loss"])
        history = list(payload.get("history", []))
    scaler = torch.amp.GradScaler("cuda", enabled=config.mixed_precision and device.type == "cuda")
    started = time.monotonic()
    status = "completed"
    for epoch in range(start_epoch, config.epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_total = 0.0
        train_count = 0
        for step, batch in enumerate(train_loader):
            with torch.autocast(device_type=device.type, enabled=config.mixed_precision and device.type == "cuda"):
                loss = _batch_loss(model, batch, criterion, device) / config.gradient_accumulation_steps
            scaler.scale(loss).backward()
            if (step + 1) % config.gradient_accumulation_steps == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            batch_size = batch[0].shape[0]
            train_total += float(loss.detach()) * config.gradient_accumulation_steps * batch_size
            train_count += batch_size
        if train_count and (step + 1) % config.gradient_accumulation_steps:
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        model.eval()
        validation_total = 0.0
        validation_count = 0
        correct = 0
        with torch.no_grad():
            for batch in validation_loader:
                inputs, targets = batch
                outputs = model(inputs.to(device))
                loss = criterion(outputs, targets.to(device))
                validation_total += float(loss) * inputs.shape[0]
                validation_count += inputs.shape[0]
                correct += int((outputs.argmax(dim=1) == targets.to(device)).sum())
        validation_loss = validation_total / max(1, validation_count)
        row = {"epoch": float(epoch), "train_loss": train_total / max(1, train_count),
               "validation_loss": validation_loss, "validation_accuracy": correct / max(1, validation_count)}
        history.append(row)
        if validation_loss < best_loss:
            best_loss, stale = validation_loss, 0
            if checkpoint_path:
                path = Path(checkpoint_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                torch.save({"epoch": epoch, "model_state": model.state_dict(),
                            "optimizer_state": optimizer.state_dict(),
                            "best_validation_loss": best_loss, "history": history,
                            "config": asdict(config)}, path)
        else:
            stale += 1
        if on_epoch_end is not None:
            on_epoch_end(dict(row))
        if stale and config.early_stopping_patience and stale >= config.early_stopping_patience:
            status = "early_stopped"
            break
    return TrainingResult(status, best_loss, len(history), time.monotonic() - started,
                          tuple(history), str(checkpoint_path) if checkpoint_path else None)
