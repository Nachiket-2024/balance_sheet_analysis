from pydantic import BaseModel, EmailStr, Field, field_validator

from ...emails.email_normalization import normalize_email


class SignupSchema(BaseModel):
    # Capped so an unbounded string can't be stored/displayed/logged indefinitely
    name: str = Field(..., max_length=100)
    email: EmailStr
    # Capped so an arbitrarily large string isn't fed straight into Argon2 hashing
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # Lowercased at the input boundary so casing is already canonical
        # before it reaches signup_service: the CRUD layer normalizes too,
        # but doing it here means logs/tokens/audit see the canonical form
        # from the earliest point, not just at the DB.
        return normalize_email(value)
