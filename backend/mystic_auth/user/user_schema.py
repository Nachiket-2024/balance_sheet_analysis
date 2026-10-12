import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from ..emails.email_normalization import normalize_email
from .user_model import UserRole

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class UserBase(BaseModel):
    """Shared base schema for User data used across create/read schemas."""

    # Capped to match signup_schema.SignupSchema: an unbounded string here
    # would feed straight into Argon2 hashing (password) or be stored/
    # displayed/logged indefinitely (name).
    name: str = Field(..., max_length=100)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def _reject_blank_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)


class UserCreate(UserBase):
    """Schema used when registering a new user account. Role defaults to
    'user'; admin accounts are assigned separately."""

    password: str = Field(..., max_length=128)


class UserUpdate(BaseModel):
    """Schema for user-controlled profile updates only. Role changes are
    intentionally excluded; use management endpoints for that.

    Backs both PUT /users/me and PUT /users/{email} (management), so the
    same max_length caps as signup_schema.SignupSchema must apply here too:
    an unbounded password submitted through either route would otherwise
    feed straight into Argon2 hashing uncapped.
    """

    name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def _reject_blank_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped

    # Required (by PUT /users/me's own handler, not this schema) when an
    # account with a password changes it via self-service: otherwise a
    # hijacked access-token cookie alone could lock the real owner out by
    # setting a new password, no proof of the old one needed. Not required
    # for the management route (PUT /users/{email}, which reuses this
    # schema) or for an OAuth-only account setting a password for the first
    # time (nothing to confirm against).
    current_password: str | None = Field(default=None, max_length=128)

    # Per-user re-skin override (#rrggbb); see user_model.py's brand_color
    # column docstring. Explicit null resets to the app default.
    brand_color: str | None = Field(default=None, max_length=7)

    @field_validator("brand_color")
    @classmethod
    def _validate_hex_color(cls, value: str | None) -> str | None:
        if value is not None and not _HEX_COLOR_RE.match(value):
            raise ValueError("must be a hex color like #b5533c")
        return value


class UserSelfDeleteRequest(BaseModel):
    """Body for DELETE /users/me. Required (re-authentication) for an
    account that already has a password, same current-password gate as
    UserUpdate.current_password above; optional only for an OAuth-only
    account (hashed_password=None) with nothing to confirm against."""

    current_password: str | None = Field(default=None, max_length=128)


class UserStatsRead(BaseModel):
    """Aggregate counts backing the Users page's summary card. Always
    reflects the whole table regardless of the caller's current page/filter,
    so the card doesn't shift numbers as an operator pages through the list
    below it."""

    total: int
    verified: int
    unverified: int
    inactive: int


class UserRoleUpdate(BaseModel):
    """Schema used exclusively by management endpoints to change a user's role.
    Kept separate from UserUpdate to make privilege escalation explicit."""

    role: UserRole


class UserRead(UserBase):
    """Schema returned in API responses. Exposes role as a plain string for
    clean serialization."""

    id: int

    # Display/grouping metadata only; None for an account with no role at
    # all (see user_model.py's role note).
    role: UserRole | None

    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # None = using the app default scale (app/theme.ts); see user_model.py's
    # brand_color column docstring.
    brand_color: str | None = None

    # When this account was soft-deleted, if ever. None means never deleted
    # (or restored via reactivation, which clears it).
    deleted_at: datetime | None = None

    # Set on every successful sign-in; None means the account has never
    # signed in (e.g. created by an admin but not yet used).
    last_login_at: datetime | None = None

    # Pulled from the ORM object (from_attributes) only to derive
    # has_password below; excluded from the response so the hash itself is
    # never serialized.
    hashed_password: str | None = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    # Known mypy limitation w/ @computed_field + @property stacking (pydantic/pydantic#3849)
    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_password(self) -> bool:
        """Whether this account currently has a usable password credential.
        False for an OAuth-only account; see user_model.py's hashed_password
        column and oauth2_service.py's login_or_create_user, the only place
        that clears it back to None."""
        return self.hashed_password is not None


class UserSelfUpdateResponse(UserRead):
    """PUT /users/me's response shape: UserRead plus whether a password
    change's other-session revocation was actually confirmed.

    None for any update that wasn't a password change. False means the
    password was changed but Valkey was unreachable, so other sessions were
    NOT revoked and remain valid; see user_self_service_routes.py's
    update_my_profile."""

    sessions_revoked: bool | None = None


class UserAdminUpdateResponse(UserRead):
    """PUT /users/{email}'s response shape (an admin editing another user's
    account). Same sessions_revoked contract as UserSelfUpdateResponse
    above; see user_management_update_routes.py's update_any_user."""

    sessions_revoked: bool | None = None
