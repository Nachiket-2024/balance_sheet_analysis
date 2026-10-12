from pydantic import BaseModel, Field


class AccountDeleteConfirmSchema(BaseModel):
    # Capped well above any legitimate token's length, same as
    # PasswordResetConfirmSchema.token.
    token: str = Field(..., max_length=2048)
