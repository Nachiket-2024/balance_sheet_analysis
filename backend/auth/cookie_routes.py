# FastAPI components for defining API routes, accessing request data, and raising exceptions
from fastapi import APIRouter, Request, HTTPException

# Response class that allows returning structured JSON with status codes and headers
from fastapi.responses import JSONResponse

# Internal utility functions to decode and create JWTs (handles validation, encoding, expiry, etc.)
from .jwt_handler import decode_token, create_access_token

# App config values: access token expiry time in minutes
from .settings import ACCESS_TOKEN_EXPIRE_MINUTES

# Constants for cookie names and expected token types
from .auth_constants import (
    ACCESS_TOKEN_NAME,     # e.g., "access_token"
    REFRESH_TOKEN_NAME,    # e.g., "refresh_token"
    REFRESH_TOKEN_TYPE,    # e.g., "refresh"
)

# Importing logger
from ..logging.logging_config import get_logger

# Create a sub-router for cookie-based auth handling
router = APIRouter(tags=["Cookie Auth"])

# Initialize logger for this module
logger = get_logger("cookie_routes")

# Standard cookie flags reused across multiple endpoints for security consistency
COOKIE_KWARGS = {
    "httponly": True,       # Prevent JavaScript from accessing the cookie
    "samesite": "lax",      # Helps mitigate CSRF while allowing redirects between your domain and frontend
    "secure": True,         # Only transmit cookies over HTTPS
}


@router.post("/auth/refresh")
def refresh_token_cookie(request: Request) -> JSONResponse:
    """
    Refreshes the user's access token by:
    - Extracting the refresh token from cookies.
    - Decoding and validating the refresh token.
    - Creating a new short-lived access token.
    - Returning it in a secure Set-Cookie header.
    """
    # Get the refresh token from the request's cookies
    refresh_token = request.cookies.get(REFRESH_TOKEN_NAME)
    if not refresh_token:
        logger.warning("Refresh token missing in the request")
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        # Decode and validate the refresh token
        payload = decode_token(refresh_token)

        # Check that the token type is 'refresh' (extra safety vs using access tokens)
        if payload.get("type") != REFRESH_TOKEN_TYPE:
            logger.warning("Invalid refresh token type")
            raise HTTPException(status_code=401, detail="Invalid refresh token type")

        # Extract user ID (subject) from the payload
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            logger.warning("Invalid user ID in token")
            raise HTTPException(status_code=401, detail="Invalid user ID in token")

        # Generate a new access token for the same user
        new_access_token = create_access_token({"sub": user_id})

        # Create a response and set the access token in a secure HttpOnly cookie
        res = JSONResponse(content={"message": "Access token refreshed"})
        res.set_cookie(
            key=ACCESS_TOKEN_NAME,
            value=new_access_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
            httponly=True,
            samesite="lax",   # must be a string literal (important for cookie spec compatibility)
            secure=True,
        )

        logger.info(f"Access token refreshed for user {user_id}")
        return res

    # Handle invalid token formats, expiry, or tampering
    except ValueError as e:
        logger.error(f"Error while decoding the refresh token: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/logout")
def logout_cookie() -> JSONResponse:
    """
    Logs the user out by deleting both access and refresh token cookies.
    This is a clean client-side logout. No backend state change is needed.
    """
    # Log the logout request
    logger.info("Logging out user")

    # Prepare the response and remove both tokens from the browser
    res = JSONResponse(content={"message": "Logged out"})

    # Deletes the access token cookie
    res.delete_cookie(ACCESS_TOKEN_NAME)

    # Deletes the refresh token cookie
    res.delete_cookie(REFRESH_TOKEN_NAME)

    logger.info("Successfully logged out and cookies deleted")
    return res
