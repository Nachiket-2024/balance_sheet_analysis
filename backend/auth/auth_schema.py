# --- Typed dictionaries for OAuth and user identity structures ---

from typing import TypedDict


class GoogleTokenResponse(TypedDict):
    """
    Structure of Google's token endpoint response (/token).
    
    Returned after exchanging authorization code for access/refresh tokens.
    """
    access_token: str         # Short-lived access token
    expires_in: int           # Lifetime of access_token (in seconds)
    id_token: str             # JWT for verifying user identity (contains user info)
    refresh_token: str        # Token to obtain new access_token when expired
    scope: str                # Granted OAuth scopes
    token_type: str           # Typically "Bearer"


class TokenResponse(TypedDict):
    """
    Internal token response returned to client by our backend.

    Used during login and refresh flows.
    """
    access_token: str         # JWT access token issued by backend
    token_type: str           # Always "bearer"


class GoogleUserInfo(TypedDict, total=False):
    """
    Structure of user info returned from Google's userinfo endpoint.

    This is typically fetched using the access token.
    Fields are optional (`total=False`) as they may vary.
    """
    id: str                   # User's unique Google ID
    email: str                # Email address
    verified_email: bool      # Whether email is verified
    name: str                 # Full name
    given_name: str           # First name
    family_name: str          # Last name
    picture: str              # Profile picture URL
    locale: str               # Preferred language/region
