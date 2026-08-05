import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database.base import Base


class UserRole(str, enum.Enum):
    """
    Enumeration of all valid user roles in the system.
    Roles are mutually exclusive : a user holds exactly one at a time.

    Extend this enum to add new roles (e.g. moderator, staff).
    """

    user = "user"
    admin = "admin"
    system = "system"


class User(Base):
    """
    Central user authentication model supporting:
    - Email/password authentication
    - OAuth2 authentication (Google, etc.)
    - A single `role` column kept as display/grouping metadata only : see
      `role` below and `authorization/` for the actual PBAC decision-maker,
      which never reads this column
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, index=True)

    # Nullable for OAuth-only users.
    hashed_password: Mapped[str | None]

    # Single role assigned to the user : mutually exclusive. Stored as a
    # native DB enum for data integrity. Nullable: role is display/grouping
    # metadata only (see authorization/ for the actual PBAC decision-maker,
    # which never reads this column) : the system must support accounts with
    # no role at all, authorized purely through assigned policies.
    #
    # Deliberately no Python-side `default=` here: SQLAlchemy applies a
    # column default whenever the value supplied at construction is None,
    # treating "explicitly None" the same as "omitted" : which would make it
    # impossible for any caller (including tests) to actually persist a
    # roleless account by passing role=None. Every real creation path
    # (signup_service.py, scripts/create_system_user.py) already sets role
    # explicitly, so no caller relied on a fallback default in practice.
    role: Mapped[UserRole | None] = mapped_column(Enum(UserRole))

    is_verified: Mapped[bool] = mapped_column(default=False)

    # Soft-disable flag for deactivating accounts without deletion. Also the
    # flag every auth check point already gates on (login_service.py,
    # oauth2_service.py, current_user_handler.py) : soft-deleting an account
    # reuses this exact mechanism rather than adding a second, parallel "is
    # deleted" check that every one of those call sites would also need
    # updating for.
    is_active: Mapped[bool] = mapped_column(default=True)

    # Soft-delete marker : set when an account is deleted via the default
    # (reversible) deletion flow. NULL means never deleted. Distinct from
    # is_active=False alone so an admin can tell "deliberately deactivated"
    # apart from "deleted" if that distinction is ever needed, and so
    # reactivation can clear it explicitly. A soft-deleted row is NOT
    # removed : see user_management_routes.py's soft-delete vs purge (hard delete)
    # routes, and docs/mystic_auth/security/decisions.md for the full rationale.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
