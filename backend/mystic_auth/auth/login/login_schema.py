from pydantic import BaseModel, EmailStr, Field, field_validator

from ...emails.email_normalization import normalize_email


class LoginSchema(BaseModel):
    email: EmailStr
    # Capped at the same length signup allows, so an arbitrarily large string
    # isn't fed straight into Argon2 hashing.
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)
