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
    identity used to key the revocation cache (see below).

    Real token validity is governed by durable Postgres version counters
    (jwt_service.py: `account_ver:{email}` account-wide, `chain_ver:
    {email}:{chain_id}` per-session), with Valkey as a cache, not by anything in this table. This
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
    # session - the durable revocation-version scope (chain_ver), and what
    # ties every row's rotations back to the one login that started it.
    # Nullable: rows created before this column existed carry none.
    chain_id: Mapped[str | None] = mapped_column(index=True)

    # Best-effort request metadata, nullable since not every token mint has a
    # live request (e.g. tests calling login_service.login directly).
    user_agent: Mapped[str | None]
    ip_address: Mapped[str | None]

    # Best-effort geolocation of ip_address at the time this row was
    # created, resolved via session_geolocation.py (a local MaxMind
    # GeoLite2-City database). Both null whenever ip_address is null,
    # GEOIP_DB_PATH is unset, or the lookup otherwise fails - never
    # re-resolved afterward even if ip_address's real-world location
    # data changes, same "first-login snapshot" spirit as created_at.
    city: Mapped[str | None]
    country: Mapped[str | None]

    # First-login time for this session; never updated by rotation.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Set explicitly by session_service on create/rotate, not an `onupdate`
    # trigger: an `onupdate` would also bump this the moment revoked_at is
    # set, blurring "last actually used" with "last row write".
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Mirrors current_jti's own expiry, for display only now (Valkey no
    # longer needs it to compute a blocklist TTL - chain_ver's own TTL is
    # set independently, see jwt_service.bump_chain_version).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # NULL while active. session_repository.py's revoke_by_id/revoke_by_jti/
    # revoke_by_chain_id/revoke_all_for_user/revoke_all_for_user_except_chain
    # delete the row outright instead of setting this column now - kept as a
    # column (not dropped) only so a row fetched moments before its own
    # delete still has a well-typed field to read, never actually persisted
    # as non-NULL. Rows that lapse via expires_at without an explicit revoke
    # are swept separately by procrastinate_tasks/session_cleanup_tasks.py.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
