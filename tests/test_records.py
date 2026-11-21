from archai_shared.records import ArtifactStore, ExperimentRecord, Provenance


def test_huggingface_space_status_is_evidence_only(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("archai_space", "apps/huggingface-space/app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("ARCHAI_GENERATOR_CHECKPOINT", raising=False)
    monkeypatch.setenv("ARCHAI_MODEL_MANIFEST", str(tmp_path / "missing.json"))
    monkeypatch.setenv("ARCHAI_DATASET_MANIFEST", str(tmp_path / "missing-dataset.json"))
    result = module.status()
    assert "not configured" in result
    assert "not displayed" in result


def test_experiment_provenance_roundtrip(tmp_path):
    store = ArtifactStore(tmp_path / "experiments.jsonl")
    record = ExperimentRecord(experiment_id="exp-1", architecture_id="arch-1",
                              evidence_type="benchmark_lookup", status="completed",
                              metrics={"validation_accuracy": 0.8},
                              provenance=Provenance(dataset_id="nasbench201", dataset_version="v1", seed=7))
    store.append(record)
    loaded = store.read_all()
    assert loaded[0].evidence_type == "benchmark_lookup"
    assert loaded[0].provenance.seed == 7
