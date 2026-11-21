from __future__ import annotations


def sqlalchemy_components():
    """Return optional SQLAlchemy primitives without making local API depend on them."""
    try:
        from sqlalchemy import JSON, Integer, String, Text, create_engine
        from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'platform' extra for SQLAlchemy support") from exc
    # SQLAlchemy resolves future annotations through the originating module.
    globals()["Mapped"] = Mapped

    class Base(DeclarativeBase):
        pass

    class ArchitectureRow(Base):
        __tablename__ = "architectures"
        architecture_id: Mapped[str] = mapped_column(String(64), primary_key=True)
        schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
        search_space: Mapped[str] = mapped_column(String(128), nullable=False)
        canonical_json: Mapped[dict] = mapped_column(JSON, nullable=False)
        generator_version: Mapped[str] = mapped_column(String(128), nullable=False)
        seed: Mapped[int | None] = mapped_column(Integer)

    class SearchSessionRow(Base):
        __tablename__ = "search_sessions"
        search_id: Mapped[str] = mapped_column(String(64), primary_key=True)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
        config: Mapped[dict] = mapped_column(JSON, nullable=False)
        budget_evaluations: Mapped[int] = mapped_column(Integer, nullable=False)
        consumed_evaluations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    class ExperimentRow(Base):
        __tablename__ = "experiments"
        experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
        architecture_id: Mapped[str] = mapped_column(String(64), nullable=False)
        dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
        dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)
        evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        seed: Mapped[int] = mapped_column(Integer, nullable=False)
        metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
        failure_detail: Mapped[str | None] = mapped_column(Text)

    def make_engine(url: str):
        return create_engine(url, pool_pre_ping=True)

    def make_session_factory(url: str):
        return sessionmaker(bind=make_engine(url), expire_on_commit=False)

    return Base, ArchitectureRow, SearchSessionRow, ExperimentRow, make_engine, make_session_factory
