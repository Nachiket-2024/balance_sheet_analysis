from pydantic import BaseModel, Field


class TokenPairResponseSchema(BaseModel):
    access_token: str = Field(..., description="Newly issued access token")
    refresh_token: str = Field(..., description="Newly issued refresh token")
