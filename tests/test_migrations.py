from alembic import command
from alembic.config import Config


def test_alembic_schema_can_upgrade_and_downgrade(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    from sqlalchemy import create_engine, inspect
    inspector = inspect(create_engine(database_url))
    tables = set(inspector.get_table_names())
    assert {"architectures", "search_sessions", "experiments", "datasets", "model_checkpoints"}.issubset(tables)
    assert "uq_model_checkpoints_model_id_version" in {
        index["name"] for index in inspector.get_indexes("model_checkpoints")
    }
    assert {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("experiments")} >= {
        "fk_experiments_architecture", "fk_experiments_dataset"
    }
    assert "fk_api_credentials_user" in {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys("api_credentials")
    }
    started_at = next(column for column in inspector.get_columns("experiments") if column["name"] == "started_at")
    assert started_at["nullable"] is False
