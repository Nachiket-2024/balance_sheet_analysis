import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Make 'mystic_auth' importable.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# This app's own models (backend/app/, not backend/mystic_auth/) — imported
# here too, alongside mystic_auth's own below, so autogenerate/`alembic
# check` see the full schema. Both share the same Base
# (mystic_auth.database.base.Base, re-exported as app.app_sdk.Base), so one
# alembic env/migration history covers both.
from app.balance_sheets.balance_sheet_model import BalanceSheet  # noqa: F401
from app.companies.company_model import Company  # noqa: F401
from mystic_auth.audit_log.audit_log_model import AuditLog  # noqa: F401
from mystic_auth.authorization.models.audit_log_model import AuthorizationAuditLog  # noqa: F401
from mystic_auth.authorization.models.policy_history_model import PolicyHistory  # noqa: F401
from mystic_auth.authorization.models.policy_model import Policy, UserPolicy  # noqa: F401
from mystic_auth.database.base import Base
from mystic_auth.user_table.user_model import User  # noqa: F401

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Run migrations in online mode with async engine."""
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection: Connection):
    """Run Alembic migrations using a synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
