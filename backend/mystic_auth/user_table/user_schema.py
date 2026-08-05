from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from ..emails.email_normalization import normalize_email
from .user_model import UserRole


class UserBase(BaseModel):
    """Shared base schema for User data used across create/read schemas."""

    # Capped to match signup_schema.SignupSchema : an unbounded string here
    # would feed straight into Argon2 hashing (password) or be
    # stored/displayed/logged indefinitely (name).
    name: str = Field(..., max_length=100)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)


class UserCreate(UserBase):
    """Schema used when registering a new user account. Role defaults to
    'user' : admin accounts are assigned separately."""

    password: str = Field(..., max_length=128)


class UserUpdate(BaseModel):
    """Schema for user-controlled profile updates only. Role changes are
    intentionally excluded : use admin endpoints for that.

    Backs both PUT /users/me and PUT /users/{email} (admin), so the same
    max_length caps signup_schema.SignupSchema applies must apply here too :
    an unbounded password submitted through either of these routes would
    otherwise be fed straight into Argon2 hashing uncapped.
    """

    name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=128)

    # Required (by PUT /users/me's own handler, not this schema) when an
    # account that already has a password is changing it via self-service :
    # a hijacked access-token cookie would otherwise be enough to fully lock
    # the legitimate owner out by just setting a new password, no proof of
    # the old one needed. Not required for the admin route (PUT
    # /users/{email}, which reuses this schema) or for an OAuth-only account
    # setting a password for the first time (nothing to confirm against).
    current_password: str | None = Field(default=None, max_length=128)


class UserStatsRead(BaseModel):
    """Aggregate counts backing the Users page's summary card. Independent
    of whatever page/filters the caller currently has applied to the main
    list - always reflects the whole table, so the card doesn't shift
    numbers around as an admin pages/filters through the list below it."""

    total: int
    verified: int
    unverified: int
    inactive: int


class UserRoleUpdate(BaseModel):
    """Schema used exclusively by admin endpoints to change a user's role.
    Kept separate from UserUpdate to make privilege escalation explicit."""

    role: UserRole


class UserRead(UserBase):
    """Schema returned in API responses. Exposes role as a plain string for
    clean serialization."""

    id: int

    # Display/grouping metadata only; None for an account with no role at all
    # (see user_model.py's Role note).
    role: UserRole | None

    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # When this account was soft-deleted, if ever : None means never deleted
    # (or fully restored via reactivation, which clears it).
    deleted_at: datetime | None = None

    # Pulled in from the ORM object (from_attributes) purely to derive
    # has_password below; excluded from the response so the hash itself is
    # never serialized.
    hashed_password: str | None = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    # Known mypy limitation w/ @computed_field + @property stacking (pydantic/pydantic#3849)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_password(self) -> bool:
        """Whether this account currently has a usable password credential
        (False for an OAuth-only account : see user_model.py's
        hashed_password column and oauth2_service.py's login_or_create_user,
        which is the only thing that ever clears it back to None)."""
        return self.hashed_password is not None
