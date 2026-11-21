import pytest


def test_sqlalchemy_model_factory_is_dependency_gated():
    pytest.importorskip("sqlalchemy")
    from archai_api.db import sqlalchemy_components
    Base, ArchitectureRow, SearchSessionRow, ExperimentRow, make_engine, make_session_factory = sqlalchemy_components()
    assert {ArchitectureRow.__tablename__, SearchSessionRow.__tablename__, ExperimentRow.__tablename__} == {"architectures", "search_sessions", "experiments"}
