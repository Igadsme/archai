import pytest


def test_sqlalchemy_model_factory_is_dependency_gated():
    pytest.importorskip("sqlalchemy")
    from archai_api.db import sqlalchemy_components
    Base, ArchitectureRow, SearchSessionRow, ExperimentRow, make_engine, make_session_factory = sqlalchemy_components()
    assert {ArchitectureRow.__tablename__, SearchSessionRow.__tablename__, ExperimentRow.__tablename__} == {"architectures", "search_sessions", "experiments"}


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
