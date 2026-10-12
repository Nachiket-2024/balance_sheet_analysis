from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...database.base import Base


class TokenRevocationVersion(Base):
    """Durable Postgres version counter used to invalidate token scopes."""

    __tablename__ = "token_revocation_versions"

    key: Mapped[str] = mapped_column(String(length=512), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
