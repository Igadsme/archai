import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _load_space_module():
    spec = importlib.util.spec_from_file_location("archai_space_app", ROOT / "apps/huggingface-space/app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_space_status_verifies_checkpoint_and_model_manifest(tmp_path, monkeypatch):
    module = _load_space_module()
    checkpoint = tmp_path / "generator.pt"
    checkpoint.write_bytes(b"checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = tmp_path / "models.json"
    manifest.write_text(json.dumps([{"path": str(checkpoint), "sha256": digest}]))
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}")
    monkeypatch.setenv("ARCHAI_GENERATOR_CHECKPOINT", str(checkpoint))
    monkeypatch.setenv("ARCHAI_GENERATOR_CHECKPOINT_SHA256", digest)
    monkeypatch.setenv("ARCHAI_MODEL_MANIFEST", str(manifest))
    monkeypatch.setenv("ARCHAI_DATASET_MANIFEST", str(dataset))
    report = module.status()
    assert "verified" in report
    assert "1 verified" in report
