# --- Standard library imports ---
from datetime import datetime, timedelta, timezone  # For setting token expiration timestamps
from typing import TypedDict, cast  # For precise payload typing and type casting

# --- External libraries ---
from jose import jwt, JWTError, ExpiredSignatureError  # PyJWT-compatible library for encoding/decoding JWT
from collections.abc import MutableMapping  # For typing the payload passed to `jwt.encode`

# --- Application settings ---
from .settings import (
    JWT_SECRET,                    # Secret key used for encoding/decoding JWTs
    ALGORITHM,                     # Hashing algorithm, e.g., "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES,  # Expiration duration for access token (in minutes)
    REFRESH_TOKEN_EXPIRE_DAYS,    # Expiration duration for refresh token (in days)
)


# --- Payload structure for JWT tokens ---
class JWTPayload(TypedDict, total=False):
    sub: str        # "Subject" — usually user ID
    exp: float      # "Expiration time" as UNIX timestamp
    type: str       # Either "access" or "refresh"


# --- Create an access token with a short expiry ---
def create_access_token(data: JWTPayload) -> str:
    """
    Returns a signed JWT access token that expires in ACCESS_TOKEN_EXPIRE_MINUTES.
    Adds 'exp' and 'type' = 'access' fields to payload.
    """
    payload: JWTPayload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire.timestamp()
    payload["type"] = "access"

    # Encode using HS256 (or as configured), and cast payload to MutableMapping to satisfy type checker
    return jwt.encode(cast(MutableMapping[str, object], dict(payload)), JWT_SECRET, algorithm=ALGORITHM)


# --- Create a refresh token with a longer expiry ---
def create_refresh_token(data: JWTPayload) -> str:
    """
    Returns a signed JWT refresh token that expires in REFRESH_TOKEN_EXPIRE_DAYS.
    Adds 'exp' and 'type' = 'refresh' fields to payload.
    """
    payload: JWTPayload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload["exp"] = expire.timestamp()
    payload["type"] = "refresh"

    return jwt.encode(cast(MutableMapping[str, object], dict(payload)), JWT_SECRET, algorithm=ALGORITHM)


# --- Decode and validate a token ---
def decode_token(token: str) -> JWTPayload:
    """
    Decodes the given JWT and verifies its signature and expiration.
    Returns the decoded payload if valid, otherwise raises a ValueError.
    """
    try:
        # Decode with algorithm and secret; raises if expired or invalid
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return cast(JWTPayload, cast(object, payload))  # Double cast helps satisfy type checker
    except ExpiredSignatureError as e:
        raise ValueError("Token expired") from e
    except JWTError as e:
        raise ValueError("Invalid token") from e
