from archai_shared.registry import ModelRegistry, sha256_file


def test_model_registry_hashes_and_deduplicates(tmp_path):
    artifact = tmp_path / "weights.safetensors"
    artifact.write_bytes(b"real-artifact-bytes")
    registry = ModelRegistry(tmp_path / "models.json")
    value = registry.register(model_id="ArchAI-Predictor", kind="predictor", version="v1",
                              artifact_path=artifact, metadata={"seed": 4})
    assert value.sha256 == sha256_file(artifact)
    assert registry.get("ArchAI-Predictor", "v1") == value
