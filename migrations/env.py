from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from order_utils.models import Base
from order_utils.storage import engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with engine.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        foreign_keys = None
        if is_sqlite:
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            connection.commit()
            # SQLite batch migrations must replace tables referenced by other tables.
            # Change this setting before BEGIN; SQLite ignores changes inside it.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()

        try:
            with connection.begin():
                if is_sqlite:
                    # Explicit BEGIN makes SQLite DDL rollback with the data changes.
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    if connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                        raise RuntimeError("Database has foreign-key violations before migration")

                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    render_as_batch=True,
                )

                with context.begin_transaction():
                    context.run_migrations()

                if is_sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                    raise RuntimeError("Migration produced foreign-key violations")
        finally:
            if is_sqlite:
                connection.rollback()
                connection.exec_driver_sql(f"PRAGMA foreign_keys={int(foreign_keys)}")
                connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
