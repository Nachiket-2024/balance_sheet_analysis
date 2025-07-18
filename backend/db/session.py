# Import the standard `os` module for accessing environment variables
import os

# Import SQLAlchemy's engine and session utilities for ORM-based DB access
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import dotenv utilities to load environment variables from a .env file
from dotenv import load_dotenv

# Import `Path` for cross-platform file system path handling
from pathlib import Path


# --- Load environment variables from the project root ---

# Resolve BASE_DIR to the root of the project (three levels up from this file)
# Useful when running code from subdirectories (e.g., scripts, tests)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Construct the path to the `.env` file in the root directory
env_path = BASE_DIR / ".env"

# Load all variables from the .env file into the environment
_ = load_dotenv(dotenv_path=env_path)


# --- Get the database connection URL ---

# Try fetching the DATABASE_URL from environment variables (from .env or system)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Fail early if the variable is not defined
if SQLALCHEMY_DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in the .env file.")

# Extract the database name from the URL
db_name = SQLALCHEMY_DATABASE_URL.split('/')[-1]

# Print only the database name
print(f"Loaded DATABASE_NAME: {db_name} (Remove this when in production)")

# --- SQLAlchemy Engine and Session setup ---

# Create the SQLAlchemy engine instance
# This manages the connection pool and issues actual SQL to the database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a sessionmaker — this is a factory to create new DB sessions
# - `autocommit=False`: You must call `commit()` explicitly.
# - `autoflush=False`: ORM changes aren't auto-flushed to DB unless manually done.
# - `bind=engine`: Ties this session to our database engine.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
