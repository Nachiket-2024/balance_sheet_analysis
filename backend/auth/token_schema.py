# --- Import BaseModel from Pydantic for data validation and schema generation ---
from pydantic import BaseModel


# --- Schema representing a basic JWT token response ---
class Token(BaseModel):
    access_token: str    # Your app's JWT, used for authenticating requests
    token_type: str      # Typically 'bearer' for OAuth2-compliant flows
