from pydantic import BaseModel, EmailStr, field_validator

from ...emails.email_normalization import normalize_email


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)
