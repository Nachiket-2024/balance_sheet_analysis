# The `os` module is used to access environment variables using `os.getenv(...)`.
import os

# `load_dotenv` loads variables from a `.env` file into `os.environ` so that
# they can be accessed by `os.getenv`. This allows environment configuration
# to be stored locally in a developer-friendly `.env` file.
from dotenv import load_dotenv

# Load all the key=value pairs defined in the `.env` file and add them
# to the current process environment, if not already present.
_ = load_dotenv()

def must_get_env(name: str) -> str:
    """
    Helper function that safely retrieves a required environment variable.
    
    Args:
        name (str): The name of the environment variable.
    
    Returns:
        str: The value of the environment variable.
    
    Raises:
        ValueError: If the variable is not set in the environment or .env file.
    
    Purpose:
        Avoid silent failures caused by missing secrets (e.g., JWT keys, OAuth credentials).
    """
    value = os.getenv(name)  # Try to read the variable from environment
    if value is None:
        # Fail fast if the variable is missing to prevent runtime errors
        raise ValueError(f"{name} is missing in the .env file.")
    return value


# Secret key used to sign and verify JWT tokens (HMAC SHA256 or similar).
# This must remain confidential and unpredictable.
JWT_SECRET: str = must_get_env("JWT_SECRET")


# OAuth 2.0 Client ID registered with Google Developers Console.
GOOGLE_CLIENT_ID: str = must_get_env("GOOGLE_CLIENT_ID")

# OAuth 2.0 Client Secret (keep this private and never commit it to Git).
GOOGLE_CLIENT_SECRET: str = must_get_env("GOOGLE_CLIENT_SECRET")

# Redirect URI configured in the Google API Console — it must match exactly
# what is defined there. Google redirects users to this URI after authentication.
GOOGLE_REDIRECT_URI: str = must_get_env("GOOGLE_REDIRECT_URI")