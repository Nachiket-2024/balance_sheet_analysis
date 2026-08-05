from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database.base import Base


class UserSession(Base):
    """
    One row per login session, surfaced on the "Manage Sessions" dashboard
    card so a user can see (and selectively end) every device they're
    currently signed in on.

    Refresh tokens are single-use and rotate their jti on every
    /auth/refresh call (see refresh_token_service.py), so the jti itself
    can't be this row's stable identity - `current_jti` tracks whichever
    jti currently represents this session, updated in place on each
    rotation (see session_repository.rotate), while `id` stays the stable
    identifier shown to and revoked by the client, and `chain_id` is the
    identity Redis actually keys revocation off (see below).

    Real token validity is governed entirely by Redis version counters
    (jwt_service.py: `account_ver:{email}` account-wide, `chain_ver:
    {email}:{chain_id}` per-session), not by anything in this table. This
    table is a best-effort mirror for display and for knowing which
    chain_id to bump when a specific session is revoked by id. A row here
    going missing or stale never affects login/refresh correctness (see
    session_service.py's try/except-everywhere), the same reasoning as
    security_audit_log's independence from the actual auth decision it
    records.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Unique: exactly one session row should ever claim a given jti at a time.
    current_jti: Mapped[str] = mapped_column(unique=True, index=True)

    # Stable per-login identity, unchanged across every rotation of this
    # session - what actually gets revoked in Redis (chain_ver), and what
    # ties every row's rotations back to the one login that started it.
    # Nullable: rows created before this column existed carry none.
    chain_id: Mapped[str | None] = mapped_column(index=True)

    # Best-effort request metadata, nullable since not every token mint has a
    # live request (e.g. tests calling login_service.login directly).
    user_agent: Mapped[str | None]
    ip_address: Mapped[str | None]

    # First-login time for this session; never updated by rotation.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Set explicitly by session_service on create/rotate, not an `onupdate`
    # trigger: an `onupdate` would also bump this the moment revoked_at is
    # set, blurring "last actually used" with "last row write".
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Mirrors current_jti's own expiry, for display only now (Redis no
    # longer needs it to compute a blocklist TTL - chain_ver's own TTL is
    # set independently, see jwt_service.bump_chain_version).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # NULL while active. Set by logout/logout-all/reuse-detection/explicit
    # per-session revoke; never deleted, so a user's own session history
    # remains inspectable.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
