from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archai_core.schema import Architecture


def sqlalchemy_components():
    """Return optional SQLAlchemy primitives without making local API depend on them."""
    try:
        from sqlalchemy import DateTime, JSON, Integer, String, Text, create_engine
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
        provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
        started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def make_engine(url: str):
        return create_engine(url, pool_pre_ping=True)

    def make_session_factory(url: str, engine=None):
        return sessionmaker(bind=engine or make_engine(url), expire_on_commit=False)

    return Base, ArchitectureRow, SearchSessionRow, ExperimentRow, make_engine, make_session_factory


class SqlAlchemyArchitectureStore:
    """Persist canonical architecture documents through the configured database.

    The store deliberately keeps SQLAlchemy imports lazy so the local API can run
    without the platform extra. Schema creation is opt-in; production deployments
    should apply the Alembic migrations before starting the API.
    """

    def __init__(self, session_factory, architecture_row):
        self._session_factory = session_factory
        self._row = architecture_row

    @classmethod
    def from_url(cls, url: str, *, initialize: bool = False) -> "SqlAlchemyArchitectureStore":
        Base, architecture_row, _search_row, _experiment_row, make_engine, make_session_factory = sqlalchemy_components()
        engine = make_engine(url)
        if initialize:
            Base.metadata.create_all(engine)
        return cls(make_session_factory(url, engine), architecture_row)

    def put(self, architecture: "Architecture") -> "Architecture":
        from archai_core.schema import Architecture

        canonical = architecture.with_id()
        if not isinstance(canonical, Architecture):  # pragma: no cover - defensive typing guard
            raise TypeError("architecture must be an Architecture")
        session = self._session_factory()
        try:
            row = session.get(self._row, canonical.content_hash())
            payload = canonical.canonical_dict()
            if row is None:
                row = self._row(architecture_id=canonical.content_hash(),
                                schema_version=canonical.schema_version,
                                search_space=canonical.search_space,
                                canonical_json=payload,
                                generator_version=canonical.generator_version,
                                seed=canonical.seed)
                session.add(row)
            else:
                row.canonical_json = payload
                row.schema_version = canonical.schema_version
                row.search_space = canonical.search_space
                row.generator_version = canonical.generator_version
                row.seed = canonical.seed
            session.commit()
            return canonical
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, architecture_id: str) -> "Architecture | None":
        from archai_core.schema import Architecture

        session = self._session_factory()
        try:
            row = session.get(self._row, architecture_id)
            if row is None:
                return None
            architecture = Architecture.model_validate(row.canonical_json).with_id()
            if architecture.content_hash() != row.architecture_id:
                raise ValueError("stored architecture hash does not match canonical document")
            return architecture
        finally:
            session.close()

    def list(self, limit: int = 50) -> list["Architecture"]:
        from archai_core.schema import Architecture
        from sqlalchemy import select

        session = self._session_factory()
        try:
            rows = session.scalars(select(self._row).order_by(self._row.architecture_id).limit(limit)).all()
            values = []
            for row in rows:
                architecture = Architecture.model_validate(row.canonical_json).with_id()
                if architecture.content_hash() != row.architecture_id:
                    raise ValueError("stored architecture hash does not match canonical document")
                values.append(architecture)
            return values
        finally:
            session.close()


class SqlAlchemySearchStore:
    """Persist search configuration independently from the job queue."""

    def __init__(self, session_factory, search_row):
        self._session_factory = session_factory
        self._row = search_row

    @classmethod
    def from_url(cls, url: str, *, initialize: bool = False) -> "SqlAlchemySearchStore":
        Base, _architecture_row, search_row, _experiment_row, make_engine, make_session_factory = sqlalchemy_components()
        engine = make_engine(url)
        if initialize:
            Base.metadata.create_all(engine)
        return cls(make_session_factory(url, engine), search_row)

    def put(self, search_id: str, config: dict, *, status: str = "queued") -> dict:
        session = self._session_factory()
        try:
            row = session.get(self._row, search_id)
            values = {"search_id": search_id, "status": status, "algorithm": config["algorithm"],
                      "config": dict(config), "budget_evaluations": config["budget_evaluations"]}
            if row is None:
                row = self._row(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            return {"search_id": row.search_id, **row.config}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, search_id: str) -> dict | None:
        session = self._session_factory()
        try:
            row = session.get(self._row, search_id)
            return None if row is None else {"search_id": row.search_id, **row.config}
        finally:
            session.close()

    def set_status(self, search_id: str, status: str, consumed_evaluations: int | None = None) -> None:
        session = self._session_factory()
        try:
            row = session.get(self._row, search_id)
            if row is None:
                raise KeyError(search_id)
            row.status = status
            if consumed_evaluations is not None:
                row.consumed_evaluations = consumed_evaluations
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class SqlAlchemyExperimentStore:
    """Persist evidence-aware experiment records in the relational store."""

    def __init__(self, session_factory, experiment_row):
        self._session_factory = session_factory
        self._row = experiment_row

    @classmethod
    def from_url(cls, url: str, *, initialize: bool = False) -> "SqlAlchemyExperimentStore":
        Base, _architecture_row, _search_row, experiment_row, make_engine, make_session_factory = sqlalchemy_components()
        engine = make_engine(url)
        if initialize:
            Base.metadata.create_all(engine)
        return cls(make_session_factory(url, engine), experiment_row)

    def put(self, record):
        session = self._session_factory()
        try:
            row = session.get(self._row, record.experiment_id)
            values = {"experiment_id": record.experiment_id, "architecture_id": record.architecture_id,
                      "dataset_id": record.provenance.dataset_id, "dataset_version": record.provenance.dataset_version,
                      "evidence_type": record.evidence_type, "status": record.status, "seed": record.provenance.seed,
                      "metrics": dict(record.metrics), "failure_detail": record.failure_detail,
                      "provenance": record.provenance.model_dump(), "started_at": record.started_at,
                      "completed_at": record.completed_at}
            if row is None:
                row = self._row(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            session.commit()
            return record
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, experiment_id: str):
        from archai_shared.records import ExperimentRecord, Provenance

        session = self._session_factory()
        try:
            row = session.get(self._row, experiment_id)
            if row is None:
                return None
            provenance = Provenance.model_validate(row.provenance or {
                "dataset_id": row.dataset_id, "dataset_version": row.dataset_version, "seed": row.seed})
            return ExperimentRecord(experiment_id=row.experiment_id, architecture_id=row.architecture_id,
                                    evidence_type=row.evidence_type, status=row.status, metrics=row.metrics or {},
                                    provenance=provenance, started_at=row.started_at or datetime.now(timezone.utc),
                                    completed_at=row.completed_at, failure_detail=row.failure_detail)
        finally:
            session.close()
