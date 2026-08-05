from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ...database.base import Base


class Policy(Base):
    """
    A Policy is the primary authorization unit in this PBAC system. Users
    are authorized by the policies assigned to them (see UserPolicy below),
    never by their role: role is metadata only (display/reporting), per
    the role-as-metadata invariant.

    Fields map directly onto the required policy shape:
      - identity/description: name, description
      - allowed actions: actions (a list of action-identifier strings, e.g.
        "users:read_own", the same vocabulary as authorization/permissions.py)
      - affected resources: resource_type ("users", or "*" for any resource)
      - conditions: conditions (JSON, e.g. {"self_only": true} for an
        ownership-scoped grant; see evaluators/policy_evaluator.py for how
        these are interpreted)
      - audit information: created_at/updated_at/created_by
      - inheritance/composition: deliberately NOT modeled as policy-to-policy
        references (e.g. "policy B extends policy A"): a user simply holds
        as many policies as they need (see UserPolicy), and the evaluator
        ORs across all of them. That achieves the same practical effect
        (broader access = more assigned policies) without a second
        composition mechanism to keep consistent with policy assignment.
    """

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Unique, human-readable identity for the policy (e.g. "self_service")
    name: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[str | None]

    # Action identifiers this policy grants (e.g. ["users:read_own"]).
    # Actions never grant access by themselves, only via an assigned,
    # active policy whose evaluation passes (see policy_evaluator.py).
    actions: Mapped[list[str]] = mapped_column(ARRAY(String))

    # Resource type this policy applies to (e.g. "users"). "*" matches any
    # resource type: used sparingly, for genuinely resource-agnostic grants.
    resource_type: Mapped[str]

    # Optional conditions narrowing the grant (e.g. ownership: only on the
    # caller's own resource). Null/empty means an unconditional grant for
    # the listed actions on the listed resource type.
    conditions: Mapped[dict | None] = mapped_column(JSONB)

    # Inactive policies are never evaluated as granting access, without
    # needing to delete (and lose the audit trail of) the policy row itself
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Email of the admin who created this policy, or "system" for the
    # baseline policies seeded by migration, nullable since not every
    # historical row necessarily has one.
    created_by: Mapped[str | None]

    # Quoted forward reference is required, not stylistic: UserPolicy is
    # defined below in this same file, and without `from __future__ import
    # annotations` this annotation is evaluated eagerly at class-body
    # execution time, before UserPolicy exists.
    user_links: Mapped[list["UserPolicy"]] = relationship(  # noqa: UP037
        back_populates="policy", cascade="all, delete-orphan"
    )


class UserPolicy(Base):
    """
    Many-to-many assignment of policies to users. This is the ONLY thing
    that determines what a user can do, never their role. Two users with
    the identical role can hold different UserPolicy rows and therefore
    have different authorization outcomes. Identical roles can have
    different permissions because policy assignments, not roles, grant access.
    """

    __tablename__ = "user_policies"
    __table_args__ = (
        # A user cannot be assigned the exact same policy twice
        UniqueConstraint("user_id", "policy_id", name="uq_user_policy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), index=True)

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Email of the admin who made this assignment, or "system" for
    # migration-seeded / signup-time default assignments
    assigned_by: Mapped[str | None]

    policy: Mapped[Policy] = relationship(back_populates="user_links")
