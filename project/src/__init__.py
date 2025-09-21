import os
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine

def run_migrations_with_env():
    os.environ.setdefault('ALEMBIC_CONFIG', 'alembic.ini')

    alembic_cfg = Config("alembic.ini")

    dsn = os.getenv('DATABASE_URL')
    if dsn is not None:
        alembic_cfg.set_main_option("sqlalchemy.url", dsn)

    # Run migrations
    command.upgrade(alembic_cfg, "head")

run_migrations_with_env()
