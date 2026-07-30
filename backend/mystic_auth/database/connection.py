from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..core.settings import settings


class Database:
    """Encapsulates async engine creation and session management."""

    def __init__(self, database_url: str):
        self.database_url = database_url

        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            # Checks a pooled connection is still alive before handing it out;
            # without this, a connection that went stale (DB restart, network
            # blip, idle firewall timeout) surfaces as a request-time
            # OperationalError instead of being silently replaced, which
            # matters most for a long-lived worker/backend process that isn't
            # restarted often.
            pool_pre_ping=True,
            # Recycles pooled connections after 30 minutes, below most default
            # DB/proxy idle-connection timeouts, so connections are refreshed
            # proactively rather than found dead reactively.
            pool_recycle=1800,
        )

        self.async_session = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False
        )

    async def get_session(self):
        async with self.async_session() as session:
            yield session


database = Database(settings.DATABASE_URL)
