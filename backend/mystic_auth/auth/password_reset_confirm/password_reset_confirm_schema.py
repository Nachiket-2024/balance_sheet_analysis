from pydantic import BaseModel, Field


class PasswordResetConfirmSchema(BaseModel):
    # Capped well above any legitimate token's length
    token: str = Field(..., max_length=2048)
    # Same cap as signup/login
    new_password: str = Field(..., max_length=128)
