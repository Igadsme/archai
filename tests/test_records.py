from archai_shared.records import ArtifactStore, ExperimentRecord, Provenance


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
