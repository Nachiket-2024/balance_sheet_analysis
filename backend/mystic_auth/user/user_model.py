import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database.base import Base


class UserRole(str, enum.Enum):
    """All valid user roles. Mutually exclusive: a user holds exactly one at
    a time. Extend this enum to add new roles (e.g. moderator, staff)."""

    user = "user"
    admin = "admin"
    system = "system"


class User(Base):
    """
    Central user authentication model. Supports email/password and OAuth2
    (Google, etc.) authentication. The `role` column below is display/
    grouping metadata only; the actual PBAC decision-maker in
    `authorization/` never reads it.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, index=True)

    # Nullable for OAuth-only users.
    hashed_password: Mapped[str | None]

    # Nullable: a roleless account is authorized purely through assigned
    # policies. No Python-side `default=`, since SQLAlchemy would treat an
    # explicit role=None the same as omitted and apply the column default
    # anyway, making a roleless account impossible to persist.
    role: Mapped[UserRole | None] = mapped_column(Enum(UserRole))

    # Per-user re-skin of the app's brand accent/logo/favicon (#rrggbb). NULL
    # means "use the app default" (app/theme.ts's brand scale). See
    # AppearanceCard.tsx/applyAppearanceOverride.ts on the frontend for how
    # this becomes a full color scale.
    brand_color: Mapped[str | None] = mapped_column(String(7))

    is_verified: Mapped[bool] = mapped_column(default=False)

    # Soft-disable flag for deactivating accounts without deletion. Every
    # auth check already gates on this, so soft-delete reuses it instead of
    # adding a second, parallel "is deleted" check.
    is_active: Mapped[bool] = mapped_column(default=True)

    # Soft-delete marker, set when an account is deleted via the default
    # (reversible) flow. NULL means never deleted; kept separate from
    # is_active=False so an operator can tell "deactivated" apart from
    # "deleted". See docs/mystic_auth/security/decisions.md.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set on every successful sign-in (password or OAuth2), NULL for an
    # account that has never signed in. Cheap to sort/filter on since it's a
    # plain column, unlike aggregating the audit log for "last login".
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
