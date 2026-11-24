from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401  (registra las tablas)
from app.config import get_settings
from app.database import Base

config = context.config
if config.config_file_name:
    from logging.config import fileConfig
    fileConfig(config.config_file_name)

url = get_settings().DATABASE_URL
target_metadata = Base.metadata
es_sqlite = url.startswith("sqlite")


def run_migrations_offline():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=es_sqlite)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata,
                          render_as_batch=es_sqlite, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
