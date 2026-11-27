from __future__ import annotations

from .engine import TrainingConfig, train_model


def train_candidate(architecture, train_loader, validation_loader, config: TrainingConfig, *, checkpoint_path=None):
    from archai_compiler.pytorch_compiler import compile_architecture
    model = compile_architecture(architecture)
    return train_model(model, train_loader, validation_loader, config, checkpoint_path=checkpoint_path)
