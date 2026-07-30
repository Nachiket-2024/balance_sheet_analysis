from pydantic import BaseModel, EmailStr, Field, field_validator

from ...emails.email_normalization import normalize_email


class VerifyAccountSchema(BaseModel):
    # Capped well above any legitimate token's length
    token: str = Field(..., max_length=2048)


class VerifyAccountRequestSchema(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return normalize_email(value)
