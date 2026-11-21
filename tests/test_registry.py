from archai_shared.registry import ModelRegistry, sha256_file
from scripts.register_model import main as register_model_main


def test_model_registry_hashes_and_deduplicates(tmp_path):
    artifact = tmp_path / "weights.safetensors"
    artifact.write_bytes(b"real-artifact-bytes")
    registry = ModelRegistry(tmp_path / "models.json")
    value = registry.register(model_id="ArchAI-Predictor", kind="predictor", version="v1",
                              artifact_path=artifact, metadata={"seed": 4})
    assert value.sha256 == sha256_file(artifact)
    assert registry.get("ArchAI-Predictor", "v1") == value


def test_register_model_cli_writes_file_manifest(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "weights.bin"
    artifact.write_bytes(b"cli-artifact")
    manifest = tmp_path / "models.json"
    monkeypatch.setenv("ARCHAI_MODEL_MANIFEST", str(manifest))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["register_model", "--model-id", "ArchAI-Generator",
        "--kind", "generator", "--version", "v1", "--artifact", str(artifact)])
    assert register_model_main() == 0
    assert capsys.readouterr().out.strip()
    assert ModelRegistry(manifest).get("ArchAI-Generator", "v1") is not None
