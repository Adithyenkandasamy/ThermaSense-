"""
Alembic migrations environment.

Key design decisions:
  - Uses the SYNC psycopg2 driver (ALEMBIC_DATABASE_URL) because Alembic
    does not support async drivers natively.
  - Imports Base from app.database so autogenerate can detect model changes.
  - Creates the PostGIS extension before running migrations so geometry
    columns work in fresh databases.
  - Renders item-level differences (compare_type=True) so column type
    changes are detected by autogenerate.
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text

# Load environment variables from .env file
load_dotenv()

# ── Load app settings via env vars ────────────────────────────────
# We do NOT use get_settings() here because Alembic may run outside
# the app container. Instead we read the env var directly.
DATABASE_URL = os.environ.get(
    "ALEMBIC_DATABASE_URL",
    "postgresql+psycopg2://thermasense:thermasense@localhost:5434/thermasense",
)

# ── Alembic config ────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from env var (not from alembic.ini)
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ORM metadata for autogenerate ─────────────────────────
# All models must be imported before this point so Alembic can see them.
import app.models  # noqa: F401 — side-effect import, registers all ORM models
from app.database import Base  # noqa: E402

target_metadata = Base.metadata


def _ensure_postgis(connection) -> None:
    """Create PostGIS extension if it doesn't already exist."""
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generates SQL without connecting).

    Useful for generating SQL scripts to review or run manually.
    Note: PostGIS extension creation is skipped in offline mode.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (connects to the database).

    This is the normal mode used during development and deployment.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling in migration scripts
    )

    with connectable.connect() as connection:
        # Ensure PostGIS is installed before any migration runs
        _ensure_postgis(connection)
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,          # Detect column type changes
            compare_server_default=True,  # Detect server default changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
