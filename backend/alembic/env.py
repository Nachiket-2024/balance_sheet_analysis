import os
import sys
from logging.config import fileConfig

from dotenv import dotenv_values
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
from app.balance_sheets.analysis_models import (  # noqa: F401
    AnalysisAlert,
    AnalysisNotificationDelivery,
    AnalysisNotificationPolicy,
    AnalysisNotificationPreference,
    AnalysisSettingsHistory,
    CompanyAnalysisSettings,
)
from app.balance_sheets.balance_sheet_model import (  # noqa: F401
    BalanceSheet,
    BalanceSheetImportAttempt,
    BalanceSheetSnapshot,
)
from app.balance_sheets.currency_model import CurrencyRate  # noqa: F401
from app.companies.company_model import Company  # noqa: F401
from app.financial_statements.financial_statement_model import (  # noqa: F401
    FinancialStatement,
    FinancialStatementImportAttempt,
    FinancialStatementSnapshot,
)
from app.llm.llm_model import LLMFeedback, LLMProviderProbe, LLMUsage  # noqa: F401
from app.reviews.review_model import ReviewAssignment, ReviewComment, ReviewReport, ReviewSignoff  # noqa: F401
from mystic_auth.audit_log.audit_log_model import AuditLog  # noqa: F401
from mystic_auth.auth.token_logic.consumed_refresh_token_model import ConsumedRefreshToken  # noqa: F401
from mystic_auth.auth.token_logic.token_revocation_version_model import TokenRevocationVersion  # noqa: F401
from mystic_auth.authorization.models.authorization_audit_log_model import AuthorizationAuditLog  # noqa: F401
from mystic_auth.authorization.models.policy_history_model import PolicyHistory  # noqa: F401
from mystic_auth.authorization.models.policy_model import Policy, UserPolicy  # noqa: F401
from mystic_auth.authorization.models.user_permission_model import UserPermission  # noqa: F401
from mystic_auth.database.base import Base
from mystic_auth.user.user_model import User  # noqa: F401
from mystic_auth.user_lifecycle.account_lifecycle_outbox_model import AccountLifecycleOutbox  # noqa: F401
from mystic_auth.user_session.session_model import UserSession  # noqa: F401

# Relative to repo root: alembic runs with cwd=backend/ from CI/conftest,
# so a bare load_dotenv() (which looks for ./.env) silently finds nothing.
# Only fills in values not already in the environment (Docker/CI always
# wins), and among the two files, app's value wins on overlap, matching
# every docker-compose invocation in this template's own scripts.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_env_file_values = {
    **dotenv_values(os.path.join(_REPO_ROOT, 'env', 'mystic_auth', '.env.dev')),
    **dotenv_values(os.path.join(_REPO_ROOT, 'env', 'app', '.env.dev')),
}
for _key, _value in _env_file_values.items():
    if _value is not None:
        os.environ.setdefault(_key, _value)
DATABASE_URL = os.environ["DATABASE_URL"]

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_name(name, type_, parent_names):
    """Excludes Procrastinate's own tables/types (procrastinate_jobs,
    procrastinate_events, ...) from autogenerate diffing. Their schema is
    applied via raw SQL straight from the installed `procrastinate` package
    (see versions/a4c1e8f2b6d3_add_procrastinate_schema.py), not declared as
    SQLAlchemy models here - without this, `alembic check`/`revision
    --autogenerate` would see them as present in the DB but absent from
    target_metadata and propose dropping them every time.
    """
    return not (type_ in ("table", "type") and name is not None and name.startswith("procrastinate_"))


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_name=_include_name,
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
    context.configure(connection=connection, target_metadata=target_metadata, include_name=_include_name)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
