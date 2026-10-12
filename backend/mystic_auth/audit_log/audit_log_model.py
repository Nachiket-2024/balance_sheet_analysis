from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..database.base import Base


class AuditLog(Base):
    """
    One row per security-sensitive auth event (login, logout, signup, OAuth2
    login, password reset, account verification, lockout, refresh token
    reuse). Written best-effort by audit_log_service.log_security_event,
    which never raises, so a logging failure can't break the action it
    describes (same as AuthorizationAuditLog).

    Append-only, with no foreign key to users: a user row can be deleted
    while its audit history stays, so user_email is a snapshot, not a
    reference. Nullable because some events (e.g. a failed login for an
    email that was never registered) have no matching user.

    Never store passwords, tokens, or other secrets here, only identifiers
    and outcome metadata.
    """

    __tablename__ = "security_audit_log"
    __table_args__ = (
        # Declared explicitly so alembic's autogenerate matches the composite
        # index migration e7a2c4d8f1b3 already created via raw SQL (needed
        # for exact column-direction control). Required by
        # AuditLogRepository.get_for_user's `WHERE user_email = ... ORDER BY
        # created_at DESC, id DESC` to avoid a sort step.
        Index(
            "ix_security_audit_log_user_email_created_at",
            "user_email",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Nullable for events with no resolvable account (e.g. login attempt
    # against a nonexistent email). No separate index: the composite
    # ix_security_audit_log_user_email_created_at index already covers
    # plain user_email lookups via its leftmost prefix.
    user_email = Column(String, nullable=True)

    # e.g. "login_success", "login_failure", "logout", "signup",
    # "account_locked". Full vocabulary in audit_log_service.py.
    event_type = Column(String, nullable=False, index=True)

    success = Column(Boolean, nullable=False)

    # Nullable since not every call site has a live request (e.g. background
    # token-reuse detection).
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Ties this row back to the structured app logs for the same request.
    request_id = Column(String, nullable=True)

    # Free-form event-specific detail (e.g. {"revoked_count": 3}). Never
    # secrets/passwords/tokens.
    event_metadata = Column("metadata", JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
