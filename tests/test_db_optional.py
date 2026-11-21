import pytest


def test_sqlalchemy_model_factory_is_dependency_gated():
    pytest.importorskip("sqlalchemy")
    from archai_api.db import sqlalchemy_components
    Base, ArchitectureRow, SearchSessionRow, ExperimentRow, make_engine, make_session_factory = sqlalchemy_components()
    assert {ArchitectureRow.__tablename__, SearchSessionRow.__tablename__, ExperimentRow.__tablename__} == {"architectures", "search_sessions", "experiments"}
    assert {"users", "api_credentials", "datasets", "model_checkpoints"}.issubset(Base.metadata.tables)


def test_sqlalchemy_architecture_store_round_trips_canonical_document(tmp_path):
    pytest.importorskip("sqlalchemy")
    from archai_api.db import SqlAlchemyArchitectureStore
    from archai_core.schema import Architecture, Edge, Node, TensorSpec

    architecture = Architecture(
        nodes=[Node(id="input", op="input", channels=3),
               Node(id="output", op="output", channels=3)],
        edges=[Edge(source="input", target="output")],
        input_spec=TensorSpec(channels=3, height=8, width=8),
        output_classes=10,
    )
    store = SqlAlchemyArchitectureStore.from_url(
        f"sqlite:///{tmp_path / 'archai.sqlite'}", initialize=True)
    stored = store.put(architecture)
    loaded = store.get(stored.content_hash())
    assert loaded is not None
    assert loaded.content_hash() == stored.content_hash()
    assert store.list(10)[0].canonical_json() == stored.canonical_json()


def test_sqlalchemy_search_and_experiment_stores_round_trip(tmp_path):
    pytest.importorskip("sqlalchemy")
    from archai_api.db import SqlAlchemyExperimentStore, SqlAlchemySearchStore
    from archai_shared.records import ExperimentRecord, Provenance

    url = f"sqlite:///{tmp_path / 'records.sqlite'}"
    search_store = SqlAlchemySearchStore.from_url(url, initialize=True)
    experiment_store = SqlAlchemyExperimentStore.from_url(url, initialize=True)
    config = {"algorithm": "random", "dataset_id": "unit", "budget_evaluations": 4, "seed": 9}
    assert search_store.put("search-1", config)["algorithm"] == "random"
    assert search_store.get("search-1")["budget_evaluations"] == 4
    record = ExperimentRecord(experiment_id="experiment-1", architecture_id="architecture-1",
        evidence_type="benchmark_lookup", status="created", metrics={"accuracy": 0.5},
        provenance=Provenance(dataset_id="unit", dataset_version="1", seed=9))
    experiment_store.put(record)
    loaded = experiment_store.get("experiment-1")
    assert loaded is not None
    assert loaded.provenance.dataset_id == "unit"
    assert loaded.metrics == {"accuracy": 0.5}
    updated = loaded.model_copy(update={"status": "completed", "metrics": {"accuracy": 0.7}})
    experiment_store.put(updated)
    assert experiment_store.get("experiment-1").status == "completed"
    assert experiment_store.get("experiment-1").metrics == {"accuracy": 0.7}


def test_sqlalchemy_model_registry_round_trips_checksum_manifest(tmp_path):
    pytest.importorskip("sqlalchemy")
    from archai_api.db import SqlAlchemyModelRegistry

    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"checkpoint")
    registry = SqlAlchemyModelRegistry.from_url(
        f"sqlite:///{tmp_path / 'models.sqlite'}", initialize=True)
    registered = registry.register(model_id="predictor", kind="predictor", version="v1",
                                   artifact_path=artifact, metadata={"seed": 4})
    assert registry.get("predictor", "v1").sha256 == registered.sha256
    assert registry.list()[0].metadata == {"seed": 4}


def test_sqlalchemy_dataset_store_enforces_checksum_and_immutability(tmp_path):
    pytest.importorskip("sqlalchemy")
    from archai_api.db import SqlAlchemyDatasetStore

    store = SqlAlchemyDatasetStore.from_url(f"sqlite:///{tmp_path / 'datasets.sqlite'}", initialize=True)
    value = store.put(dataset_id="unit", version="1", checksum="b" * 64, uri="file:///unit")
    assert store.get("unit", "1") == value
    with pytest.raises(ValueError, match="immutable"):
        store.put(dataset_id="unit", version="1", checksum="b" * 64, uri="file:///other")
