"""Explicitly offline SQLite coverage for the Alembic migration lifecycle."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import String, create_engine, inspect


ROOT = Path(__file__).parents[3]


def test_alembic_revisions_fit_version_num_column() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    context = MigrationContext.configure(url="postgresql+psycopg://")
    version_num_type = context._version.c.version_num.type
    assert isinstance(version_num_type, String)
    version_num_length = version_num_type.length
    assert version_num_length is not None

    revisions = ScriptDirectory.from_config(config).walk_revisions()
    for revision in revisions:
        assert len(revision.revision) <= version_num_length, (
            f"revision {revision.revision!r} exceeds Alembic version_num "
            f"VARCHAR({version_num_length})"
        )


def test_sqlite_offline_upgrade_constraints_and_downgrade(tmp_path: Path) -> None:
    database_path = (tmp_path / "tenant-migrations.db").as_posix()
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        inspector = inspect(engine)
        assert inspector.has_table("organization_business_profiles")
        assert inspector.get_pk_constraint("organization_business_profiles")[
            "constrained_columns"
        ] == ["organization_id"]
        foreign_keys = inspector.get_foreign_keys("organization_business_profiles")
        assert foreign_keys == [
            {
                "name": "fk_organization_business_profiles_organization_id_organizations",
                "constrained_columns": ["organization_id"],
                "referred_schema": None,
                "referred_table": "organizations",
                "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
        ]
        assert inspect(engine).get_indexes("organization_business_profiles") == []

        command.downgrade(config, "0001_initial_persistence")
        assert not inspect(engine).has_table("organization_business_profiles")
        assert inspect(engine).has_table("organizations")
        command.upgrade(config, "head")
        assert inspect(engine).has_table("organization_business_profiles")
    finally:
        engine.dispose()
