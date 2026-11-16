from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (regista as tabelas)
from app.config import database_url
from app.db import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = database_url()
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=url.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
