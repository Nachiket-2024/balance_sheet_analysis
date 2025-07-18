import os  # For accessing environment variables and system paths
from pathlib import Path  # Modern and cross-platform path operations
from dotenv import load_dotenv  # Loads environment variables from a .env file

# Calculate the base directory of the project by going three levels up from this file's location.
# This assumes the structure is something like: project/app/core/settings.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Construct the full path to the `.env` file expected in the project root.
env_path = BASE_DIR / ".env"

# Load the environment variables from the specified `.env` file.
# Variables already set in the environment will not be overridden.
_ = load_dotenv(dotenv_path=env_path)

# Secret key used to sign JWT tokens.
# Should be a strong, random value in production.
# Fallback is "unsafe-default", useful for development or testing.
JWT_SECRET: str = os.getenv("JWT_SECRET", "unsafe-default")

# The cryptographic algorithm used for signing JWT tokens.
# HS256 is symmetric (same key for encode/decode) and widely used.
ALGORITHM: str = "HS256"

# Expiry time (in minutes) for access tokens.
# Short expiry improves security by reducing the window of misuse.
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# Expiry time (in days) for refresh tokens.
# These are long-lived tokens used to issue new access tokens without re-login.
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Connection string for the database, compatible with SQLAlchemy.
# The default is an SQLite database stored in the current directory.
# Replace this with a production-grade DB URL (e.g., PostgreSQL) as needed.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")
