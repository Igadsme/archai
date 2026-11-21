from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture


def export_architecture_json(architecture: Architecture, path: str | Path) -> str:
    architecture = validate_architecture(architecture)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = architecture.model_dump(mode="json")
    temporary = destination.with_suffix(destination.suffix + ".partial")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2))
    temporary.replace(destination)
    return architecture.content_hash()


def model_fingerprint(model) -> str:
    """Hash ordered state-dict tensor bytes after model initialization."""
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        if not hasattr(tensor, "detach"):
            raise TypeError(f"state entry {name} is not a tensor")
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def export_safetensors(model, path: str | Path) -> str:
    try:
        from safetensors.torch import save_file
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra with safetensors to export weights") from exc
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tensors = {name: tensor.detach().cpu().contiguous() for name, tensor in model.state_dict().items()}
    save_file(tensors, str(destination))
    return model_fingerprint(model)


def export_onnx(model, example_input, path: str | Path, *, opset_version: int = 17) -> str:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra to export ONNX") from exc
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.onnx.export(model, example_input, str(destination), opset_version=opset_version,
                      input_names=["input"], output_names=["logits"], dynamo=False)
    return hashlib.sha256(destination.read_bytes()).hexdigest()
