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
    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert {"architectures", "search_sessions", "experiments", "datasets", "model_checkpoints"}.issubset(tables)
