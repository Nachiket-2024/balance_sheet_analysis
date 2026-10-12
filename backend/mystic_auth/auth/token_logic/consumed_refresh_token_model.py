from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ...database.base import Base


class ConsumedRefreshToken(Base):
    """Alembic metadata for durable single-use refresh-token claims."""

    __tablename__ = "consumed_refresh_tokens"

    jti: Mapped[str] = mapped_column(String(length=64), primary_key=True)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(length=64))
    account_ver: Mapped[int] = mapped_column(BigInteger(), nullable=False, server_default="0")
    chain_ver: Mapped[int] = mapped_column(BigInteger(), nullable=False, server_default="0")
