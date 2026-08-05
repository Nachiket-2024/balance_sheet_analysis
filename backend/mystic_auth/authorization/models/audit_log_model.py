from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...database.base import Base


class AuthorizationAuditLog(Base):
    """
    One row per authorization decision (per the PBAC
    Work: "Authorization decisions must be auditable" / "Automatically log
    every authorize() call"). Written by
    AuthorizationService.authorize_detailed, the single choke point every
    authorize()/require() call goes through, so no protected route or
    caller needs to log anything itself.

    Deliberately append-only and independent of the policies/user_policies
    tables (no foreign keys to Policy): a policy referenced by an old audit
    entry may since have been edited or deleted, and the audit trail must
    keep reflecting exactly what was evaluated *at the time*, not whatever
    that policy id currently means. Policy names, not just ids, are stored
    for the same reason: a renamed or deleted policy's audit history
    should still read as which policy(ies) were involved.
    """

    __tablename__ = "authorization_audit_log"
    __table_args__ = (
        # Declared here (rather than left implicit) so alembic's autogenerate
        # sees the same composite index migration c7f1a3e9d2b6 created via
        # raw SQL for exact column-direction control, otherwise `alembic
        # check`/`revision --autogenerate` would propose dropping it, since
        # nothing in the model would otherwise reference its existence.
        Index(
            "ix_audit_log_user_email_created_at",
            "user_email",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # The acting user's email, never their role (see PBAC decision-making).
    # No `index=True` here: this column is covered by the composite
    # `ix_audit_log_user_email_created_at` index instead (its leftmost
    # prefix already serves plain user_email lookups), see migration
    # c7f1a3e9d2b6 for the query-plan evidence behind that decision.
    user_email: Mapped[str]
    action: Mapped[str] = mapped_column(index=True)
    resource_type: Mapped[str]

    # Best-effort identifier for the specific resource instance involved
    # (e.g. a target user's email), since "resource" can be an arbitrary
    # dict, not every check has (or needs) one.
    resource_identifier: Mapped[str | None]

    # The outcome of PolicyEvaluationEngine.evaluate_detailed
    allowed: Mapped[bool]

    # Every policy whose resource_type + action matched (regardless of
    # whether its conditions passed): "what was even considered"
    candidate_policy_names: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # The subset of candidates whose conditions also passed: "what
    # actually granted this" (empty when allowed is False)
    granting_policy_names: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # {policy_name: [condition_key, ...]} for every candidate policy whose
    # conditions did NOT pass: exactly which condition(s) failed on each
    # rejected policy (see evaluators/authorization_decision.py), so "why
    # was this denied" is answerable from the audit trail alone. Null when
    # no policy was rejected (either allowed=True via an unconditional
    # match, or no candidate policies existed at all).
    failed_conditions: Mapped[dict | None] = mapped_column(JSONB)

    # Whatever the caller supplied as `context` (e.g. request metadata, IP)
    context: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
