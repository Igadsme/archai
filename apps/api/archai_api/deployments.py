"""Local model serving: deployment records plus an in-process inference runtime.

A deployment pins one registered architecture and, optionally, one registered checkpoint whose
SHA-256 is re-verified every time weights are loaded. Without a checkpoint the model runs with
seeded untrained weights and every response says so.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from copy import deepcopy

UNTRAINED_WEIGHTS = "untrained (seeded init, seed=0); outputs carry no learned signal"
MAX_LOADED_MODELS = 8


def weights_label(deployment: dict) -> str:
    model = deployment.get("model")
    if not model:
        return UNTRAINED_WEIGHTS
    return f"checkpoint {model['model_id']}@{model['version']} (sha256 {model['sha256'][:12]}…, verified on load)"


def _state_dict(payload):
    import torch
    if isinstance(payload, dict):
        for key in ("model_state", "state_dict"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        if payload and all(isinstance(value, torch.Tensor) for value in payload.values()):
            return payload
    raise ValueError("checkpoint has no model_state/state_dict tensor mapping")


def build_model(architecture, artifact_path: str | None):
    """Compile the architecture and load checkpoint weights strictly; raises ValueError on mismatch."""
    import torch
    from archai_compiler.pytorch_compiler import compile_architecture

    torch.manual_seed(0)
    model = compile_architecture(architecture).eval()
    spec = architecture.input_spec
    with torch.inference_mode():
        model(torch.zeros(1, spec.channels, spec.height, spec.width))  # materialize lazy layers
    if artifact_path:
        payload = torch.load(artifact_path, map_location="cpu", weights_only=True)
        try:
            model.load_state_dict(_state_dict(payload), strict=True)
        except RuntimeError as exc:
            raise ValueError(f"checkpoint does not match the architecture: {str(exc).splitlines()[0]}") from exc
    return model


class DeploymentRuntime:
    """LRU cache of loaded models, one lock per deployment so concurrent requests serialize."""

    def __init__(self, capacity: int = MAX_LOADED_MODELS):
        self._capacity = capacity
        self._models: OrderedDict[str, tuple[object, threading.Lock]] = OrderedDict()
        self._lock = threading.Lock()

    def loaded(self, deployment_id: str) -> bool:
        return deployment_id in self._models

    def unload(self, deployment_id: str) -> None:
        with self._lock:
            self._models.pop(deployment_id, None)

    def _get(self, deployment_id: str, loader):
        with self._lock:
            if deployment_id in self._models:
                self._models.move_to_end(deployment_id)
                return self._models[deployment_id]
        entry = (loader(), threading.Lock())
        with self._lock:
            self._models[deployment_id] = entry
            while len(self._models) > self._capacity:
                self._models.popitem(last=False)
        return entry

    def predict(self, deployment_id: str, loader, inputs) -> dict:
        import torch

        model, lock = self._get(deployment_id, loader)
        with lock, torch.inference_mode():
            begin = time.perf_counter()
            logits = model(inputs)
            latency_ms = (time.perf_counter() - begin) * 1000
        probabilities = torch.softmax(logits.float(), dim=1)
        return {"output_shape": list(logits.shape), "logits": logits.tolist(),
                "predicted_class": probabilities.argmax(dim=1).tolist(),
                "confidence": probabilities.max(dim=1).values.tolist(),
                "latency_ms": latency_ms}


class InMemoryDeploymentStore:
    def __init__(self):
        self._values: dict[str, dict] = {}
        self._lock = threading.Lock()

    def put(self, deployment: dict) -> dict:
        with self._lock:
            self._values[deployment["deployment_id"]] = deepcopy(deployment)
        return deployment

    def get(self, deployment_id: str) -> dict | None:
        value = self._values.get(deployment_id)
        return deepcopy(value) if value is not None else None

    def list(self) -> list[dict]:
        return sorted((deepcopy(value) for value in self._values.values()),
                      key=lambda value: value["created_at"], reverse=True)

    def delete(self, deployment_id: str) -> bool:
        with self._lock:
            return self._values.pop(deployment_id, None) is not None
